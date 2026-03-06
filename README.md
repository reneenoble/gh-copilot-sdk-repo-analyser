# 🐛 GitHub Issue Complexity Analyser

An intelligent issue triage tool built with the **GitHub Copilot SDK** that analyses GitHub issues in context — fetching issue details, exploring repository structure, reading source code — and produces a structured complexity assessment recommending the appropriate developer skill level for the fix.

Available as both a **CLI tool** for quick terminal-based triage and a **web application** with a real-time streaming chat UI.

---

## Problem

Engineering managers and tech leads spend significant time manually triaging incoming GitHub issues: reading the description, exploring the relevant codebase, estimating complexity, and deciding who should work on it. This slows down sprint planning and can lead to mis-assignments — junior developers getting stuck on senior-level tasks, or senior developers spending time on simple fixes.

## Solution

This tool automates the triage process by using the GitHub Copilot SDK's agentic capabilities. A Copilot-powered agent:

1. **Fetches the issue** (title, body, labels, comments) via the GitHub API
2. **Explores the repository** — navigates directory structure, searches code, reads relevant files
3. **Assesses complexity** and recommends a skill level (Junior / Mid-level / Senior / Senior+)
4. **Provides actionable guidance** — suggested approach, files involved, mentorship notes, and prerequisite knowledge

The agent autonomously decides which tools to call and how deep to explore, mirroring how an experienced engineer would triage an issue.

---

## Features

| Feature | CLI | Web App |
|---|---|---|
| Issue analysis by URL or owner/repo/number | ✅ | ✅ |
| Real-time streaming output | ✅ (terminal) | ✅ (SSE chat UI) |
| Tool call visibility (which files/APIs are being queried) | ✅ | ✅ |
| Structured Markdown assessment | ✅ | ✅ (rendered) |
| REST API for integration | — | ✅ |
| Interactive chat-style interface | — | ✅ |

### Copilot SDK Concepts Demonstrated

- **`CopilotClient`** — session creation and lifecycle management
- **`@define_tool`** — custom tool definitions with Pydantic parameter schemas
- **Agentic tool calling** — Copilot autonomously invokes your Python functions to gather context
- **Streaming event handling** — real-time processing of `assistant.message`, `tool.execution_start`, `tool.execution_complete`, and `session.idle` events
- **Multi-turn tool loops** — the agent makes multiple rounds of tool calls before producing its final assessment

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      User Interface                     │
│                                                         │
│   ┌─────────────┐              ┌──────────────────┐     │
│   │  CLI Tool    │              │  Web App (HTML/  │     │
│   │  (terminal)  │              │  CSS/JS + SSE)   │     │
│   └──────┬───────┘              └────────┬─────────┘     │
│          │                               │               │
└──────────┼───────────────────────────────┼───────────────┘
           │                               │
           ▼                               ▼
┌─────────────────────────────────────────────────────────┐
│                    Python Backend                        │
│                                                         │
│   ┌──────────────────┐     ┌────────────────────────┐   │
│   │  issue_analyser   │     │  api.py (FastAPI)      │   │
│   │  .py (CLI entry)  │     │  - GET /               │   │
│   │                   │     │  - GET /analyse/stream  │   │
│   │                   │     │  - POST /analyse        │   │
│   │                   │     │  - POST /analyse/url    │   │
│   └────────┬─────────┘     └──────────┬─────────────┘   │
│            │                          │                  │
│            ▼                          ▼                  │
│   ┌────────────────────────────────────────────────┐    │
│   │           GitHub Copilot SDK                    │    │
│   │  CopilotClient → Session → Event Stream        │    │
│   │                                                 │    │
│   │  Custom Tools (@define_tool):                   │    │
│   │  ┌─────────────────┐  ┌──────────────────┐     │    │
│   │  │ get_github_issue │  │ get_repo_structure│     │    │
│   │  └─────────────────┘  └──────────────────┘     │    │
│   │  ┌──────────────────┐  ┌─────────────────┐     │    │
│   │  │search_code_in_   │  │ get_file_content │     │    │
│   │  │repo              │  │                  │     │    │
│   │  └──────────────────┘  └─────────────────┘     │    │
│   └────────────────────────┬───────────────────────┘    │
│                            │                             │
└────────────────────────────┼─────────────────────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │    GitHub REST API   │
                  │  (Issues, Contents,  │
                  │   Code Search)       │
                  └─────────────────────┘
