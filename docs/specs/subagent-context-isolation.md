# Spec: Context-isolated interactive sub-agent delegation

## Problem Statement

From a Blasphemous Mod developer's perspective, the Skill can require broad, read-heavy evidence gathering across decompiled source, runtime logs, ModdingAPI references, and localization indexes. Keeping every source document and log excerpt in the main agent's context makes large requests harder to reason about and increases the chance that evidence from one authority is mixed with another.

The Skill also lacks one shared delegation contract. Without a common contract, a delegated worker could repeat entry-gate decisions, read an unapproved reference, silently change log evidence mode, answer a user decision, modify shared files, or return a conclusion without reproducible evidence. Those failures would weaken the existing source, log, ModdingAPI, and localization boundaries.

The contract must remain usable across supported hosts and agent implementations. It must not depend on a particular model, harness, IDE, operating system shell, or vendor-specific platform capability.

## Solution

Add one shared, host-neutral delegation reference under the Skill's `references` area as the sole normative source for interactive sub-agent creation, context isolation, task boundaries, and evidence handoff. The top-level Skill router and the applicable branch references link to that source and add only their own branch-specific constraints.

Extend the read-only evidence-gathering option to four branches: source analysis, log analysis, ModdingAPI reference lookup, and localization lookup. A main agent creates an interactive sub-agent only when a task is read-only, independently verifiable, clearly bounded, and large enough that keeping the required reading in the main context would materially reduce clarity. The main agent remains responsible for entry gates, route selection, user decisions, configuration writes, synthesis, and all document or tracker publication.

The sub-agent reads the parent-provided scope in the shared workspace without creating a worktree or writing repository, configuration, source, or log content. It returns a compact, reproducible evidence handoff. If delegation is unavailable, the main agent performs the same evidence-gathering responsibility without claiming that isolation occurred.

## User Stories

1. As a Blasphemous Mod developer, I want large evidence-gathering work isolated from the main agent's context, so that broad source, log, reference, and localization investigations remain understandable.
2. As an AI agent, I want one shared delegation contract, so that every applicable branch uses the same isolation and evidence rules.
3. As a Skill maintainer, I want the shared delegation contract to have one normative owner, so that repeated branch wording cannot drift.
4. As an AI agent, I want the delegation rule to activate only for read-only, bounded, independently verifiable work, so that unnecessary child tasks are not created for small lookups.
5. As an AI agent, I want broad or context-heavy reading to be recognized as a delegation trigger, so that context pressure is handled without inventing a fragile file-count threshold.
6. As an AI agent, I want a small targeted read to remain in the main context, so that trivial work does not incur delegation overhead.
7. As an AI agent, I want the shared entry gate and request route completed before delegation, so that the child task receives an already-resolved operational boundary.
8. As an AI agent, I want the parent task to provide the exact question, allowed sources, resolved paths, evidence mode, and handoff format, so that a child task never has to guess its scope.
9. As an AI agent, I want each coherent evidence slice assigned to at most one child task, so that ownership and reconciliation remain clear.
10. As an AI agent, I want child tasks prohibited from creating further child tasks, so that delegation depth does not become unbounded.
11. As an AI agent, I want independent evidence slices to be delegable separately, so that unrelated source and log reading do not share an unnecessarily broad context.
12. As a Skill maintainer, I want child tasks to use the shared workspace only for reading, so that the delegation contract does not create hidden repository or worktree state.
13. As an AI agent, I want child tasks prohibited from modifying documents, source, logs, configuration, or generated data, so that the main agent remains the single write owner.
14. As a user, I want the main agent to retain requirement clarification and user questions, so that a child task cannot make a decision on my behalf.
15. As an AI agent, I want a blocked child task to return the exact missing fact and question rather than inventing an answer, so that the main agent can decide whether clarification is needed.
16. As an AI agent, I want a standard evidence handoff containing task identity, claims, precise locations, source identity, gaps, conflicts, and next action, so that child results are reproducible.
17. As an AI agent, I want source evidence to include precise file and line locations, so that every cited class, path, and relationship can be checked in the selected source tree.
18. As an AI agent, I want source-analysis child tasks to follow the existing source-navigation authority and configured source-path requirements, so that decompiled game evidence remains separate from Mod-owned and dependency code.
19. As an AI agent, I want log-analysis child tasks to use an explicitly selected current-log or Test log snapshot mode, so that live evidence is not confused with session-bound evidence.
20. As an AI agent, I want log-analysis child tasks to report missing or unreadable sources without silently switching modes or changing configuration, so that the existing recovery contract remains intact.
21. As an AI agent, I want ModdingAPI lookup child tasks to receive a resolved local or release-aware remote reference, so that version-sensitive framework evidence comes from the selected authority.
22. As an AI agent, I want ModdingAPI lookup child tasks to read only the selected topic and directly required pages, so that unrelated upstream documentation does not consume context.
23. As an AI agent, I want ModdingAPI lookup child tasks prohibited from cloning, updating, checking out, or replacing a reference, so that ordinary evidence lookup remains non-mutating.
24. As an AI agent, I want ModdingAPI evidence to preserve the selected selector, version, commit, or local checkout identity, so that a claim can be reproduced against the same framework reference.
25. As an AI agent, I want localization lookup child tasks to use the index selected for the requested languages, so that a small core index is not replaced by an unnecessary full-language read.
26. As an AI agent, I want full-language comparisons and ambiguous multi-candidate searches to be delegable, so that large localization evidence does not crowd out the main reasoning context.
27. As an AI agent, I want localization child tasks to return exact keys, requested-language values, aliases, and ambiguity, so that translation variants remain distinguishable.
28. As an AI agent, I want localization evidence kept separate from gameplay evidence, so that a text match cannot silently become a claim about runtime behavior.
29. As an AI agent, I want unresolved code-like localization terms to be reported for controlled source routing by the main agent, so that a child task does not silently cross branch ownership.
30. As an AI agent, I want the main agent to combine child evidence with user observations and other branch evidence, so that the final answer preserves each evidence owner's boundary.
31. As an AI agent, I want the main agent to perform the same evidence work when a child task is unavailable, so that platform availability does not change the answer contract.
32. As a Skill maintainer, I want delegation rules written in host-neutral language, so that the Skill does not require a specific model, harness, IDE, shell, or vendor platform.
33. As a Skill maintainer, I want the contract to avoid platform-specific command forms and provider identifiers, so that the same rules apply on supported Windows, Linux, and macOS workflows.
34. As a Skill maintainer, I want documentation tests to verify observable routing and evidence boundaries, so that prose refactoring cannot silently remove delegation safeguards.
35. As a Skill maintainer, I want existing route owners and evidence vocabulary preserved, so that this feature adds context isolation without changing source, log, ModdingAPI, or localization semantics.
36. As a maintainer, I want task publication and repository changes to remain owned by the main agent, so that a child task cannot create external or externally visible state.

