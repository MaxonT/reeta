import pytest

from app.config import settings
from app.content import load_answer_key
from app.exam import AnswerStream, transcripts_text, verify_quote, verify_quotes
from app.llm.mock import MockLLMClient
from app.repo.sqlite_repo import SQLiteRepository
from app.service import ReetaService
from app.speech.base import BrowserSpeechClient
from app.words import sentences_to_words


def stream_text(chunks):
    s, out = AnswerStream(), ""
    for c in chunks:
        out += s.feed(c)
    return out, s.finish()


def test_answer_stream_hides_the_quote_tail_even_when_split_across_chunks():
    shown, (answer, quote) = stream_text(["I think it calls itself.\nQUO", "TE: ", "calls it", "self"])
    assert shown == "I think it calls itself."
    assert answer == "I think it calls itself."
    assert quote == "calls itself"


def test_answer_stream_none_quote_and_missing_marker():
    shown, (answer, quote) = stream_text(["I don't know.\nQUOTE: NONE"])
    assert (shown, answer, quote) == ("I don't know.", "I don't know.", None)
    shown, (answer, quote) = stream_text(["Just an answer"])
    assert (shown, answer, quote) == ("Just an answer", "Just an answer", None)


def lecture(words_text="A function can call itself. Recursion stops by itself."):
    sents = [{"text": "A function can call itself.", "start_ms": 0, "end_ms": 2000},
             {"text": "Recursion stops by itself.", "start_ms": 2000, "end_ms": 4000}]
    return {"id": 7, "text": words_text, "words": sentences_to_words(sents)}


def test_verify_quote_finds_timings_and_ignores_case_and_punctuation():
    found = verify_quote("recursion STOPS by itself", [lecture()])
    assert found["lecture_id"] == 7
    assert found["quote"] == "Recursion stops by itself."
    assert found["start_ms"] == 2000 and found["end_ms"] == 4000


def test_verify_quote_tolerates_a_misquoted_ending_but_rejects_fabrications():
    assert verify_quote("a function can call itself because python says", [lecture()]) is not None  # 5 of 8 words
    assert verify_quote("a function can call itself because python says so", [lecture()]) is None  # 5 of 9: under 60%
    assert verify_quote("recursion needs a base case to stop", [lecture()]) is None
    assert verify_quote("itself", [lecture()]) is None  # too short to count
    assert verify_quote(None, [lecture()]) is None


def test_verify_quote_on_typed_lecture_has_no_timings():
    found = verify_quote("call itself", [{"id": 1, "text": "A function can call itself.", "words": []}])
    assert found["start_ms"] is None and found["end_ms"] is None


def test_transcripts_text_labels_lectures_and_skips_empty():
    out = transcripts_text([{"text": "one"}, {"text": "  "}, {"text": "two"}])
    assert out == "[Lecture 1]\none\n\n[Lecture 3]\ntwo"


@pytest.fixture
def key():
    return load_answer_key(settings.content_dir)


def make_svc(key, tmp_path, llm):
    repo = SQLiteRepository(":memory:")
    return repo, ReetaService(repo, BrowserSpeechClient(), llm, key, tmp_path / "audio")


def teach(repo, session="s1"):
    lec = lecture()
    lid = repo.create_lecture(session, "lecture", lec["text"])
    repo.update_lecture(lid, text=lec["text"], words=lec["words"])
    return lid


def by_event(events):
    out = {}
    for e in events:
        out.setdefault(e["event"], []).append(e["data"])
    return out


