# Read-only evidence delegation

This reference is the sole authority for shared delegation rules across read-only evidence-gathering routes. When route-owner documents cover delegation, they MUST link here and add only branch-specific delegation constraints; they remain authoritative for their other branch-specific guidance.

## Terms

- **Main agent**: the agent responsible for the user's request, decisions, evidence synthesis, and final response.
- **Child task**: one bounded task assigned to another agent to gather read-only evidence for the main agent.

## Eligibility and timing

The main agent MAY delegate an evidence-gathering task only when all of these conditions hold:

- The task is read-only.
- The question and permitted sources can be bounded clearly.
- Another agent's findings can be checked independently.
- The required reading is broad or context-heavy enough that keeping it in the main context would materially reduce clarity.

A small, targeted lookup SHOULD stay in the main context. The Skill does not set a file-count or other numeric delegation threshold. Work that requires a user decision, a configuration or reference-lifecycle change, code or document edits, or publication MUST remain with the main agent or its existing workflow owner.

Before creating a child task, the main agent MUST complete the shared entry gate for operational routes and select the request route. It MUST also resolve that route's required gate, source scope, authority, and evidence mode. For the read-only localization exception, it MUST select the applicable index and language scope. If a required gate, decision, or source is unresolved, the main agent MUST resolve it or ask the user before delegating.

## Parent scope and ownership

The main agent MUST give each child task:

- One exact question and a bounded evidence slice.
- The permitted sources and resolved paths.
- The completed gate facts and the selected authority identity, including version or checkout identity when relevant.
- The required evidence mode, such as the selected log mode, when relevant.
- The required handoff fields.

Each child task MUST own exactly one coherent evidence slice. Each slice MUST have exactly one child owner. Independent slices MAY be assigned to separate child tasks. A child task MUST NOT delegate further.

The main agent MUST retain ownership of route selection, entry-gate decisions, configuration and reference lifecycle changes, user clarification and decisions, path recovery, evidence synthesis, conclusions, and every repository or tracker write and publication.

## Child task boundaries

A child task MUST read only within the parent-provided scope and MUST treat the shared workspace as read-only. It MUST NOT create a worktree or branch, modify repository or caller files, change configuration, write logs or generated data, change the selected authority or evidence mode, or write to an external service. Every child task MUST NOT modify any source tree, source file, or game-code copy, whether inside or outside the shared workspace; this includes every path named in `references/config/first-time-setup.md`: `lightweight_source_code_path` (including decompiler output at `<skill-root>/source_code/`), optional `full_source_code_path`, and the Steam game installation used for source acquisition.

A child task MUST NOT broaden the question, change the route or resolved scope, make a decision for the user, contact the user for clarification, publish results, or create another child task. If the provided scope is insufficient or a source is missing or unreadable, it MUST return the exact gap and the question or recovery action for the main agent; it MUST NOT guess or silently switch sources or modes.

## Evidence handoff

The child task MUST return a compact handoff that lets the main agent reproduce and check its findings. It MUST include:

- Task identity, question, and scope.
- Each claim with concise supporting evidence and a precise location, such as a file and line, document section, log path and record, or reference page.
- The selected source identity, such as a repository, checkout or commit, document or reference version, log path or session, or localization index.
- The evidence mode when relevant.
- Missing evidence, ambiguity, or conflicts.
- The next useful action.

The handoff SHOULD include only the short excerpts or structured records needed to verify the claims. It MUST NOT copy entire documents, source trees, or logs when precise locations and concise evidence suffice. The main agent SHOULD verify the handoff against the requested authority before using it in a conclusion.

## Fallback

If the available environment cannot create or safely scope a child task, the main agent MUST perform the same read-only evidence gathering under the same source, mode, and write boundaries. It MUST NOT claim that context isolation or delegation occurred.

## Host neutrality

This contract does not require a particular model, harness, IDE, shell, provider, or vendor API. Any environment used for a child task MUST preserve the scope, read-only boundary, ownership, and handoff rules above. If it cannot, the main agent MUST use the fallback.