## Implementation Decisions

- A new shared delegation reference under the installed Skill's `references` area is the single normative owner for interactive sub-agent terminology, trigger conditions, lifecycle, context boundary, prohibited actions, evidence handoff, fallback behavior, and platform-neutral wording.
- The top-level Skill router points applicable requests to the shared delegation reference before the specialized branch reference. The specialized branches link to the shared contract and state only their own evidence-source and route-specific rules.
- The delegation-enabled branch set is limited to source analysis, log analysis, ModdingAPI reference lookup, and localization lookup.
- A task is eligible when it is read-only, clearly bounded, independently verifiable, and large or context-heavy enough that keeping the required reading in the main context would materially reduce clarity. The contract uses this qualitative condition rather than a new numeric configuration threshold.
- A small targeted read stays in the main agent. The main agent may create separate child tasks for independent evidence slices, but each coherent slice has one child owner and child tasks cannot delegate further.
- Delegation occurs after the Requirement levels, shared entry gate, and request routing have been completed for operational branches. The localization branch keeps its documented configuration exception; its index and language scope are resolved before delegation.
- The main agent passes the exact question, completed gate facts, allowed authorities, resolved configuration and paths, evidence mode, and required handoff fields. The child receives no authority to broaden that scope.
- Child tasks read the current shared workspace and selected external read sources as needed, but do not create worktrees or modify repository files, caller configuration, source, logs, generated data, reference checkouts, or external services.
- The main agent owns requirement clarification, user confirmation, entry-gate decisions, route selection, configuration and lifecycle writes, evidence synthesis, final conclusions, requirements documents, tracker tickets, and publication.
- A child handoff must identify the task, state claims and unresolved items, cite precise source locations, identify the active configuration or reference identity where relevant, include short evidence or structured records, name gaps and conflicts, and state the next action. It must not return unrelated full-document or full-log dumps.
- Source-analysis delegation preserves the existing configured source-path gate and the source-navigation authority. Every source claim remains tied to the selected source tree and is returned with a precise location.
- Log-analysis delegation preserves the existing BepInEx-first behavior, configured Unity-log requirement, diagnostic ownership vocabulary, and explicit `--current` versus `--snapshot` distinction. A child cannot silently change evidence mode or edit the configuration to recover a missing source.
- ModdingAPI delegation begins only after the main agent resolves the selected local checkout or release-aware remote reference. The child follows the selected development index and directly required topic pages, retains selector/version/commit identity, and may inspect matching source or assembly evidence when the selected route requires version-sensitive verification. It cannot clone, update, check out, replace, or otherwise manage the reference.
- Localization delegation begins only after the main agent determines the requested instruction, source, target, comparison languages, and correct bundled index. It may search the selected index and semantic aliases for broad comparisons or ambiguity, but it must preserve exact localization records, report candidates, and keep gameplay inference and source-branch escalation with the main agent.
- If an interactive child task is unavailable, the main agent performs the same read-only evidence-gathering responsibility under the same authority, source-mode, and write restrictions and does not claim that isolation occurred.
- The contract is host-neutral. It names no model, harness, IDE, shell, provider, or vendor-specific API and does not require a platform change. Any host that can maintain the stated parent/child scope and evidence handoff may implement the behavior.
- The highest implementation seam is the packaged Skill Markdown routing and branch contract. No runtime API, CLI, profile workflow, or Codex platform seam is introduced.