def test_run_exam_with_mock_grades_each_answer_and_stores_everything(key, tmp_path):
    repo, svc = make_svc(key, tmp_path, MockLLMClient())
    lid = teach(repo)
    events = list(svc.run_exam("s1", 5))
    ev = by_event(events)

    assert len(ev["questions"][0]["questions"]) == 5
    assert [g["id"] for g in ev["graded"]] == ["q1", "q2", "q3", "q4", "q5"]  # question order
    done = {d["id"]: d for d in ev["answer_done"]}
    assert done["q1"]["supported"] and done["q1"]["quote"] == "A function can call itself."
    assert done["q1"]["lecture_id"] == lid and done["q1"]["quote_end_ms"] == 2000
    graded = {g["id"]: g for g in ev["graded"]}
    assert graded["q1"]["is_correct"] and graded["q1"]["reason"] == "correct"
    assert not graded["q2"]["is_correct"] and graded["q2"]["reason"] == "wrong"  # taught the misconception
    assert graded["q3"]["reason"] == "not_taught" and not done["q3"]["supported"]
    assert ev["done"][0]["score"] == 1 and ev["done"][0]["total"] == 5

    attempts = repo.list_attempts("s1")
    assert attempts[0]["score"] == 1 and len(attempts[0]["answers"]) == 5
    first = attempts[0]["answers"][0]
    assert first["prompt"] and first["reference_answer"] and first["quote"] and first["is_correct"] is True


def test_answer_deltas_never_contain_the_quote_marker(key, tmp_path):
    repo, svc = make_svc(key, tmp_path, MockLLMClient())
    teach(repo)
    deltas = [e["data"]["text"] for e in svc.run_exam("s1", 2) if e["event"] == "answer_delta"]
    assert deltas and "QUOTE" not in "".join(deltas)


class InventsQuotes(MockLLMClient):
    """Answers confidently from 'outside knowledge' with a quote that is not in any transcript."""

    def answer_stream(self, question, transcripts):
        yield "Every recursive function needs a base case.\nQUOTE: you always need a base case to stop"


def test_a_quote_not_in_the_transcripts_does_not_count(key, tmp_path):
    repo, svc = make_svc(key, tmp_path, InventsQuotes())
    teach(repo)
    ev = by_event(svc.run_exam("s1", 2))
    assert all(not d["supported"] and d["quote"] is None for d in ev["answer_done"])
    assert all(g["reason"] == "not_taught" and not g["is_correct"] for g in ev["graded"])
    answers = repo.list_attempts("s1")[0]["answers"]
    assert all(a["answer"] is None and a["line"] for a in answers)  # NULL answer, but what she said is kept


class Unsupported(MockLLMClient):
    """The quote is real but does not back the answer: the judge says unsupported."""

    def judge(self, question, reference, answer, quote):
        return {"is_correct": False, "supported": False, "feedback": "The quote does not say that."}


def test_an_unsupported_verdict_counts_as_not_taught(key, tmp_path):
    repo, svc = make_svc(key, tmp_path, Unsupported())
    teach(repo)
    ev = by_event(svc.run_exam("s1", 1))
    assert ev["graded"][0]["reason"] == "not_taught" and not ev["graded"][0]["is_correct"]
    a = repo.list_attempts("s1")[0]["answers"][0]
    assert a["answer"] is None and a["quote"] is None and a["lecture_id"] is None and a["line"]


class BrokenQuestions(MockLLMClient):
    def generate_questions(self, key, n):
        raise RuntimeError("model down")


def test_run_exam_reports_an_error_event_if_questions_cannot_be_written(key, tmp_path):
    repo, svc = make_svc(key, tmp_path, BrokenQuestions())
    events = list(svc.run_exam("s1", 3))
    assert [e["event"] for e in events] == ["error"]
    assert repo.list_attempts("s1") == []


class RecordsTranscripts(MockLLMClient):
    def answer_stream(self, question, transcripts):
        self.seen = transcripts
        yield "A function can call itself.\nQUOTE: A function can call itself"  # only true of the first lecture


def test_exam_uses_the_newest_lecture_plus_office_hours_after_it(key, tmp_path):
    llm = RecordsTranscripts()
    repo, svc = make_svc(key, tmp_path, llm)
    repo.create_lecture("s1", "lecture", "A function can call itself. Old lecture.")
    repo.create_lecture("s1", "office_hours", "Old follow up.")
    repo.create_lecture("s1", "lecture", "Recursion stops by itself. New lecture.")
    repo.create_lecture("s1", "office_hours", "New follow up.")
    repo.create_lecture("other", "lecture", "Someone else's lecture.")
    ev = by_event(svc.run_exam("s1", 1))
    assert "New lecture" in llm.seen and "New follow up" in llm.seen
    assert "Old lecture" not in llm.seen and "Old follow up" not in llm.seen and "Someone else" not in llm.seen
    assert not ev["answer_done"][0]["supported"]  # her quote is from the old lecture, which she no longer has


