---
status: accepted
---

# Use a self-contained Python Codex workflow for Skill-document compression

The repository needs repeatable, keyless compression for its packaged Skill Markdown, but the existing compression path depends on Anthropic or the Claude CLI. The compression workflow therefore lives under `/ci/compress-docs` as a self-contained Python 3.9+ standard-library CLI that invokes the user's authenticated local Codex CLI, keeps candidates and runtime evidence separate from live skill documents, and requires explicit application. Direct provider APIs and API keys are deliberately deferred; a future provider boundary must be designed and recorded before they are added.

## Considered Options

- Keeping the Anthropic/Claude-only path would preserve the maintainer's credential blocker.
- A Node.js driver would contradict the later repository decision to use Python for repository workflows and add a second implementation boundary.
- A direct DeepSeek or other provider adapter would introduce credential handling and provider coupling that this workaround does not need.
- Modifying the installed `caveman-compress` Skill would broaden the change beyond this repository-local maintenance workflow.

## Consequences

- Native Windows, Linux, and macOS hosts use one Python CLI with no runtime package installation.
- Codex authentication, process execution, and validation failures fail closed; no provider fallback is available.
- Runtime artifacts stay in an ignored, repository-local compression-run area, while Git remains the document rollback boundary after explicit apply.
- A future custom API/API-key integration is possible but is not part of this decision or implementation.
