# Referencing ModdingAPI

Agent MUST use this sub-skill whenever task needs ModdingAPI documentation, source
guidance, or coding conventions. Agent MUST resolve reference before browsing it.

Before executing command in this reference, agent MUST apply command-context contract in [Invocation preflight](../config/invocation-preflight.md). commands MUST run from caller's Mod repository; caller does not need repository checkout containing Skill.

## Reference selection

1. Agent MUST read selected `config.yml`.
2. If `modding_api_reference_path` is present, agent MUST use that local checkout. The
   path is authoritative for task; agent MUST NOT clone or update it during an
   ordinary question. If its selector is absent, agent MUST treat it as `latest` for
   explicit local-reference lifecycle commands.
3. If local fields are absent, agent MUST use release-aware remote fallback below.
   This is valid for legacy configuration and for first-time setup where the
   user selected **Skip** for local checkout.

Optional fields, normalized-path rule, and approved user/project scope
locations are defined in the [config schema](../config/preferences-schema.md).
Explicit local-checkout setup flow is in
[first-time-setup.md#q6-local-moddingapi-reference](../config/first-time-setup.md#q6-local-moddingapi-reference).

## Reference and topic routing

After reading `config.yml`, Agent MUST use this single table to select the
reference and topic route. After opening the selected reference's `main.md`
index, Agent MUST resolve topic pages from its `docs/development` directory.

| Request signal / condition | Route destination | Boundary / next action |
| --- | --- | --- |
| Configured local reference: `modding_api_reference_path` is present | `<modding_api_reference_path>/docs/development/main.md` | Agent MUST use this checkout and its selector/lock state. Agent MUST NOT clone or update it for an ordinary question. |
| Release-aware remote fallback: local reference fields are absent, including legacy configuration or setup **Skip** | `<MODDING_API_DOCS_URL>/development/main.md` | Agent MUST resolve the selected reference first and retain its tag, branch, or commit in every URL. Agent MUST NOT use an unqualified moving branch. |
| Stable topic: Project setup and package shape | `docs/development/setup.md` | When project structure matters, Agent MUST follow direct links to `docs/development/mod.md`. |
| Stable topic: Mod class, registration, and lifecycle | `docs/development/mod.md` | For callback order, Agent MUST follow `docs/development/execution.md`. |
| Stable topic: Initialization and callback order | `docs/development/execution.md` | For lifecycle context, Agent MUST follow `docs/development/mod.md`. |
| Stable topic: Persistent data and save compatibility | `docs/development/persistence.md` | When lifecycle context matters, Agent MUST follow `docs/development/mod.md`. |
| Stable topic: ModLog methods and severity | `docs/development/logging.md` | Agent MUST verify version-sensitive facts against the referenced assembly and matching source. |
| Stable topic: Mod configuration | `docs/development/config.md` | When paths or data files matter, Agent MUST follow `docs/development/files.md`. |
| Stable topic: File utilities and Mod-owned files | `docs/development/files.md` | When configuration is involved, Agent MUST follow `docs/development/config.md`. |
| Stable topic: Input and keybindings | `docs/development/input.md` | For registration context, Agent MUST follow `docs/development/mod.md`. |
| Stable topic: Localization and translations | `docs/development/localization.md` | For resource paths, Agent MUST follow `docs/development/files.md`. |
| Advanced / archived topic: Console commands | `docs/development/console.md` | Agent MUST read only on demand and MUST verify current command types in source. |
| Advanced / archived topic: Custom items | `docs/development/items.md` | Agent MUST read only on demand and MUST verify current item APIs in source. |
| Advanced / archived topic: Level modifications | `docs/development/levels.md` | Agent MUST read only on demand and MUST treat active-development behavior as version-sensitive. |
| Advanced / archived topic: Custom penitences | `docs/development/penitence.md` | Agent MUST read only on demand and MUST verify current types in source. |

## Stable API topic routing

Rows marked **Stable** are the default first route for ordinary ModdingAPI
work.

## Advanced and archived topics

Agent MUST load rows marked **Advanced / archived** only when the task names
that topic or a stable route points to it. Agent MUST follow the selected
index's current labels because upstream status may change.

For topics absent from the table, Agent MUST use the selected reference's
`docs/development/main.md` as the index and MUST follow only the exact linked
page needed for the question. Agent MUST NOT copy the upstream documentation
tree into this Skill.

## Routing contract

Agent MUST treat the selected reference as the sole ModdingAPI authority for
the task and MUST open its `docs/development/main.md` index before loading the
named page or any directly linked page required by the question. The `main.md` filename
identifies that documentation index; it MUST NOT be interpreted as an
unqualified Git branch. The resolver's tag, branch, or commit remains part of
every remote URL and local-reference decision.

Agent MUST finish reference selection by recording either the validated local
checkout and its selector/lock state or the release-aware remote resolver
result. Agent MUST browse only the recorded route. Version-sensitive
signatures and behavior MUST be confirmed against the actual referenced
assembly and matching source before writing code.

## Game-source separation

Agent MUST keep two source routes distinct:

- ModdingAPI API, lifecycle, logging, and framework behavior MUST use release-aware reference route.
- Decompiled Blasphemous game classes MUST use
  [Blasphemous Source Code Navigation](../source-code-navigation/MAIN.md) and
  its source-analyzer branch.

Task may load both routes when it compares framework behavior with game
class, but each claim MUST remain tied to route that owns it.

## Release-aware remote fallback

Official upstream is
`https://github.com/BrandenEK/Blasphemous.ModdingAPI.git`. Resolve remote
reference before opening documentation or source:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/resolve_modding_api.py" --selector latest
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\resolve_modding_api.py') --selector latest
```

Agent MUST use resolver's `MODDING_API_DOCS_URL` and `MODDING_API_SOURCE_URL` outputs
for remote browsing. `latest` selector is resolved from official
GitHub Releases endpoint and accepts only newest non-draft,
non-prerelease Release. It does not silently use `main` or another moving
branch. If user deliberately selected different reference, pass exactly
one of:

- `tag:REF` for named Git tag;
- `branch:REF` for explicit branch, including `branch:main` when requested;
- `commit:SHA` for exact 40-character commit.

The Python resolver MUST emit the established `MODDING_API_*` fields. nonzero
exit MUST print terminal `[ERROR REPORT]` with cause and next step. Agent MUST preserve that
report, MUST NOT invent URL, and MUST ask for corrected selector, local checkout,
or retry when Release lookup fails.

The fixture schema, provenance fields, and mismatch recovery contract are
defined in the [config schema](../config/preferences-schema.md#resolver-fixture-contract).
The smoke check consumes that contract and never presents fixture data as live Release
metadata.

## Local checkout use

When setup succeeds, agent MUST use stored absolute path for documentation and source
lookups. fresh-clone commands are explicit operations and create shallow
checkout pinned to stored selector. They also write sibling lock state
`<reference-path>.lock`; lock is outside checkout and records the
selector, resolved tag, resolved commit, check time, and supported repository:

- Python: `"$PYTHON3" "$SKILL_ROOT/scripts/clone_modding_api.py"`

Tags and commits are detached; explicit branches track their corresponding
`origin/<branch>`. Existing targets are not replaced.

## Explicit lifecycle operations

Agent MUST use lifecycle manager only when user explicitly asks to check or
update local checkout. Ordinary ModdingAPI questions MUST NOT mutate the
checkout. Python `clone_modding_api.py` owns fresh-clone behavior and Python
`manage_modding_api.py` owns check/update behavior; its compatibility wrappers expose
the existing operation model:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/manage_modding_api.py" --operation check
"$PYTHON3" "$SKILL_ROOT/scripts/manage_modding_api.py" --operation update
"$PYTHON3" "$SKILL_ROOT/scripts/manage_modding_api.py" --operation update --dry-run
"$PYTHON3" "$SKILL_ROOT/scripts/manage_modding_api.py" --operation check --offline
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\manage_modding_api.py') -Operation check
& $PYTHON3 (Join-Path $SkillRoot 'scripts\manage_modding_api.py') -Operation update
& $PYTHON3 (Join-Path $SkillRoot 'scripts\manage_modding_api.py') -Operation update -DryRun
& $PYTHON3 (Join-Path $SkillRoot 'scripts\manage_modding_api.py') -Operation check -Offline
```

Manager reads `modding_api_reference_path` and
`modding_api_reference_selector` from the selected configuration file, unless
`--target-path`/`-TargetPath` or `--selector`/`-Selector` is supplied. It also
accepts same `--scope`/`-Scope` and `--preferences-file`/`-PreferencesFile`
options as fresh-clone command. When none of those three routing options
is supplied, it uses the active configuration context selected by [Invocation
preflight](../config/invocation-preflight.md); explicit scope always selects
its approved path.

`check` resolves requested selector, verifies clean worktree and the
official origin, confirms checkout shape and current HEAD, and writes a
fresh lock state when checkout matches. `update` is only operation
that fetches and changes checkout: fixed references fetch resolved
commit and remain detached; explicit branches fetch their remote-tracking
branch and advance only with fast-forward. dirty worktree, invalid
repository, wrong origin, divergent history, wrong checkout shape, or missing
reference stops before destructive recovery. manager never resets,
stashes, deletes, or replaces checkout. shallow branch checkout may be
deepened during update so Git can prove that fast-forward is safe; fixed
reference updates remain shallow by default.

`--dry-run` resolves and validates planned operation but performs no
fetch, checkout, merge, or lock-state write. matching `check --offline`
uses only sibling lock and local Git state; it succeeds only when the
selector, resolved commit/tag, origin, clean worktree, checkout shape, and
current HEAD agree. For branch dry-run whose local remote-tracking ref is
absent, operation remains non-mutating and emits
`MODDING_API_PLAN_REQUIRES_FETCH=true`. offline update fails because it
cannot refresh reference. If online `check` loses network access, it may fall back to
that same matching lock validation; missing or mismatching offline state is
error and MUST NOT be presented as verified version.

Exit codes are stable across the Python entry points: `0` means success, `2`
means usage or configuration failure, and `1` means runtime, Git, network,
offline, or reference-state failure. Every failure prints terminal text
`[ERROR REPORT]` containing `operation`, `target_path`, `selector`,
`current_head`, `worktree_state`, `network_state`, `cause`, and `next_step`.

Agent MUST mark lifecycle verification complete when explicitly requested operation exits successfully and reports resolved selector and checkout state: non-dry-run `check` or `update` MUST leave expected lock state, while `--dry-run` MUST report its validated plan without writing lock state. question that did not request lifecycle mutation is complete only after agent reports that no lifecycle operation was performed.

## Documentation smoke check

Agent MUST run the deterministic Python documentation smoke check from the
caller's Mod repository using the explicit Skill-root path:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/test_referencing_modding_api.py"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\test_referencing_modding_api.py')
```

It verifies top-level pointer, stable and archived route tables, the
game-source boundary, and both configuration outcomes: configured local path
selects local route, while skipped local setup selects release-aware
remote route. It also reports the selected configuration selector, local lock
selector, local lock version, remote selector/resolution version, matching
fixture version, and historical fixture label; a mismatch fails with recovery
guidance. Bash and PowerShell
command forms invoke this same Python entry point and therefore retain
identical resolver fields, exit codes, and fixture checks.

## Cross-platform acceptance gate

Agent MUST run the deterministic Python acceptance gate before publishing
changes to the reference workflow:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/test_modding_api_acceptance.py"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\test_modding_api_acceptance.py')
```

