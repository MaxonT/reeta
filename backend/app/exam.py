"""Pure helpers for the live exam: parse Reeta's reply and verify Reeta's quote against the transcripts."""
import math
import re

MARKER = "QUOTE:"
_MARKER_RE = re.compile(r"quote\s*:", re.IGNORECASE)


class AnswerStream:
    """Reeta replies `<answer text>\\nQUOTE: "<verbatim words>"` (or `QUOTE: NONE`).
    feed() returns only the new answer text, holding back anything that could be the start of the marker."""

    def __init__(self):
        self.buf = ""
        self.sent = 0

    def _visible_end(self) -> int:
        m = _MARKER_RE.search(self.buf)
        if m:
            return len(self.buf[:m.start()].rstrip())
        # hold back a trailing partial marker like "QUO" and the whitespace before it
        text = self.buf.rstrip()
        for k in range(min(len(MARKER) - 1, len(text)), 0, -1):
            if MARKER.lower().startswith(text[-k:].lower()):
                return len(text[:-k].rstrip())
        return len(text)

    def feed(self, chunk: str) -> str:
        self.buf += chunk
        end = self._visible_end()
        out = self.buf[self.sent:end] if end > self.sent else ""
        self.sent = max(self.sent, end)
        return out

    def finish(self) -> tuple[str, str | None]:
        """-> (answer_text, quote or None)"""
        m = _MARKER_RE.search(self.buf)
        answer = (self.buf[:m.start()] if m else self.buf).strip()
        quote = self.buf[m.end():].strip().strip("\"'“”‘’").strip() if m else ""
        if not quote or quote.upper().startswith("NONE"):
            return answer, None
        return answer, quote


def _norm(token: str) -> str:
    return re.sub(r"[^a-z0-9']", "", token.lower().replace("’", "'"))


def _lecture_tokens(lecture: dict) -> list[tuple[str, str, int | None, int | None]]:
    """(normalized, original, start_ms, end_ms) per word. Typed lectures have no timings."""
    out = []
    if lecture.get("words"):
        for w in lecture["words"]:
            n = _norm(w["w"])
            if n:
                out.append((n, w["w"], w.get("start_ms"), w.get("end_ms")))
    else:
        for w in lecture.get("text", "").split():
            n = _norm(w)
            if n:
                out.append((n, w, None, None))
    return out


def verify_quote(quote: str | None, lectures: list[dict]) -> dict | None:
    """Find the quote in the lectures. Accepts a verbatim stretch covering at least 60% of the quote
    (min 2 words) so a slightly misquoted ending does not discard a real quote. Never trusts the model:
    returns None unless the words are really in a transcript. -> {lecture_id, quote, start_ms, end_ms}"""
    q = [t for t in (_norm(w) for w in (quote or "").split()) if t]
    if len(q) < 2:
        return None
    need = max(2, math.ceil(0.6 * len(q)))
    best = None  # (length, lecture, start index)
    for lec in lectures:
        toks = _lecture_tokens(lec)
        norm = [t[0] for t in toks]
        for length in range(len(q), need - 1, -1):
            if best and length <= best[0]:
                break
            found = False
            for i in range(len(q) - length + 1):
                piece = q[i:i + length]
                for j in range(len(norm) - length + 1):
                    if norm[j:j + length] == piece:
                        best, found = (length, lec, toks[j:j + length]), True
                        break
                if found:
                    break
            if found:
                break
    if not best:
        return None
    _, lec, span = best
    return {"lecture_id": lec["id"], "quote": " ".join(t[1] for t in span),
            "start_ms": span[0][2], "end_ms": span[-1][3]}


def transcripts_text(lectures: list[dict]) -> str:
    """All of a session's lectures as one block for Reeta's prompt."""
    return "\n\n".join(f"[Lecture {i}]\n{lec['text']}" for i, lec in enumerate(lectures, 1) if lec["text"].strip())
