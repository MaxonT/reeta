"""Turn timed transcript segments into sentences with start_ms / end_ms.

Segments (e.g. Whisper's) do not line up with sentences, so we interpolate a
time for every character of the joined text and cut on sentence punctuation.
"""
import re

_SENTENCE_END = re.compile(r"[^.!?]+(?:[.!?]+|$)")


def segments_to_sentences(segments: list[dict]) -> list[dict]:
    """segments: [{text, start_ms, end_ms}] -> [{idx, text, start_ms, end_ms}]"""
    text = ""
    char_ms: list[int] = []
    for seg in segments:
        seg_text = seg["text"].strip()
        if not seg_text:
            continue
        if text:
            text += " "
            char_ms.append(int(seg["start_ms"]))
        n = len(seg_text)
        span = max(int(seg["end_ms"]) - int(seg["start_ms"]), 0)
        for i in range(n):
            char_ms.append(int(seg["start_ms"]) + span * i // max(n, 1))
        text += seg_text
        # make sure the segment's last char maps to its end
        char_ms[-1] = int(seg["end_ms"])

    out = []
    for m in _SENTENCE_END.finditer(text):
        raw = m.group(0)
        stripped = raw.strip()
        if not re.search(r"\w", stripped):
            continue
        start = m.start() + (len(raw) - len(raw.lstrip()))
        end = m.start() + len(raw.rstrip()) - 1
        out.append({
            "idx": len(out),
            "text": stripped,
            "start_ms": char_ms[start],
            "end_ms": char_ms[end],
        })
    return out


def text_to_sentences(text: str) -> list[dict]:
    """Typed Lecture without audio: sentences with zero timestamps."""
    parts = [m.group(0).strip() for m in _SENTENCE_END.finditer(text)]
    parts = [s for s in parts if re.search(r"\w", s)]
    return [{"idx": i, "text": s, "start_ms": 0, "end_ms": 0} for i, s in enumerate(parts)]
