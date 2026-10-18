"""Word timings for transcripts that did not come from Whisper word timestamps."""


def sentences_to_words(sentences: list[dict]) -> list[dict]:
    """[{text, start_ms, end_ms}] -> [{w, start_ms, end_ms}], each sentence's span split evenly across its words."""
    out = []
    for s in sentences:
        tokens = str(s.get("text", "")).split()
        if not tokens:
            continue
        start, end = int(s.get("start_ms") or 0), int(s.get("end_ms") or 0)
        step = max(end - start, 0) / len(tokens)
        for i, w in enumerate(tokens):
            out.append({"w": w, "start_ms": round(start + step * i), "end_ms": round(start + step * (i + 1))})
    return out
