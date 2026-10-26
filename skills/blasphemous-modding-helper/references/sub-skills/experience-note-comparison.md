# Experience note comparison

This reference owns the read-only comparison of a Blasphemous 1 experience-note candidate. It follows the shared [subagent delegation guidelines](../subagent-delegation/subagent-delegation-general-guidelines.md), reuses the note format and lifecycle in [Modding knowledge](../modding-knowledge.md), and does not define local saving, stale-note maintenance, or pull-request creation.

## Eligibility and child task

- The main task MUST start comparison only for a finding supported by evidence that may help beyond the current task, including a future improvement to the current Mod.
- The main task MUST start one independent child task with comparison as its only responsibility, then continue its own work without waiting for the comparison result.
- The main task MUST give the child the candidate claim, supporting evidence and source, reproduction or verification steps, applicable Blasphemous 1 version context (or state that it is unknown), relevant route, and the resolved local `modding-knowledge` path selected by [Invocation preflight](../config/invocation-preflight.md).
- The child MUST use only the supplied candidate and source scope. It MUST NOT delegate further, access any other user configuration, modify repository or caller files, or edit stale or conflicting notes.
- If an independent child task cannot be started, the main task MUST report comparison as deferred and continue. It MUST NOT perform the comparison synchronously in a way that blocks the main task.
- This workflow covers Blasphemous 1 only. Blasphemous 2 findings MUST NOT enter this comparison.

## Comparison sources

1. The child MUST compare the candidate with every readable Markdown note in the supplied local note corpus under `modding-knowledge`. A missing directory is an empty local corpus. An unresolved path or an unreadable or malformed note makes the comparison incomplete; the child MUST defer it and name the gap.
2. The child MUST compare the candidate with public canonical notes using the [read-only lookup rules](../modding-knowledge.md#read-only-lookup): resolve the public repository's current `main` exactly once, record the full SHA, read the index at that SHA, and fetch at most one clearly matching `verified` note from the same SHA. The child MUST NOT resolve `main` again, fetch a note for an ambiguous match, or use cached or previously fetched content.
3. The child MUST record which local notes were considered and the public SHA, index path, and selected note path, or state that no public note clearly matched. If commit resolution, index retrieval or parsing, or selected-note retrieval or validation fails, the child MUST defer the candidate and MUST NOT use fallback content.
4. The child MUST compare the finding, its applicable version, route, evidence, reproduction or verification steps, verification result, and limitations. An exact duplicate means the same reusable finding applies to the same relevant version context and route with equivalent supporting evidence and verification; a similar title or partial overlap alone is not an exact duplicate. If the distinction is uncertain, the result MUST be deferred.

A comparison failure, an incomplete source corpus, or an unresolved possible match MUST produce `deferred`; the child MUST NOT treat missing evidence as proof that the candidate is unique.

## Result and handoff

The child MUST return exactly one outcome to the main task:

| Outcome | Required handoff |
| --- | --- |
| `unique` | Candidate summary, evidence, reproduction or verification steps, version context, route, local corpus checked, and public SHA/index checked. Use only when both comparisons completed and no duplicate, stale note, conflict, or unresolved possible match remains. |
| `exact-duplicate` | Matching note reference, its version context, and the evidence that establishes the duplicate. Report it to the main task only. |
| `deferred` | Candidate summary, checked sources, and the exact uncertainty, ambiguity, retrieval failure, or corpus gap. |
| `stale` | Existing note reference, its applicable version context, the candidate's version context, and the evidence showing why the existing note may be stale. |
| `conflict` | Existing note reference, both applicable version contexts, and the evidence supporting the incompatible claims. |

For every outcome, the child MUST NOT prompt the user, save a note, or create a pull request. For `exact-duplicate`, `deferred`, `stale`, and `conflict`, the main task MUST receive only the report. For `stale` or `conflict`, the child MUST NOT edit the existing note; maintenance belongs to a separate task. For `unique`, the child MUST return the candidate to the main task without requesting approval or writing anything. A later workflow owns any approval or save decision.

The main task MUST retain responsibility for the user's decisions, any later local-save approval, and any later publication approval. This comparison does not imply that a candidate was approved, saved, canonicalized, or published.

## Completion criteria

Done when the main task has received one outcome with the required handoff fields and can continue independently. A comparison that is uncertain or incomplete is complete only as a disclosed `deferred` result.

The next action is to continue the main task; a `unique` candidate may be presented to the separately authorized local-save workflow after the main task reaches its review point.
