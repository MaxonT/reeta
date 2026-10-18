"""Source material: turn an upload into clean text, and combine a session's sources for the question writer.
To support another file type (e.g. PDF), add an extractor to _EXTRACTORS. Nothing else needs to change."""
from pathlib import Path

PASTED = "pasted notes"


class SourceError(ValueError):
    """An upload we refuse. `status` is the HTTP code the API should answer with."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _decode_text(data: bytes) -> str:
    for enc in ("utf-8-sig", "latin-1"):  # latin-1 accepts any byte, so this never fails
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise AssertionError("unreachable")


_EXTRACTORS = {".txt": _decode_text, ".md": _decode_text}


def extract_text(filename: str, data: bytes, max_chars: int) -> str:
    """Bytes of an uploaded file -> clean text. Raises SourceError if empty, too long, or an unsupported type."""
    ext = Path(filename or "").suffix.lower()
    extractor = _EXTRACTORS.get(ext)
    if extractor is None:
        raise SourceError(f"Unsupported file type {ext or '(none)'}. Upload: {', '.join(sorted(_EXTRACTORS))}")
    return clean_text(extractor(data), max_chars)


def clean_text(text: str, max_chars: int) -> str:
    """Normalise pasted or extracted text. Raises SourceError if empty or too long."""
    text = text.replace("\r\n", "\n").replace("\x00", "").strip()
    if not text:
        raise SourceError("That source is empty.")
    if len(text) > max_chars:
        raise SourceError(f"That source is too long ({len(text):,} characters, the limit is {max_chars:,}).", 413)
    return text


def combine_sources(sources: list[dict], max_chars: int) -> str | None:
    """A session's sources as one block of notes for the question writer, cut to max_chars.
    None if there are no sources, so the caller can fall back to the default notes."""
    parts = [f"## {s['filename']}\n{s['text']}" for s in sources]
    if not parts:
        return None
    return "\n\n".join(parts)[:max_chars]