Gate runs resolver, clone, lifecycle, and documentation suites through the
same Python surface on the current native host. Its fixture scenarios cover
annotated tags,
branches, exact commits, clean updates, dirty worktrees, wrong origins,
missing references, network failure, offline locks, output fields, and exit
codes. It also checks resolver parity, installer dry-runs, repository-owned
Markdown links, reports ignored local Markdown artifacts separately, and runs
`git diff --check`. It never contacts GitHub and never uses user's reference
checkout.

Final verification invocation may require a clean worktree:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/test_modding_api_acceptance.py" --require-clean
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\test_modding_api_acceptance.py') --require-clean
```

Live network check is separate and manual. It resolves the actual latest
non-draft, non-prerelease Release through the Python entry point, compares the
resolved tag and commit, and verifies tag-specific documentation and source
URLs:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/test_modding_api_live.py"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\test_modding_api_live.py')
```

Agent MAY run live check only when network access is available. failure MUST NOT be
treated as reason to substitute `main`; agent MUST preserve resolver error report and
retry or use explicit selector.

Acceptance verification is complete when the Python documentation smoke check
and acceptance gate exit successfully on each native Windows/Linux/macOS CI
matrix job. Ignored local Markdown artifacts MAY produce a separate warning,
but MUST NOT make repository-owned documentation validation fail; live network
check is optional and MUST be reported as not run when it was not requested or
unavailable.

## Completion criterion

Agent MUST report the selected ModdingAPI reference and topic, the resolved
reference evidence, status, the blocked reason when applicable, and the next
source or code action. If the request did not ask for lifecycle mutation, the
report MUST state that no checkout mutation was performed.
