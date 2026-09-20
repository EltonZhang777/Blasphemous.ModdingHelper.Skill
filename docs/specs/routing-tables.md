# Spec: Skill routing table standardization

## Problem Statement

From a Blasphemous Mod developer's perspective, the Skill has several routing layers, but their entry cues are not presented consistently. Some routing documents begin with a route map, some place routing decisions after several paragraphs, and some express routing through prose or multiple index tables. An agent must therefore reconstruct the route before it can tell which branch reference owns the request.

The inconsistency is most visible across the top-level Skill entry, the shared invocation gate, Coding-standards routing, Mod-test routing, ModdingAPI reference selection, ModdingAPI development-document routing, and source-code navigation. Existing branch boundaries and relative links are useful, but the lack of a common route-table contract makes omissions and stale destinations harder to detect.

## Solution

Give every document that owns a routing decision one concise route table after its introductory and entry/requirement material and before its detailed routing instructions. Each table will use the same three concepts: the request signal or condition, the route destination, and the boundary or next action.

The seven approved routing layers are covered: the top-level request router; the shared invocation preflight; the Coding-standards router; the shared Mod-test entry; the ModdingAPI reference selector and topic router; the ModdingAPI development-document route index; and the source-code navigation index. Existing route maps and decision tables are normalized in place where they already serve this purpose. Existing navigation, quick-access, and domain-reference tables remain when they are not the document's primary request route.

The change is documentation-only. It makes the route visible before detailed branch instructions, preserves the current branch owners and evidence boundaries, and adds a single documentation-contract seam that can detect missing routes, invalid relative links, misplaced tables, and accidental promotion of excluded documents.

## User Stories

1. As a Blasphemous Mod developer, I want the top-level Skill entry to show the available request routes at a glance, so that I know whether a request belongs to localization, source analysis, log analysis, testing, or general Mod work.
2. As an AI agent, I want the top-level request signal to route to the owning reference before evidence gathering, so that I do not load unrelated branch instructions.
3. As an AI agent, I want the read-only localization exception visible in the route table, so that a term lookup does not enter the operational configuration gate.
4. As an AI agent, I want operational requests to show the shared entry-gate boundary, so that source, log, test, and Mod work receive the required context before execution.
5. As a Mod developer, I want the invocation preflight to show configuration and runtime route outcomes, so that missing configuration, localization-only work, and the tracked-session stop exception are distinguishable.
6. As an AI agent, I want the invocation preflight to point setup and Python validation to their existing owners, so that shared-gate prose does not duplicate or compete with detailed setup guidance.
7. As a Mod developer, I want Coding-standards requests mapped to the correct branch reference, so that C# and runtime Unity, ModdingAPI, Harmony, architecture placement, and excluded source code are separated.
8. As an AI agent, I want the Coding-standards scope gate represented as a negative route, so that decompiled, upstream, dependency, generated, and directly copied code is not sent into Mod-owned standards.
9. As a Mod developer, I want a test request classified by its runtime conditions, so that a deterministic test and a real-profile test do not share an ambiguous entry path.
10. As an AI agent, I want the Mod-test route table to distinguish Real-profile and Automated xUnit evidence, so that startup logs and player-operated Manual verification remain separate.
11. As an AI agent, I want ambiguous test conditions routed to clarification, so that the Skill does not silently select a destructive, incomplete, or evidence-incompatible branch.
12. As a Mod developer, I want a combined test request to show its ordered phases, so that Automated xUnit and Real-profile evidence remain independently attributable.
13. As an AI agent, I want ModdingAPI reference selection to distinguish a validated local checkout from the release-aware remote fallback, so that I do not silently use an unqualified moving branch.
14. As a Mod developer, I want ModdingAPI topic signals mapped to their first documentation pages, so that the agent loads only the development material relevant to the task.
15. As an AI agent, I want advanced and archived ModdingAPI topics visibly separated from stable topics, so that on-demand and version-sensitive material is not treated as the default route.
16. As an AI agent, I want ModdingAPI API facts and decompiled game-source facts routed to separate authorities, so that claims remain attributable to the correct source route.
17. As a Mod developer, I want the ModdingAPI development-document index to show every current upstream document responsibility, so that a new or removed upstream page cannot silently disappear from the local route map.
18. As a source analyst, I want feature and path signals mapped to the correct source-navigation document, so that player, enemy, boss, UI, item, level, tool, localization, and core requests start in the narrowest index.
19. As an AI agent, I want the source-navigation route to preserve the existing `Assembly-CSharp/` boundary, so that navigation guidance does not imply a different source tree.
20. As a documentation maintainer, I want one concise route table per routing-responsibility document, so that route discovery does not require comparing several prose sections.
21. As a documentation maintainer, I want existing route maps and decision tables reused rather than duplicated, so that one route has one visible authority.
22. As an AI agent, I want each route table to state the next owner or boundary, so that a route row is actionable rather than merely descriptive.
23. As a documentation maintainer, I want relative route links checked against the repository, so that table normalization cannot introduce a dead branch destination.
24. As a documentation maintainer, I want route tables placed after entry conditions and before detailed routing instructions, so that the route summary is available before procedural detail.
25. As a maintainer, I want current route semantics preserved, so that the standardization does not change configuration requirements, evidence vocabulary, ownership boundaries, or branch sequencing.
26. As a maintainer, I want the legacy compatibility pointer excluded from the authoritative route set, so that it cannot compete with the Coding-standards sub-skill.
27. As a maintainer, I want terminal branch documents excluded unless they select among sibling routes, so that every Markdown page does not gain a redundant table.
28. As a maintainer, I want the project-architecture route to remain soft guidance, so that route-table work does not become a migration or restructure request.
29. As a maintainer, I want the routing contract verified at the packaged Skill Markdown boundary, so that documentation regressions are caught without requiring a game profile or caller Mod repository.
30. As a future Skill contributor, I want the route-table contract documented in one spec, so that new routing layers can be evaluated against the same scope and placement rules.

