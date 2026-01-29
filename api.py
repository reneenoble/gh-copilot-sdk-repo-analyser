"""
FastAPI wrapper for the GitHub Issue Complexity Analyser.

Provides a REST API to analyse GitHub issues and get formatted results.

Run with: uvicorn api:app --reload
"""

import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from copilot import CopilotClient
from issue_analyser import (
    get_github_issue,
    get_repo_structure,
    search_code_in_repo,
    get_file_content,
    parse_github_url,
    SYSTEM_INSTRUCTIONS,
)

app = FastAPI(
    title="GitHub Issue Complexity Analyser",
    description="Analyse GitHub issues to determine appropriate developer skill level",
    version="1.0.0",
)

# Serve static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class AnalyseRequest(BaseModel):
    """Request body for issue analysis."""
    owner: str = Field(description="Repository owner (e.g., 'microsoft')")
    repo: str = Field(description="Repository name (e.g., 'vscode')")
    issue_number: int = Field(description="Issue number to analyse")


class AnalyseURLRequest(BaseModel):
    """Request body for issue analysis via URL."""
    url: str = Field(description="Full GitHub issue URL")


class AnalysisResult(BaseModel):
    """Response model for analysis results."""
    owner: str
    repo: str
    issue_number: int
    analysis: str


async def stream_analysis(owner: str, repo: str, issue_number: int):
    """Stream the complexity analysis as SSE events."""
    client = CopilotClient()
    await client.start()

    session = await client.create_session({
        "model": "gpt-5",
        "tools": [
            get_github_issue,
            get_repo_structure,
            search_code_in_repo,
            get_file_content,
        ],
        "instructions": SYSTEM_INSTRUCTIONS,
    })

    queue = asyncio.Queue()
    tool_calls = []
    message_count = 0
    idle_count = 0

    def on_event(event):
        nonlocal message_count, idle_count
        event_name = event.type.value if hasattr(event.type, 'value') else str(event.type)
        
        if event_name == "assistant.message":
            message_count += 1
            queue.put_nowait(("message", event.data.content))
        elif event_name == "tool.call":
            tool_calls.append(event.data.name)
            queue.put_nowait(("tool_call", event.data.name))
        elif event_name == "session.idle":
            idle_count += 1
            # Only finish if: no tools called, OR this is 2nd+ idle (after tools completed)
            if not tool_calls or idle_count > 1:
                queue.put_nowait(("done", list(tool_calls)))

    session.on(on_event)

    prompt = f"Please analyze GitHub issue #{issue_number} in the repository {owner}/{repo}. First fetch the issue details, then explore the codebase, and provide your complexity assessment."

    await session.send({"prompt": prompt})

    # Yield SSE events from the queue
    while True:
        event_type, data = await queue.get()
        if event_type == "message":
            yield f"event: message\ndata: {json.dumps({'content': data})}\n\n"
        elif event_type == "tool_call":
            yield f"event: tool_call\ndata: {json.dumps({'name': data})}\n\n"
        elif event_type == "done":
            yield f"event: done\ndata: {json.dumps({'tools_used': data})}\n\n"
            break

    await session.destroy()
    await client.stop()


async def run_analysis(owner: str, repo: str, issue_number: int) -> str:
    """Run the complexity analysis and return the full response."""
    client = CopilotClient()
    await client.start()

    session = await client.create_session({
        "model": "gpt-5",
        "tools": [
            get_github_issue,
            get_repo_structure,
            search_code_in_repo,
            get_file_content,
        ],
        "instructions": SYSTEM_INSTRUCTIONS,
    })

    done = asyncio.Event()
    response_parts = []
    tool_calls = []

    def on_event(event):
        if event.type.value == "assistant.message":
            response_parts.append(event.data.content)
        elif event.type.value == "tool.call":
            tool_calls.append(event.data.name)
        elif event.type.value == "session.idle":
            done.set()

    session.on(on_event)

    prompt = f"Please analyze GitHub issue #{issue_number} in the repository {owner}/{repo}. First fetch the issue details, then explore the codebase, and provide your complexity assessment."

    await session.send({"prompt": prompt})
    await done.wait()

    await session.destroy()
    await client.stop()

    full_response = "".join(response_parts)

    if tool_calls:
        tools_used = "\n\n---\n*Tools used: " + ", ".join(tool_calls) + "*"
        full_response += tools_used

    return full_response


@app.get("/")
async def root():
    """Serve the web frontend."""
    return FileResponse(static_dir / "index.html")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/analyse/stream")
async def analyse_stream(owner: str, repo: str, issue_number: int):
    """Stream analysis results as Server-Sent Events."""
    return StreamingResponse(
        stream_analysis(owner, repo, issue_number),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.post("/analyse", response_model=AnalysisResult)
async def analyse_issue(request: AnalyseRequest):
    """Analyse a GitHub issue's complexity."""
    try:
        analysis = await run_analysis(
            request.owner, request.repo, request.issue_number
        )
        return AnalysisResult(
            owner=request.owner,
            repo=request.repo,
            issue_number=request.issue_number,
            analysis=analysis,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyse/url", response_model=AnalysisResult)
async def analyse_issue_by_url(request: AnalyseURLRequest):
    """Analyse a GitHub issue by its URL."""
    try:
        owner, repo, issue_number = parse_github_url(request.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        analysis = await run_analysis(owner, repo, issue_number)
        return AnalysisResult(
            owner=owner,
            repo=repo,
            issue_number=issue_number,
            analysis=analysis,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
