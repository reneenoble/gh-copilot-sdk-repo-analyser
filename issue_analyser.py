"""
GitHub Issue Complexity Analyzer

Uses the GitHub Copilot SDK to analyze GitHub issues and assess 
the difficulty level, recommending the appropriate developer skill level.

This demonstrates:
- Custom tool definitions with @define_tool
- Session creation and event handling
- Integrating external data (GitHub API) with Copilot
"""

import asyncio
import os
import sys
from pydantic import BaseModel, Field
from copilot import CopilotClient, define_tool

# Try to import httpx for GitHub API calls (fallback to urllib if not available)
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    import urllib.request
    import json as json_lib
    HAS_HTTPX = False


# =============================================================================
# Tool Parameter Models (Pydantic)
# =============================================================================

class GetIssueParams(BaseModel):
    """Parameters for fetching a GitHub issue."""
    owner: str = Field(description="Repository owner (e.g., 'microsoft')")
    repo: str = Field(description="Repository name (e.g., 'vscode')")
    issue_number: int = Field(description="Issue number to fetch")


class GetRepoStructureParams(BaseModel):
    """Parameters for fetching repository structure."""
    owner: str = Field(description="Repository owner")
    repo: str = Field(description="Repository name")
    path: str = Field(default="", description="Path within repo to explore (empty for root)")


class SearchCodeParams(BaseModel):
    """Parameters for searching code in a repository."""
    owner: str = Field(description="Repository owner")
    repo: str = Field(description="Repository name")
    query: str = Field(description="Search query (keywords from the issue)")


class GetFileContentParams(BaseModel):
    """Parameters for fetching a specific file's content."""
    owner: str = Field(description="Repository owner")
    repo: str = Field(description="Repository name")
    path: str = Field(description="File path within the repository")


# =============================================================================
# GitHub API Helper
# =============================================================================

def github_api_request(endpoint: str) -> dict:
    """Make a request to the GitHub API."""
    url = f"https://api.github.com{endpoint}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "copilot-issue-analyzer"
    }
    
    # Add auth token if available
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    if HAS_HTTPX:
        with httpx.Client() as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    else:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            return json_lib.loads(response.read().decode())


# =============================================================================
# Custom Tools for Copilot
# =============================================================================

@define_tool(description="Fetch details about a GitHub issue including title, body, labels, and comments")
async def get_github_issue(params: GetIssueParams) -> str:
    """Fetch issue details from GitHub API."""
    try:
        issue = github_api_request(f"/repos/{params.owner}/{params.repo}/issues/{params.issue_number}")
        
        # Also fetch comments for additional context
        comments = github_api_request(f"/repos/{params.owner}/{params.repo}/issues/{params.issue_number}/comments")
        
        result = {
            "number": issue["number"],
            "title": issue["title"],
            "body": issue.get("body", "No description provided"),
            "state": issue["state"],
            "labels": [label["name"] for label in issue.get("labels", [])],
            "created_at": issue["created_at"],
            "user": issue["user"]["login"],
            "comments_count": issue["comments"],
            "comments": [
                {"user": c["user"]["login"], "body": c["body"][:500]}
                for c in comments[:5]  # Limit to first 5 comments
            ],
            "url": issue["html_url"]
        }
        return str(result)
    except Exception as e:
        return f"Error fetching issue: {str(e)}"


@define_tool(description="Get the directory structure of a GitHub repository to understand the codebase layout")
async def get_repo_structure(params: GetRepoStructureParams) -> str:
    """Fetch repository directory structure."""
    try:
        contents = github_api_request(f"/repos/{params.owner}/{params.repo}/contents/{params.path}")
        
        if isinstance(contents, list):
            items = []
            for item in contents[:50]:  # Limit items
                icon = "📁" if item["type"] == "dir" else "📄"
                items.append(f"{icon} {item['path']}")
            return "\n".join(items)
        else:
            return f"Single file: {contents['path']}"
    except Exception as e:
        return f"Error fetching repo structure: {str(e)}"


@define_tool(description="Search for code in a repository that might be related to an issue")
async def search_code_in_repo(params: SearchCodeParams) -> str:
    """Search for code snippets in the repository."""
    try:
        # GitHub code search API
        query = f"{params.query} repo:{params.owner}/{params.repo}"
        results = github_api_request(f"/search/code?q={query}&per_page=10")
        
        files = []
        for item in results.get("items", [])[:10]:
            files.append({
                "path": item["path"],
                "name": item["name"],
                "url": item["html_url"]
            })
        
        if not files:
            return "No matching code found"
        
        return str(files)
    except Exception as e:
        return f"Error searching code: {str(e)}"


