import os
import subprocess
import sys
import textwrap
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

# app.main builds the real service at import, so run it in a process with the offline providers.
SCRIPT = textwrap.dedent("""
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    for method, path in [("get", "/report"), ("get", "/notebook"), ("get", "/office-hours"),
                         ("post", "/exam/take"), ("post", "/lectures/1/confirm")]:
        r = getattr(c, method)(path, **({"json": {}} if path.endswith("confirm") else {}))
        print(path, r.status_code, r.json()["detail"])
""")


def test_notebook_endpoints_answer_410_instead_of_crashing():
    env = {**os.environ, "DB_PROVIDER": "sqlite", "SQLITE_PATH": ":memory:", "LLM_PROVIDER": "mock",
           "SPEECH_PROVIDER": "browser", "ORACLE_USER": "", "ORACLE_PASSWORD": ""}
    out = subprocess.run([sys.executable, "-c", SCRIPT], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-800:]
    lines = out.stdout.strip().splitlines()
    assert len(lines) == 5 and all(" 410 " in line and "no longer supported" in line for line in lines), out.stdout
