# GitHub Issue Complexity Analyser

A demo showing how the GitHub Copilot SDK can streamline dev workflows by automatically assessing GitHub issue complexity and recommending the appropriate skill level for the fix.

## What it does

Analyses a GitHub issue and recommends whether it should be assigned to:
- **Junior** – Simple, isolated changes
- **Mid-level** – Multiple components, moderate complexity  
- **Senior** – Systems knowledge, architecture decisions
- **Senior+** – Cross-cutting concerns, security, deep domain expertise

## Features

- Uses **Copilot SDK custom tools** (`@define_tool`) to let Copilot fetch GitHub data
- Explores repository structure and relevant code
- Provides reasoning, suggested approach, and mentorship notes

## Usage

```bash
# Install dependencies
pip install -e .

# Analyse an issue by URL
python issue_analyser.py https://github.com/microsoft/vscode/issues/12345

# Or by owner/repo/number
python issue_analyser.py microsoft vscode 12345
```

Set `GITHUB_TOKEN` environment variable for higher API rate limits.

## SDK Concepts Demonstrated

- `CopilotClient` and session management
- `@define_tool` decorator for custom tools with Pydantic schemas
- Streaming event handling
- Tool calling (Copilot invokes your Python functions)
