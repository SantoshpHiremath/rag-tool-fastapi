# RAG Tool Agent — FastAPI Wrapper

A second, independent service layer over the same RAG + tool-routing
agent as [rag-tool-agent-demo](https://github.com/SantoshpHiremath/rag-tool-agent-demo),
this time using **FastAPI** instead of Flask — built to get real, tested,
hands-on FastAPI experience on top of an LLM/agent project I had already
built and verified, closing a specific gap named by a job posting that
asked for "first experience with FastAPI/Streamlit or building small
services."

## Why this exists alongside rag-tool-api (the Flask version)

[`rag-tool-api`](https://github.com/SantoshpHiremath/rag-tool-api) already
wraps the same agent as a Flask service. Rather than pretend the Flask
version was FastAPI, or rewrite it in place and lose the honest record of
what was actually built when, this is a genuinely separate, independently
tested project that reuses the same `agent_runner.py` (the
`AgentRunner` dependency-injection interface with `RealAgentRunner` and
`StubAgentRunner`) and the same `schemas.py` Pydantic models — copied
across unchanged, exactly as `rag-tool-api`'s own README predicted:
*"This is the same validation layer FastAPI is built on, so the schema
module ports over unchanged if this is later moved from Flask to
FastAPI."* That prediction is now verified true, not just asserted.

## What's different from the Flask version

- **`app.py`** is FastAPI instead of Flask: `FastAPI()` app, async route
  handlers, `app.state.agent_runner` instead of `app.config["AGENT_RUNNER"]`.
- Same two endpoints, same status-code contract (200 / 400 / 502), same
  validation behavior — verified by a test suite that mirrors the Flask
  suite test-for-test (16 tests in each), so the two services can be
  honestly claimed as offering an equivalent, independently-verified
  contract, not just visually similar code.
- One real difference had to be handled explicitly: Flask's
  `request.get_json(silent=True)` returns `None` for a non-JSON body,
  but FastAPI/Starlette's `request.json()` *raises* on a non-JSON body
  instead of returning `None`. A naive port would have let that
  exception surface as an unhandled 500 instead of the intended 400.
  `_has_json_body()` in `app.py` handles this explicitly. This was
  caught and confirmed the way every bug in this portfolio is confirmed:
  the check was deliberately disabled (forced to always report "valid
  JSON"), which reproduced an unhandled `JSONDecodeError` instead of a
  clean 400, `test_ask_non_json_body_returns_400` failed as expected
  against the broken version, and the fix was restored and re-verified.

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

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running the tests

```bash
pytest tests/ -v
```

Runs fully offline with `AGENT_MODE=stub` (the default) — no Ollama
required. 16/16 tests passing, verified against a deliberately
re-introduced bug (see above) as well as the happy path.

## Running the real server

```bash
AGENT_MODE=stub uvicorn app:app --host 0.0.0.0 --port 8010
```

Verified with a real running `uvicorn` process (not just FastAPI's
`TestClient`), hit with real `curl` requests:

```bash
curl http://localhost:8010/health
# {"status":"ok"}

curl -X POST http://localhost:8010/ask -H "Content-Type: application/json" \
  -d '{"question": "Compute 12 + 30"}'
# {"question":"Compute 12 + 30","answer":"[calculator] Evaluated expression in: Compute 12 + 30"}
```

With `AGENT_MODE=real` and the `rag-tool-agent-demo` project on
`PYTHONPATH`, plus Ollama running locally with `llama3.2` and
`nomic-embed-text` pulled, this calls the actual LangChain agent instead
of the deterministic stub — same as `rag-tool-api`.

## Relationship to the other projects

This repo does not duplicate the agent logic — `agent_runner.py` (copied
from `rag-tool-api`) imports and calls `run_agent()` from
[rag-tool-agent-demo](https://github.com/SantoshpHiremath/rag-tool-agent-demo)
when `AGENT_MODE=real`. That project remains the source of truth for the
actual RAG pipeline (FAISS vector index, Ollama embeddings, LCEL
retrieval chain, calculator tool, and the LLM's tool-routing decision
logic). This repo, like `rag-tool-api`, is purely a service layer on top
of it — this one demonstrating FastAPI specifically.