## Implementation Decisions

- The approved route-owner set contains seven layers: top-level request routing, shared invocation preflight, Coding-standards routing, shared Mod-test routing, ModdingAPI reference selection/topic routing, ModdingAPI development-document routing, and source-code navigation routing.
- A document qualifies as a route owner when it selects among two or more operational branches, authorities, or destination references, or when it is the authoritative index for a set of feature-specific navigation destinations.
- A branch document that only owns one selected workflow is not a route owner. The legacy compatibility pointer is explicitly non-authoritative and remains outside the route-owner set.
- Each route-owner document receives one concise route table. Existing tables that already own the route are normalized in place; a second competing table is not added.
- The canonical table concepts are request signal or condition, route destination, and boundary or next action. Exact wording may follow the document's established vocabulary.
- Route destinations use the existing relative links and authorities. This work does not create new branch documents, rename branch owners, or introduce alternate destinations.
- Route tables appear after the document's introductory material and entry/requirement constraints, and before detailed routing instructions. The table may replace an existing prose-only route preamble without changing its normative meaning.
- Positive routes, negative scope routes, combined-request sequencing, and clarification routes are included when the existing document owns those decisions. A row is not added merely to repeat non-routing background material.
- The top-level Skill remains the sole cross-branch router. The invocation preflight remains the shared operational gate, and specialized references continue to add only their own requirements and evidence.
- Coding-standards remains the single Mod-owned C# entry point. The route table must preserve its progressive disclosure, scope gate, branch ownership, and RFC 2119 authority.
- Mod-test routing continues to distinguish Automated xUnit, Real-profile, combined requests, and unresolved runtime conditions. Automated evidence, startup evidence, and Manual verification remain separate.
- ModdingAPI routing continues to distinguish configured local references, release-aware remote references, stable topics, advanced or archived topics, and decompiled game-source navigation.
- Source-code navigation continues to route by existing feature/path coverage and does not broaden the indexed source tree.
- The project-architecture route remains a soft placement guide. Route-table work must not move, rename, or restructure existing Caller Mod files.
- The documentation change does not alter runtime code, CLI behavior, configuration parsing, ModdingAPI resolution, game-source lookup, test execution, or profile safety behavior.
- No new dependency is introduced for Markdown validation. Existing standard-library documentation tests and repository checks are preferred.

## Testing Decisions

- The highest and only required seam is the packaged Skill Markdown routing contract. Tests inspect observable route behavior and document relationships, not paragraph wording or internal test helpers.
- The contract verifies that the seven approved route-owner documents each expose one canonical route table in the required location.
- The contract verifies that every current route branch, exclusion boundary, and clarification/combined path owned by the document remains represented.
- The contract verifies that route destinations resolve through existing relative links and that the legacy compatibility pointer and terminal branch documents are not promoted as route owners.
- Existing documentation tests remain prior art for checking branch links, route signals, evidence boundaries, architecture routing, localization routing, and RFC 2119 constraints. The implementation should extend or reuse those checks before adding a separate validator.
- If the existing tests cannot express the cross-document placement and completeness contract, one small standard-library documentation test may be added at that seam; separate per-document test frameworks are not required.
- Verification includes the relevant documentation test command, a relative-link audit, `git diff --check`, and final worktree inspection. No real game, Modding profile, external source checkout, or caller Mod repository is required.

## Out of Scope

- Rewriting or redesigning existing request-routing logic.
- Changing branch ownership, configuration requirements, evidence boundaries, or route sequencing.
- Adding route tables to terminal branch documents, ordinary reference pages, source detail pages, or the legacy compatibility pointer solely for uniform appearance.
- Creating new Skill branches, new source-navigation categories, new ModdingAPI topics, or new route destinations.
- Modifying runtime Python, installer JavaScript, configuration parsing, decompiler behavior, ModdingAPI resolution, or test CLI behavior.
- Adding a new Markdown parser, documentation framework, or runtime dependency.
- Modifying caller Mod repositories, game source trees, Modding profiles, logs, generated output, or external upstream repositories.
- Creating a real-game test, Automated xUnit test project, Test Mod, or gameplay automation.
- Refactoring existing documents beyond the minimum needed to expose the approved route table and preserve readable placement.
- Committing, pushing, or opening a pull request as part of this specification.

## Further Notes

- The route-owner boundary follows the repository glossary: a Coding-standards sub-skill selects Branch references; the project-architecture route remains a soft routing guide; and the Skill repository is distinct from any Caller Mod repository.
- ADR 0002 remains authoritative for the single Coding-standards entry point, progressive disclosure, and RFC 2119 vocabulary. ADR 0008 remains authoritative for the non-migrating project-architecture route.
- The route table is an orientation layer, not a replacement for the detailed reference. Detailed branch documents remain the authority for operational requirements and evidence.
- The route-table contract should be kept small. If future routing layers appear, add them only when they own a real branch or destination decision and update the route-owner inventory together with its documentation test.
