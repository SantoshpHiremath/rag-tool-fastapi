"""
app.py
------

FastAPI service wrapping the same RAG + tool-routing agent as
rag-tool-api (github.com/SantoshpHiremath/rag-tool-api), which wraps it
in Flask. This is a second, independent service layer over the exact
same agent — same AgentRunner interface, same Pydantic request/response
schemas (schemas.py is copied unchanged from rag-tool-api, exactly as
that project's own README predicted: "This is the same validation layer
FastAPI is built on, so the schema module ports over unchanged if this
is later moved from Flask to FastAPI").

Endpoints (identical contract to the Flask version):

  GET  /health        -> liveness check
  POST /ask            -> {"question": "..."} -> {"question": "...", "answer": "..."}

Which agent backend is used is controlled by the AGENT_MODE env var:
  AGENT_MODE=stub  (default) -> StubAgentRunner, no external dependencies,
                                  used for tests and local dev without Ollama.
  AGENT_MODE=real            -> RealAgentRunner, calls the actual LangChain
                                  agent. Requires Ollama running locally with
                                  llama3.2 + nomic-embed-text pulled, and the
                                  rag-tool-agent-demo project on PYTHONPATH.
"""

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from agent_runner import RealAgentRunner, StubAgentRunner
from schemas import AskRequest, AskResponse


def create_app(agent_runner=None) -> FastAPI:
    app = FastAPI(title="RAG Tool Agent API (FastAPI)")

    if agent_runner is None:
        mode = os.environ.get("AGENT_MODE", "stub")
        agent_runner = RealAgentRunner() if mode == "real" else StubAgentRunner()

    app.state.agent_runner = agent_runner

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/ask")
    async def ask(request: Request):
        payload = await request.json() if await _has_json_body(request) else None
        if payload is None or not isinstance(payload, dict):
            return JSONResponse(status_code=400, content={"error": "Request body must be valid JSON."})

        try:
            req = AskRequest(**payload)
        except ValidationError as exc:
            return JSONResponse(status_code=400, content={"error": exc.errors()[0]["msg"]})

        runner = app.state.agent_runner
        try:
            answer = runner.run(req.question)
        except Exception as exc:  # agent/runtime failure, not a client error
            return JSONResponse(status_code=502, content={"error": f"Agent failed to answer: {exc}"})

        response = AskResponse(question=req.question, answer=answer)
        return response.model_dump()

    return app


async def _has_json_body(request: Request) -> bool:
    """FastAPI/Starlette raises on request.json() for a non-JSON body
    rather than returning None (Flask's request.get_json(silent=True)
    behavior) -- this normalizes that so /ask can return a clean 400
    instead of an unhandled 500 for a malformed body."""
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        return False
    try:
        await request.json()
        return True
    except Exception:
        return False


app = create_app()
