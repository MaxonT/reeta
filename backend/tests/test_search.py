"""Notebook search and concept edges (the knowledge graph)."""
from fastapi.testclient import TestClient

from .conftest import teach

EDGES = [("self_call", "base_case"), ("base_case", "smaller_problem"), ("self_call", "independent_frames"),
         ("independent_frames", "return_propagation"), ("smaller_problem", "return_propagation")]


def test_edges_seeded_from_answer_key(svc, key):
    assert key.edges == EDGES
    assert svc.repo.list_edges() == EDGES


def test_empty_query_returns_all_and_neighbors(svc):
    teach(svc, "Every recursive function needs a base case.")
    res = svc.search_notebook("s1")
    assert [r["concept_id"] for r in res] == ["base_case"]
    r = res[0]
    assert r["confirmed"] is True and r["status"] == "correct" and r["text"].startswith("Every recursive")
    assert {"sentence_id", "start_ms", "end_ms", "label", "misconception_id"} <= set(r)
    assert r["neighbors"] == [{"concept_id": "self_call", "status": "missing"},
                              {"concept_id": "smaller_problem", "status": "missing"}]


def test_query_and_concept_filter(svc):
    teach(svc, "Every recursive function needs a base case. Each call should work on a smaller problem.")
    assert {r["concept_id"] for r in svc.search_notebook("s1", "SMALLER")} == {"smaller_problem"}
    assert {r["concept_id"] for r in svc.search_notebook("s1", "base_case")} == {"base_case"}
    assert svc.search_notebook("s1", "zzz") == []
    res = svc.search_notebook("s1", "", "base_case")
    assert [r["concept_id"] for r in res] == ["base_case"]
    assert {"concept_id": "smaller_problem", "status": "correct"} in res[0]["neighbors"]
    assert svc.search_notebook("s2") == []


def test_superseded_excluded(svc):
    teach(svc, "Honestly you don't need a base case.")
    teach(svc, "Every recursive function needs a base case.", kind="office_hours")
    res = svc.search_notebook("s1", "base")
    assert len(res) == 1 and res[0]["status"] == "correct" and "needs a base case" in res[0]["text"]


def test_http_endpoints(svc, monkeypatch):
    import app.repo.base
    import app.speech.base
    monkeypatch.setattr(app.speech.base, "get_speech_client", lambda _p: svc.speech)
    monkeypatch.setattr(app.repo.base, "get_repository", lambda _p: svc.repo)
    from app import main
    monkeypatch.setattr(main, "svc", svc)
    client = TestClient(main.app)
    assert client.get("/concepts/edges").json()["edges"] == [list(e) for e in EDGES]
    teach(svc, "Every recursive function needs a base case.", session="h1")
    body = client.get("/notebook/search", params={"q": "base"}, headers={"X-Session-Id": "h1"}).json()
    assert [r["concept_id"] for r in body["results"]] == ["base_case"]
    assert client.get("/notebook/search", headers={"X-Session-Id": "other"}).json()["results"] == []