## Testing Decisions

- Tests verify externally observable Skill behavior and documentation relationships, not exact paragraph wording, model behavior, or a particular agent implementation.
- The primary test seam is the packaged Skill Markdown delegation contract spanning the top-level router, the shared delegation reference, and the four enabled branch references.
- Documentation tests must verify that all four enabled branches link to one shared delegation authority, that the shared contract defines the trigger, parent/child boundary, handoff, fallback, and platform-neutral requirements, and that branch documents retain only branch-specific constraints.
- Positive route checks must cover broad source reading, broad log reading, ModdingAPI reference reading, and full or ambiguous localization lookup.
- Negative route checks must cover small targeted reads, configuration/setup decisions, reference lifecycle mutations, real-profile operations, Manual verification, code writes, and publication, ensuring they remain with the main agent or their existing owner.
- Source checks must verify preservation of the configured source-path requirement, source-navigation authority, and precise evidence expectation.
- Log checks must verify preservation of explicit current versus snapshot evidence, no silent fallback, and no child configuration write.
- ModdingAPI checks must verify resolved-reference identity, selected-topic routing, local/remote authority separation, and the prohibition on clone/update/checkout operations during ordinary lookup.
- Localization checks must verify index selection, full-language/ambiguity gating, exact record reporting, semantic-alias handling, and separation of localization evidence from gameplay evidence.
- Cross-platform checks must reject normative dependencies on a specific model, harness, IDE, shell, provider, or vendor API and must validate repository-relative links through existing Markdown checks.
- Existing localization documentation tests, ModdingAPI resolver and documentation smoke tests, source/log route checks, RFC 2119 audits, repository Markdown-link checks, `git diff --check`, and final worktree inspection are prior art and should be reused or extended before adding a new standard-library documentation check.
- No real game process, Modding profile, external reference checkout mutation, or user gameplay action is required to verify this documentation contract.

## Out of Scope

- Creating, managing, or changing the capabilities of the agent platform or any parent/child execution API.
- Depending on or linking to a specific model, harness, IDE, shell, provider, or vendor-specific integration.
- Delegating coding standards decisions, project-architecture decisions, code generation, code modification, or code publication.
- Delegating configuration selection, first-time setup, path recovery, dependency installation, decompilation, or reference clone/update/checkout operations.
- Delegating Automated xUnit execution, Real-profile build/deploy/launch/stop/clean/snapshot operations, process control, or Manual verification.
- Changing the existing source, log, ModdingAPI, localization, test, profile, or evidence semantics beyond adding the delegation boundary.
- Adding a configuration field or numeric threshold for delegation size.
- Creating a worktree, persistent log copy, generated source tree, or other caller-owned artifact for a child task.
- Adding a new source-navigation category, ModdingAPI topic, localization corpus, or alternate evidence authority.
- Implementing the underlying business Mod, changing the Skill runtime scripts, or adding a dependency solely for delegation.
- Standardizing route tables or modifying the sibling group's untracked routing-table work.
- Publishing, committing, pushing, or creating a pull request as part of the spec implementation itself.

## Further Notes

- “Main agent” means the agent that owns the user conversation and final task result. “Interactive sub-agent” means a bounded worker for read-only evidence collection; it is not a replacement decision-maker or publisher.
- The shared delegation reference is intentionally a normal Skill reference document, not a platform adapter. Branch documents should link to it and state only deltas that cannot be inferred from the shared contract.
- Shared-workspace context isolation is logical: a child can inspect the same files needed for evidence, but isolation comes from explicit task scope, read-only permissions, and a bounded handoff rather than a required Git worktree.
- Evidence handoffs should prefer concise claims and precise locations over copying complete source files or logs. The parent can request a narrower follow-up slice when the evidence is insufficient.
- A later extension to another Skill branch requires a separate scope decision and must preserve the same read-only, independently verifiable, context-heavy threshold; it is not implied by this spec.
