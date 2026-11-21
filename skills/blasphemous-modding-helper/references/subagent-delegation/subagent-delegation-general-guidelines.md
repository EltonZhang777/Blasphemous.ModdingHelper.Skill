# General subagent delegation guidelines

This document defines the shared baseline for assigning work to a subagent. Route-specific references add constraints for their phase and remain authoritative for those details.

## Scope and ownership

- The parent agent MUST assign one bounded responsibility with clear scope, acceptance criteria, required inputs, expected handoff, and any authorized write boundary.
- Each responsibility MUST have one owner. Parallel tasks MAY run only when their scopes and write sets are independent. If tasks touch one document, the parent MUST assign disjoint sections and integrate their changes deliberately.
- A child MUST stay within its assignment and MUST NOT broaden the task or delegate further. If scope or required information is missing, it MUST return the gap and the question for the parent instead of guessing.
- The parent retains user intent, user decisions, clarification, integration, final review, and the final report. External writes and publication require explicit authorization in the task scope.
- A child may modify files only within the write boundary explicitly granted by the parent. Otherwise, treat the supplied workspace as read-only.

## Handoff and review

The child MUST return a concise handoff with the task identity, result, files changed or inspected, commands and checks with outcomes, evidence locations, and unresolved issues. It MUST distinguish completed work from assumptions or blocked work.

The parent MUST inspect delegated results against the assigned acceptance criteria and run the relevant checks before reporting completion. A child result is evidence for the parent to review, not a substitute for integration or final review.

## Specialist guidance

- Read-only evidence gathering MUST follow [Read-only evidence delegation](read-only-evidence-delegation.md), including its stricter source and write boundaries.
- Mod-test delegation MUST follow the selected phase owner: [Automated xUnit testing delegation](xunit-testing-delegation.md) or [Real-profile testing delegation](real-profile-testing-delegation.md).
- Other route owners remain authoritative for their own branch-specific requirements.

These rules are host-neutral: no particular model, harness, IDE, shell, provider, or vendor API is required.
