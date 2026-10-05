# RAG Tool Agent — FastAPI Wrapper

A second, independent service layer over the same RAG + tool-routing
agent as [rag-tool-agent-demo](https://github.com/SantoshpHiremath/rag-tool-agent-demo),
this time using **FastAPI** instead of Flask. I built it to get hands-on,
tested FastAPI experience on top of an LLM/agent project I had already
built and verified.

## What it does

[`rag-tool-api`](https://github.com/SantoshpHiremath/rag-tool-api) already
wraps the same agent as a Flask service. This is a separate, independently
tested project that reuses the same `agent_runner.py` (the `AgentRunner`
dependency-injection interface with `RealAgentRunner` and
`StubAgentRunner`) and the same `schemas.py` Pydantic models, copied
across unchanged, exactly as `rag-tool-api`'s own README predicted:
*"This is the same validation layer FastAPI is built on, so the schema
module ports over unchanged if this is later moved from Flask to
FastAPI."* The port confirmed that prediction.

## Differences from the Flask version

- **`app.py`** is FastAPI instead of Flask: `FastAPI()` app, async route
  handlers, `app.state.agent_runner` instead of `app.config["AGENT_RUNNER"]`.
- Same two endpoints, same status-code contract (200 / 400 / 502), same
  validation behavior, verified by a test suite that mirrors the Flask
  suite test-for-test (16 tests in each), so the two services offer an
  equivalent, independently-verified contract.
- One difference needed explicit handling: Flask's
  `request.get_json(silent=True)` returns `None` for a non-JSON body,
  but FastAPI/Starlette's `request.json()` *raises* on a non-JSON body
  instead of returning `None`. A direct port would let that exception
  surface as an unhandled 500 instead of the intended 400.
  `_has_json_body()` in `app.py` handles this explicitly. I confirmed the
  check works by deliberately disabling it (forcing it to always report
  "valid JSON"), which reproduced an unhandled `JSONDecodeError` instead of
  a clean 400 and made `test_ask_non_json_body_returns_400` fail as
  expected; I then restored the fix and re-verified.

## Endpoints (identical contract to rag-tool-api)

```
GET  /health
     -> 200 {"status": "ok"}

POST /ask
     body: {"question": "What is the FordA dataset used for?"}
     -> 200 {"question": "...", "answer": "..."}
     -> 400 {"error": "..."}   if the question is missing/blank/too long/not JSON
     -> 502 {"error": "..."}   if the underlying agent fails (e.g. Ollama down)
```

## Running it

Setup:

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Tests:

```bash
pytest tests/ -v
```

The tests run fully offline with `AGENT_MODE=stub` (the default), so Ollama
is not required. 16/16 tests pass, including against the deliberately
re-introduced bug described above.

Real server:

```bash
AGENT_MODE=stub uvicorn app:app --host 0.0.0.0 --port 8010
```

I verified this with a real running `uvicorn` process (not just FastAPI's
`TestClient`), hit with real `curl` requests:

```bash
curl http://localhost:8010/health
# {"status":"ok"}

curl -X POST http://localhost:8010/ask -H "Content-Type: application/json" \
  -d '{"question": "Compute 12 + 30"}'
# {"question":"Compute 12 + 30","answer":"[calculator] Evaluated expression in: Compute 12 + 30"}
```

## Notes

With `AGENT_MODE=real` and the `rag-tool-agent-demo` project on
`PYTHONPATH`, plus Ollama running locally with `llama3.2` and
`nomic-embed-text` pulled, the service calls the actual LangChain agent
instead of the deterministic stub, the same as `rag-tool-api`.

This repo does not duplicate the agent logic. `agent_runner.py` (copied
from `rag-tool-api`) imports and calls `run_agent()` from
[rag-tool-agent-demo](https://github.com/SantoshpHiremath/rag-tool-agent-demo)
when `AGENT_MODE=real`. That project remains the source of truth for the
RAG pipeline (FAISS vector index, Ollama embeddings, LCEL retrieval chain,
calculator tool, and the LLM's tool-routing decision logic). Like
`rag-tool-api`, this repo is a service layer on top of it, here built with
FastAPI.
