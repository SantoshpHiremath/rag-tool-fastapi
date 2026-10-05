"""
tests/test_api.py
------------------

Tests the FastAPI service through its actual HTTP interface (FastAPI's
TestClient, built on httpx), not by calling internal functions directly
-- verifying what a real client would see: status codes, JSON shape, and
error handling. Uses AGENT_MODE=stub (StubAgentRunner) so the suite runs
fully offline with no Ollama dependency. Mirrors the equivalent Flask
suite in rag-tool-api/tests/test_api.py test-for-test, so the two
services offer the same verified contract.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_runner import StubAgentRunner
from app import create_app


@pytest.fixture
def client():
    app = create_app(agent_runner=StubAgentRunner())
    return TestClient(app)


class TestHealth:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_status_ok(self, client):
        resp = client.get("/health")
        assert resp.json() == {"status": "ok"}


class TestAskHappyPath:
    def test_ask_returns_200(self, client):
        resp = client.post("/ask", json={"question": "What is the FordA dataset used for?"})
        assert resp.status_code == 200

    def test_ask_returns_question_and_answer(self, client):
        resp = client.post("/ask", json={"question": "What is the FordA dataset used for?"})
        body = resp.json()
        assert body["question"] == "What is the FordA dataset used for?"
        assert "answer" in body
        assert isinstance(body["answer"], str)
        assert len(body["answer"]) > 0

    def test_ask_routes_dataset_question_to_search_notes(self, client):
        resp = client.post("/ask", json={"question": "What preprocessing is applied to the FordA dataset?"})
        body = resp.json()
        assert "[search_notes]" in body["answer"]

    def test_ask_routes_arithmetic_question_to_calculator(self, client):
        resp = client.post("/ask", json={"question": "Compute 1320 / (3601 + 1320)"})
        body = resp.json()
        assert "[calculator]" in body["answer"]

    def test_ask_routes_general_question_directly(self, client):
        resp = client.post("/ask", json={"question": "What is the capital of France?"})
        body = resp.json()
        assert "[direct]" in body["answer"]

    def test_ask_strips_whitespace_from_question(self, client):
        resp = client.post("/ask", json={"question": "  What is the capital of France?  "})
        body = resp.json()
        assert body["question"] == "What is the capital of France?"


class TestAskValidation:
    def test_ask_missing_question_field_returns_400(self, client):
        resp = client.post("/ask", json={})
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_ask_blank_question_returns_400(self, client):
        resp = client.post("/ask", json={"question": "   "})
        assert resp.status_code == 400

    def test_ask_empty_string_question_returns_400(self, client):
        resp = client.post("/ask", json={"question": ""})
        assert resp.status_code == 400

    def test_ask_non_json_body_returns_400(self, client):
        resp = client.post("/ask", content=b"not json", headers={"content-type": "text/plain"})
        assert resp.status_code == 400

    def test_ask_question_too_long_returns_400(self, client):
        resp = client.post("/ask", json={"question": "x" * 2001})
        assert resp.status_code == 400

    def test_ask_wrong_type_for_question_returns_400(self, client):
        resp = client.post("/ask", json={"question": 12345})
        assert resp.status_code == 400


class TestAskAgentFailure:
    def test_ask_returns_502_when_agent_raises(self, client):
        class FailingRunner:
            def run(self, question: str) -> str:
                raise RuntimeError("Ollama connection refused")

        client.app.state.agent_runner = FailingRunner()
        resp = client.post("/ask", json={"question": "Any question"})
        assert resp.status_code == 502
        assert "error" in resp.json()


class TestNotFound:
    def test_unknown_route_returns_404(self, client):
        resp = client.get("/nonexistent")
        assert resp.status_code == 404
