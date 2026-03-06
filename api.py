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


ANALYSIS_PROMPT = """Please analyse GitHub issue #{issue_number} in the repository {owner}/{repo}.

Always use Autralian English spelling. 

First fetch the issue details, then explore the codebase, and provide your complexity assessment - this means is it a simple bug fix, a moderate feature addition, or a complex architectural change. Is it somethinga junior, mid-level, senior, or senior+ developer should handle? 

Format your response with clear sections, using language that is suitable for the intended skill level.:
## Issue Summary
## Complexity Assessment
- **Recommended Skill Level**: Junior / Mid-level / Senior / Senior+
- **Confidence**: High / Medium / Low
## Reasoning
## Files Likely Involved
## Suggested Approach
## Mentorship Notes (if applicable)
## What you need to know before you start
 - Skills a dev that is too junior can learn to be able to complete this task (make it really approachable)
"""

async def stream_analysis(owner: str, repo: str, issue_number: int):
    """Stream the analysis results as Server-Sent Events."""
    
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
    expecting_tools = False
    got_final_response = False
    # Map tool_call_id -> args from assistant.turn_end tool_requests
    pending_tool_args = {}

    def _parse_tool_args(raw_args):
        """Parse tool arguments from various formats."""
        if raw_args is None:
            return {}
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            try:
                return json.loads(raw_args)
            except (json.JSONDecodeError, TypeError):
                return {}
        # Handle Pydantic models or dataclass-like objects
        if hasattr(raw_args, 'model_dump'):
            return raw_args.model_dump()
        if hasattr(raw_args, '__dict__'):
            return {k: v for k, v in vars(raw_args).items() if not k.startswith('_')}
        return {}

    def on_event(event):
        nonlocal expecting_tools, got_final_response
        event_name = event.type.value if hasattr(event.type, 'value') else str(event.type)
        
        if event_name == "assistant.message":
            content = getattr(event.data, 'content', None)
            # Only queue if there's actual content
            if content and content.strip():
                queue.put_nowait(("message", content))
                
                if any(word in content.lower() for word in ['plan:', 'proceeding', 'will fetch', 'let me', 'i\'ll']):
                    expecting_tools = True
                
                if tool_calls and not expecting_tools:
                    got_final_response = True
        
        elif event_name == "assistant.turn_end":
            # Capture tool_requests with their arguments before execution starts
            tool_requests = getattr(event.data, 'tool_requests', None)
            if tool_requests:
                expecting_tools = True
                for tr in tool_requests:
                    tr_name = getattr(tr, 'name', None)
                    tr_id = getattr(tr, 'tool_call_id', None)
                    tr_args = _parse_tool_args(getattr(tr, 'arguments', None))
                    if tr_id:
                        pending_tool_args[tr_id] = {"name": tr_name, "args": tr_args}
                
        elif event_name in ("tool.call", "tool.execution_start"):
            tool_name = getattr(event.data, 'name', None) or getattr(event.data, 'tool_name', None)
            if tool_name:
                tool_calls.append(tool_name)
                # Try to get args: first from pending_tool_args, then from event itself
                tool_call_id = getattr(event.data, 'tool_call_id', None)
                tool_args = {}
                if tool_call_id and tool_call_id in pending_tool_args:
                    tool_args = pending_tool_args.pop(tool_call_id).get("args", {})
                else:
                    tool_args = _parse_tool_args(getattr(event.data, 'arguments', None))
                queue.put_nowait(("tool_call", {"name": tool_name, "args": tool_args}))
                expecting_tools = False
            
        elif event_name == "tool.execution_complete":
            expecting_tools = False
            
        elif event_name == "session.idle":
            if not expecting_tools and (got_final_response or not tool_calls):
                queue.put_nowait(("done", tool_calls))

    session.on(on_event)

    prompt = ANALYSIS_PROMPT.format(issue_number=issue_number, owner=owner, repo=repo)

    await session.send({"prompt": prompt})

    # Yield SSE events from the queue
    while True:
        event_type, data = await queue.get()
        if event_type == "message":
            yield f"event: message\ndata: {json.dumps({'content': data})}\n\n"
        elif event_type == "tool_call":
            yield f"event: tool_call\ndata: {json.dumps(data)}\n\n"
        elif event_type == "done":
            yield f"event: done\ndata: {json.dumps({'tools_used': data})}\n\n"
            break

    await session.destroy()
    await client.stop()