def test_exam_with_only_office_hours_uses_all_of_them(key, tmp_path):
    llm = RecordsTranscripts()
    repo, svc = make_svc(key, tmp_path, llm)
    repo.create_lecture("s1", "office_hours", "First follow up.")
    repo.create_lecture("s1", "office_hours", "Second follow up.")
    list(svc.run_exam("s1", 1))
    assert "First follow up" in llm.seen and "Second follow up" in llm.seen


def test_exam_skips_a_blank_lecture(key, tmp_path):
    llm = RecordsTranscripts()
    repo, svc = make_svc(key, tmp_path, llm)
    repo.create_lecture("s1", "lecture", "Good lecture.")
    repo.create_lecture("s1", "lecture", "")  # e.g. a failed upload left an empty row
    list(svc.run_exam("s1", 1))
    assert "Good lecture" in llm.seen  # the blank newest lecture does not wipe out the real one


def test_answer_stream_reads_several_quote_lines_and_caps_them_at_three():
    s = AnswerStream()
    s.feed("It has thylakoids and a stroma.\nQUOTE: thylakoids hold the chlorophyll\nquote: the fluid is the stroma\n")
    s.feed("QUOTE: NONE\nQUOTE: third one\nQUOTE: fourth one")
    answer, quotes = s.finish_all()
    assert answer == "It has thylakoids and a stroma."
    assert quotes == ["thylakoids hold the chlorophyll", "the fluid is the stroma", "third one"]
    assert s.finish() == (answer, "thylakoids hold the chlorophyll")


def test_verify_quotes_keeps_real_ones_and_drops_fabrications_and_repeats():
    lecs = [{"id": 1, "text": "Thylakoids hold the chlorophyll. The fluid around them is the stroma.", "words": []}]
    found = verify_quotes(["thylakoids hold the chlorophyll", "the fluid around them is the stroma",
                           "Thylakoids hold the chlorophyll!", "mitochondria make all the sugar"], lecs)
    assert [f["quote"] for f in found] == ["Thylakoids hold the chlorophyll.", "The fluid around them is the stroma."]


class TwoPassages(MockLLMClient):
    """An answer stitched from two sentences, citing each, like the chloroplast question."""

    def answer_stream(self, question, transcripts):
        yield "Thylakoids hold chlorophyll and the stroma runs the Calvin cycle.\n"
        yield "QUOTE: thylakoids hold the chlorophyll\nQUOTE: the fluid around them is the stroma"

    def judge(self, question, reference, answer, quote):
        self.judged = quote
        return {"is_correct": True, "supported": True, "feedback": "ok"}


def test_an_answer_built_from_two_passages_is_supported_and_the_judge_sees_both(key, tmp_path):
    llm = TwoPassages()
    repo, svc = make_svc(key, tmp_path, llm)
    lid = repo.create_lecture("s1", "lecture", "Thylakoids hold the chlorophyll. The fluid around them is the stroma.")
    ev = by_event(svc.run_exam("s1", 1))
    done = ev["answer_done"][0]
    assert done["supported"] and done["lecture_id"] == lid
    assert done["quote"] == "Thylakoids hold the chlorophyll."  # the single quote fields hold the first one
    assert [q["quote"] for q in done["quotes"]] == ["Thylakoids hold the chlorophyll.",
                                                    "The fluid around them is the stroma."]
    assert llm.judged == "Thylakoids hold the chlorophyll. [...] The fluid around them is the stroma."
    assert ev["graded"][0]["is_correct"]


class FakeQuoteOnly(MockLLMClient):
    def answer_stream(self, question, transcripts):
        yield "Something.\nQUOTE: this sentence was never said anywhere"


def test_a_rejected_quote_is_shown_in_the_feedback(key, tmp_path):
    repo, svc = make_svc(key, tmp_path, FakeQuoteOnly())
    teach(repo)
    ev = by_event(svc.run_exam("s1", 1))
    assert not ev["answer_done"][0]["supported"] and ev["answer_done"][0]["quotes"] == []
    assert "this sentence was never said anywhere" in repo.list_attempts("s1")[0]["answers"][0]["feedback"]