```

---

## Prerequisites

- **Python 3.10+**
- **GitHub Copilot CLI** installed and authenticated ([quick guide](https://docs.github.com/en/copilot/github-copilot-in-the-cli))
- **GitHub Token** (optional but recommended) — set `GITHUB_TOKEN` or `GH_TOKEN` environment variable for higher API rate limits

---

## Setup & Installation

```bash
# Clone the repository
git clone https://github.com/<your-org>/gh-copilot-sdk-repo-analyser.git
cd gh-copilot-sdk-repo-analyser

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -e .

# (Optional) Set GitHub token for higher rate limits
export GITHUB_TOKEN=ghp_your_token_here
```

---

## Usage

### CLI

Analyse an issue directly from the terminal with streaming output:

```bash
# By GitHub issue URL
python src/issue_analyser.py https://github.com/microsoft/vscode/issues/12345

# By owner, repo, and issue number
python src/issue_analyser.py microsoft vscode 12345
```

The CLI streams the agent's reasoning and tool calls to the terminal in real time, then prints the full Markdown assessment.

### Web Application

Start the FastAPI server:

```bash
cd src && uvicorn api:app --reload
```

Open **http://127.0.0.1:8000** in your browser. The web app provides:

- **URL input** — paste any GitHub issue URL
- **Manual input** — enter owner, repo, and issue number separately
- **Real-time chat UI** — watch the agent think, see each tool call with details (which file it's reading, which path it's exploring), and receive the final rendered Markdown assessment

### REST API

The server also exposes JSON endpoints for programmatic integration:

```bash
# Stream analysis as Server-Sent Events
curl "http://localhost:8000/analyse/stream?owner=microsoft&repo=vscode&issue_number=12345"

# POST with JSON body
curl -X POST http://localhost:8000/analyse \
  -H "Content-Type: application/json" \
  -d '{"owner": "microsoft", "repo": "vscode", "issue_number": 12345}'

# POST with a GitHub URL
curl -X POST http://localhost:8000/analyse/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/microsoft/vscode/issues/12345"}'
```

---

## Deployment

The application is a standard Python FastAPI app and can be deployed to any platform that supports Python web apps:

```bash
# Run in production
cd src && uvicorn api:app --host 0.0.0.0 --port 8000
```

A `Dockerfile` can be added for containerised deployment to Azure Container Apps, Azure App Service, or any container platform.

---

## Project Structure

```
gh-copilot-sdk-repo-analyser/
├── src/
│   ├── issue_analyser.py  # Core logic: custom tools, system prompt, CLI entry point
│   ├── api.py             # FastAPI server: REST API + SSE streaming + web frontend
│   ├── hello_world.py     # Minimal Copilot SDK example (for reference)
│   └── static/
│       ├── index.html     # Web app HTML
│       ├── app.js         # Frontend JavaScript (SSE handling, chat UI)
│       └── styles.css     # UI styles
├── pyproject.toml         # Python project config and dependencies
├── AGENTS.md              # Custom agent instructions
├── mcp.json               # MCP server configuration
└── docs/
    ├── RAI.md             # Responsible AI notes
    ├── architecture.md    # Architecture diagram
    └── architecture.png   # Architecture diagram image
```

---

## Responsible AI Notes

See [docs/RAI.md](docs/RAI.md) for full details. Key points:

- **Not a replacement for human judgement** — the assessment is a starting point for triage discussions, not a definitive assignment.
- **Skill level labels are contextual** — "Junior" and "Senior" refer to familiarity with the specific codebase and technologies, not overall developer capability.
- **No personal data processing** — the tool only reads public GitHub issue data and repository content.
- **Full transparency** — every tool call is visible in the UI so users can see exactly what data the agent examined.

---

## License

MIT