@define_tool(description="Fetch the content of a specific file from the repository")
async def get_file_content(params: GetFileContentParams) -> str:
    """Fetch a specific file's content."""
    try:
        import base64
        content = github_api_request(f"/repos/{params.owner}/{params.repo}/contents/{params.path}")
        
        if content.get("encoding") == "base64":
            decoded = base64.b64decode(content["content"]).decode("utf-8")
            # Truncate very long files
            if len(decoded) > 5000:
                decoded = decoded[:5000] + "\n... [truncated]"
            return decoded
        else:
            return content.get("content", "Unable to decode file content")
    except Exception as e:
        return f"Error fetching file: {str(e)}"


# =============================================================================
# Main Analyzer
# =============================================================================

SYSTEM_INSTRUCTIONS = """You are a senior engineering manager helping to triage GitHub issues.

Your task is to analyze a GitHub issue and assess its complexity to determine which skill level 
of developer should handle it:

- **Junior**: Simple, isolated changes with clear fix path. Good learning opportunity.
- **Mid-level**: Requires understanding multiple components. Moderate complexity but well-defined scope.
- **Senior**: Complex systems knowledge needed. Risk of side effects. May involve architecture decisions.
- **Senior+ / Team effort**: Cross-cutting concerns, security implications, or requires deep domain expertise.

Use the available tools to:
1. Fetch the issue details
2. Explore the repository structure
3. Search for relevant code
4. Read specific files if needed

Then provide your assessment with:
- Recommended skill level
- Confidence (High/Medium/Low)
- Reasoning (what makes it easy or hard)
- Files likely involved
- Suggested approach
- Mentorship notes (if a junior could do it with guidance)
"""


async def analyze_issue(owner: str, repo: str, issue_number: int):
    """Run the complexity analysis on a GitHub issue."""
    
    print(f"🔍 Analyzing issue #{issue_number} in {owner}/{repo}...")
    print("=" * 60)
    
    # Create Copilot client with our custom tools
    client = CopilotClient()
    await client.start()
    
    session = await client.create_session({
        "model": "gpt-5",
        "tools": [
            get_github_issue,
            get_repo_structure,
            search_code_in_repo,
            get_file_content
        ],
        "instructions": SYSTEM_INSTRUCTIONS
    })
    
    # Set up event handling for streaming response
    done = asyncio.Event()
    
    def on_event(event):
        if event.type.value == "assistant.message":
            print(event.data.content, end="", flush=True)
        elif event.type.value == "tool.call":
            print(f"\n🔧 Using tool: {event.data.name}...", flush=True)
        elif event.type.value == "session.idle":
            done.set()
    
    session.on(on_event)
    
    # Send the analysis request
    prompt = f"""Please analyze GitHub issue #{issue_number} in the repository {owner}/{repo}.

First, fetch the issue details, then explore the codebase to understand what's involved,
and finally provide your complexity assessment and skill level recommendation. This should include if it is suitable for a Junior, Mid-level, Senior, or requires Senior+ expertise. Include opportunities for mentorship if applicable (if it can be completed by a less expereience developer with some). 
Also consider if this is a change that should be made at all (maybe it is not best practice to make this change, or the code base is moving away from this pattern)."""
    
    await session.send({"prompt": prompt})
    await done.wait()
    
    print("\n" + "=" * 60)
    
    # Cleanup
    await session.destroy()
    await client.stop()


def parse_github_url(url: str) -> tuple[str, str, int]:
    """Parse a GitHub issue URL into owner, repo, and issue number."""
    # Expected format: https://github.com/owner/repo/issues/123
    url = url.rstrip("/")
    parts = url.replace("https://github.com/", "").split("/")
    
    if len(parts) >= 4 and parts[2] == "issues":
        return parts[0], parts[1], int(parts[3])
    
    raise ValueError(f"Could not parse GitHub issue URL: {url}")


async def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("🐛 GitHub Issue Complexity Analyzer")
        print("=" * 40)
        print()
        print("Analyzes GitHub issues and recommends the appropriate")
        print("developer skill level to handle the fix.")
        print()
        print("Usage:")
        print("  python issue_analyzer.py <github_issue_url>")
        print("  python issue_analyzer.py <owner> <repo> <issue_number>")
        print()
        print("Examples:")
        print("  python issue_analyzer.py https://github.com/microsoft/vscode/issues/12345")
        print("  python issue_analyzer.py microsoft vscode 12345")
        print()
        print("Environment:")
        print("  Set GITHUB_TOKEN for higher API rate limits")
        sys.exit(1)
    
    # Parse arguments
    if len(sys.argv) == 2:
        owner, repo, issue_number = parse_github_url(sys.argv[1])
    elif len(sys.argv) >= 4:
        owner = sys.argv[1]
        repo = sys.argv[2]
        issue_number = int(sys.argv[3])
    else:
        print("Error: Invalid arguments")
        sys.exit(1)
    
    await analyze_issue(owner, repo, issue_number)


if __name__ == "__main__":
    asyncio.run(main())
