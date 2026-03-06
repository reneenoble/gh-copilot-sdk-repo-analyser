# Responsible AI Notes

## Overview

The GitHub Issue Complexity Analyser uses the GitHub Copilot SDK to generate AI-powered assessments of GitHub issue complexity. This document outlines the responsible AI considerations for this tool.

## What This Tool Does

- Reads publicly available GitHub issue data (title, body, labels, comments)
- Reads publicly available repository content (file structure, source code)
- Generates a complexity assessment with a recommended developer skill level
- Provides all output transparently — users see every tool call and data source

## What This Tool Does NOT Do

- Does not make hiring, firing, or performance evaluation decisions
- Does not store or profile any personal data about developers
- Does not access private repositories unless the user provides authentication
- Does not automatically assign issues or take action on repositories
- Does not replace human engineering judgement

## Key Considerations

### Human Oversight

The tool produces **recommendations, not decisions**. Every assessment should be reviewed by an engineering manager or tech lead before being acted upon. The skill level recommendation is a starting point for discussion, not an automated assignment.

### Skill Level Labels

The labels "Junior", "Mid-level", "Senior", and "Senior+" refer to **familiarity with the specific codebase and technologies involved**, not to a developer's overall capability or worth. A senior developer in one domain may be a junior in another. The tool explicitly includes "Mentorship Notes" to support developer growth rather than gatekeeping.

### Bias Awareness

- **Issue quality bias** — Sparse or poorly written issues may appear simpler than they are. Well-documented issues with detailed descriptions may appear more complex. Teams should be aware of this when interpreting results.
- **Language bias** — Issues written in non-English languages or with non-standard terminology may be less accurately assessed.
- **Repository bias** — The agent explores code structure heuristically. Unconventional project layouts may lead to incomplete exploration.

### Transparency

- In the CLI, every tool call is printed to the terminal as it happens
- In the web UI, each tool call is shown as a chat bubble with details (which file, which path, which search query)
- The agent's full reasoning is included in the output, not just the conclusion

### Data Privacy

- The tool only accesses data that is already available via the GitHub REST API
- No data is stored persistently — each analysis is a stateless request
- GitHub API rate limits are respected; authenticated tokens are only used to increase rate limits, not to access private data beyond what the user already has access to

### Limitations

- The assessment quality depends on the quality of the issue description and codebase structure
- The agent may not fully understand proprietary frameworks or domain-specific patterns
- Complex multi-repository or monorepo issues may not be fully captured
- The tool does not understand organisational context (team capacity, business priorities, deadlines)

## Mitigation Strategies

1. **Always present as "recommended" not "required"** — UI and output language frames all assessments as suggestions
2. **Include mentorship path** — Every assessment includes guidance for less experienced developers, promoting growth
3. **Show your work** — Full tool call transparency so users can evaluate the agent's reasoning
4. **No automated actions** — The tool is read-only and informational; it never modifies repositories or assignments
