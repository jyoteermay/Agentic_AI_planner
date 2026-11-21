from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from agent.agentic_workflow import GraphBuilder
from utils.save_to_document import save_document
from starlette.responses import JSONResponse
import os
import time
import datetime
from dotenv import load_dotenv
from pydantic import BaseModel
from logger.logging import get_logger, new_request_id
load_dotenv()

logger = get_logger(__name__)

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "gemini")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # set specific origins in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Build the LLM, tools and graph once at startup instead of on every request.
logger.info("Starting AI Trip Planner API with provider=%s", MODEL_PROVIDER)
react_app = GraphBuilder(model_provider=MODEL_PROVIDER)()
logger.info("Agent graph compiled and ready")

# Drawing the graph calls the remote mermaid.ink service, so only do it on demand:
#   SAVE_GRAPH_PNG=1 uvicorn main:app --reload --port 8000
if os.getenv("SAVE_GRAPH_PNG") == "1":
    try:
        with open("my_graph.png", "wb") as f:
            f.write(react_app.get_graph().draw_mermaid_png())
        logger.info("Graph saved as 'my_graph.png' in %s", os.getcwd())
    except Exception as e:
        logger.warning("Could not save graph image: %s", e)


class QueryRequest(BaseModel):
    question: str


def _message_text(content) -> str:
    """Gemini returns a list of content blocks; join the text parts into one string."""
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


@app.get("/")
async def root():
    return {"status": "running", "provider": MODEL_PROVIDER, "docs": "/docs"}


@app.post("/query")
async def query_travel_agent(query: QueryRequest):
    request_id = new_request_id()
    start = time.perf_counter()
    logger.info("New query: %r", query.question)
    try:
        messages = {"messages": [query.question]}
        # invoke() is blocking; run it in a thread so the server stays responsive
        output = await run_in_threadpool(react_app.invoke, messages)

        if isinstance(output, dict) and "messages" in output:
            final_output = _message_text(output["messages"][-1].content)  # Last AI response
        else:
            final_output = str(output)

        llm_calls = sum(1 for m in output.get("messages", []) if getattr(m, "type", "") == "ai") if isinstance(output, dict) else 0
        logger.info(
            "Query answered in %.2fs (%d LLM calls, %d chars)",
            time.perf_counter() - start, llm_calls, len(final_output),
        )
        return {"answer": final_output}
    except Exception as e:
        logger.exception("Query failed after %.2fs: %s", time.perf_counter() - start, e)
        return JSONResponse(status_code=500, content={"error": str(e), "request_id": request_id})
