"""Oracle Autonomous Database repository via python-oracledb (thin mode, wallet / mTLS)."""
import json
from datetime import datetime
from pathlib import Path

import oracledb

from ..config import _path, settings
from .base import Repository

oracledb.defaults.fetch_lobs = False  # CLOBs come back as plain str

_SCHEMA = (Path(__file__).parent / "oracle_schema.sql").read_text()
_LECTURE_FIELDS = {"audio_path", "text", "words"}
# Oracle stores '' as NULL, so empty text is written as a single space and mapped back on read.
_EMPTY = " "
_TEXT_COLS = ("text", "prompt", "reference_answer")


def _clean(row: dict) -> dict:
    for k, v in row.items():
        if isinstance(v, datetime):
            row[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(v, float) and v.is_integer():
            row[k] = int(v)
    for k in _TEXT_COLS:
        if k in row and (row[k] is None or row[k] == _EMPTY):
            row[k] = ""
    return row


class OracleRepository(Repository):
    seed_content = create_lecture = update_lecture = get_lecture = list_lectures = _todo
    add_source = list_sources = delete_source = _todo
    list_questions = create_attempt = set_attempt_score = add_answers = list_attempts = reset_session = _todo
