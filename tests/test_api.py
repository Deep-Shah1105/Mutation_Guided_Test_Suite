import pytest
pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("langgraph")
from fastapi.testclient import TestClient
from api.main import app
from api import main


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_generate_input_validation_rejects_empty_source():
    response = TestClient(app).post("/generate", json={"source_code": ""})
    assert response.status_code == 422
    
def test_generate_returns_trace_events_for_completed_run(monkeypatch):
    trace_events = [
        {
            "timestamp": "2026-10-22T00:00:00+00:00",
            "run_id": "trace-test-run",
            "agent": "supervisor",
            "event": "routing_decision",
            "payload": {"selected_action": "reporter"},
        }
    ]

    monkeypatch.setattr(
        main,
        "run_generation",
        lambda *args: {
            "run_id": "trace-test-run",
            "function_name": "sample",
            "generated_tests": "def test_sample():\n    assert True\n",
            "pytest_result": {"status": "passed", "passed": True},
            "mutation_result": {},
            "report": {},
            "trace_path": "trace.jsonl",
            "trace_events": trace_events,
        },
    )

    response = TestClient(main.app).post(
        "/generate",
        json={
            "source_code": "def sample():\n    return 1",
            "function_name": "sample",
        },
    )

    assert response.status_code == 200
    assert response.json()["trace_events"] == trace_events