# async def stream_analysis(owner: str, repo: str, issue_number: int):
#     """Stream the complexity analysis as SSE events."""
#     client = CopilotClient()
#     await client.start()

#     session = await client.create_session({
#         "model": "gpt-5",
#         "tools": [
#             get_github_issue,
#             get_repo_structure,
#             search_code_in_repo,
#             get_file_content,
#         ],
#         "instructions": SYSTEM_INSTRUCTIONS,
#     })

#     queue = asyncio.Queue()
#     tool_calls = []
#     expecting_tools = False
#     got_final_response = False

#     def on_event(event):
#         nonlocal expecting_tools, got_final_response
#         event_name = event.type.value if hasattr(event.type, 'value') else str(event.type)
        
#         if event_name == "assistant.message":
#             content = event.data.content
#             queue.put_nowait(("message", content))
            
#             # Check if this message indicates tools are coming
#             if any(word in content.lower() for word in ['plan:', 'proceeding', 'will fetch', 'let me', 'i\'ll']):
#                 expecting_tools = True
            
#             # If we already ran tools, this is the final response
#             if tool_calls and not expecting_tools:
#                 got_final_response = True
                
#         elif event_name in ("tool.call", "tool.execution_start"):
#             tool_name = getattr(event.data, 'name', None) or getattr(event.data, 'tool_name', 'unknown')
#             tool_calls.append(tool_name)
#             queue.put_nowait(("tool_call", tool_name))
#             expecting_tools = False  # Tools are now running
            
#         elif event_name == "tool.execution_complete":
#             expecting_tools = False  # Tool finished, expect more content or idle
            
#         elif event_name == "session.idle":
#             # Only finish if: no tools expected AND (got final response OR no tools involved)
#             if not expecting_tools and (got_final_response or not tool_calls):
#                 queue.put_nowait(("done", list(tool_calls)))

#     session.on(on_event)

    # prompt = ANALYSIS_PROMPT.format(issue_number=issue_number, owner=owner, repo=repo)

    # await session.send({"prompt": prompt})

    # # Yield SSE events from the queue
    # while True:
    #     event_type, data = await queue.get()
    #     if event_type == "message":
    #         yield f"event: message\ndata: {json.dumps({'content': data})}\n\n"
    #     elif event_type == "tool_call":
    #         yield f"event: tool_call\ndata: {json.dumps({'name': data})}\n\n"
    #     elif event_type == "done":
    #         yield f"event: done\ndata: {json.dumps({'tools_used': data})}\n\n"
    #         break

    # await session.destroy()
    # await client.stop()


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
    expecting_tools = False
    got_final_response = False

    def on_event(event):
        nonlocal expecting_tools, got_final_response
        event_name = event.type.value if hasattr(event.type, 'value') else str(event.type)
        
        if event_name == "assistant.message":
            content = event.data.content
            response_parts.append(content)
            
            if any(word in content.lower() for word in ['plan:', 'proceeding', 'will fetch', 'let me', 'i\'ll']):
                expecting_tools = True
            
            if tool_calls and not expecting_tools:
                got_final_response = True
                
        elif event_name in ("tool.call", "tool.execution_start"):
            tool_name = getattr(event.data, 'name', None) or getattr(event.data, 'tool_name', 'unknown')
            tool_calls.append(tool_name)
            expecting_tools = False
            
        elif event_name == "tool.execution_complete":
            expecting_tools = False
            
        elif event_name == "session.idle":
            if not expecting_tools and (got_final_response or not tool_calls):
                done.set()

    session.on(on_event)

    prompt = ANALYSIS_PROMPT.format(issue_number=issue_number, owner=owner, repo=repo)

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
