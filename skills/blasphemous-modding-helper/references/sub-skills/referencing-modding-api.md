# Referencing ModdingAPI

Agent MUST use this sub-skill whenever task needs ModdingAPI documentation, source
guidance, or coding conventions. Agent MUST resolve reference before browsing it.

Before executing command in this reference, agent MUST apply command-context contract in [Invocation preflight](../config/invocation-preflight.md). commands MUST run from caller's Mod repository; caller does not need repository checkout containing Skill.

## Reference selection

1. Agent MUST read selected `preferences.md`.
2. If `modding_api_reference_path` is present, agent MUST use that local checkout. The
   path is authoritative for task; agent MUST NOT clone or update it during an
   ordinary question. If its selector is absent, agent MUST treat it as `latest` for
   explicit local-reference lifecycle commands.
3. If local fields are absent, agent MUST use release-aware remote fallback below.
   This is valid for legacy preferences and for first-time setup where the
   user selected **Skip** for local checkout.

Optional fields, normalized-path rule, and approved user/project scope
locations are defined in [preferences-schema.md](../config/preferences-schema.md).
Explicit local-checkout setup flow is in
[first-time-setup.md#q6-local-moddingapi-reference](../config/first-time-setup.md#q6-local-moddingapi-reference).

## Routing contract

Selected reference is sole ModdingAPI authority for task. Agent MUST start at
upstream development index and follow only linked page needed for the
question:

- Local checkout: `<modding_api_reference_path>/docs/development/main.md`.
- Remote fallback: `<MODDING_API_DOCS_URL>/development/main.md`, where
  `MODDING_API_DOCS_URL` comes from resolver for selected reference.

`main.md` name identifies documentation index. It is not request to
read unqualified Git branch; agent MUST NOT interpret it that way. resolver's tag, branch, or commit remains
part of every remote URL and every local-reference decision.

Reference selection is complete when active `preferences.md` scope has been read and agent has recorded one resolved route: validated local checkout with its selector/lock state, or release-aware remote resolver output required for browsing.

## Stable API topic routing

Agent MUST use this table as first route for ordinary ModdingAPI work. Agent MUST open the
selected reference's `docs/development/main.md`, then load named page and
any directly linked page required by question.

| Task topic | First page | Typical follow-up |
| --- | --- | --- |
| Project setup and package shape | `docs/development/setup.md` | `docs/development/mod.md` |
| Mod class, registration, and lifecycle | `docs/development/mod.md` | `docs/development/execution.md` |
| Initialization and callback order | `docs/development/execution.md` | `docs/development/mod.md` |
| Persistent data and save compatibility | `docs/development/persistence.md` | `docs/development/mod.md` |
| ModLog methods and severity | `docs/development/logging.md` | Referenced assembly/source when facts conflict |
| Mod configuration | `docs/development/config.md` | `docs/development/files.md` when paths or data files matter |
| File utilities and mod-owned files | `docs/development/files.md` | `docs/development/config.md` when configuration is involved |
| Input and keybindings | `docs/development/input.md` | `docs/development/mod.md` for registration context |
| Localization and translations | `docs/development/localization.md` | `docs/development/files.md` for resource paths |

Table is route, not replacement API reference. Agent MUST confirm version-sensitive
signatures and behavior against actual referenced assembly and matching
source before writing code.

## Advanced and archived topics

Agent MUST load these pages only when task names topic or stable route points
to it. upstream index currently labels them `Services (Archive)`:

| Topic | First page | Handling |
| --- | --- | --- |
| Console commands | `docs/development/console.md` | Read on demand; verify current command types in source |
| Custom items | `docs/development/items.md` | Read on demand; verify current item APIs in source |
| Level modifications | `docs/development/levels.md` | Read on demand; label active-development behavior as version-sensitive |
| Custom penitences | `docs/development/penitence.md` | Read on demand; verify current types in source |

For topic absent from both tables, agent MUST use selected reference's
`docs/development/main.md` as index, follow exact linked page on demand,
and record resolved reference before relying on its guidance. Agent MUST NOT copy
upstream documentation tree into this Skill.

## Game-source separation

Agent MUST keep two source routes distinct:

- ModdingAPI API, lifecycle, logging, and framework behavior MUST use release-aware reference route.
- Decompiled Blasphemous game classes MUST use
  [Blasphemous Source Code Navigation](../source_code_navigation/MAIN.md) and
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
defined in [preferences-schema.md#resolver-fixture-contract](../config/preferences-schema.md#resolver-fixture-contract).
The smoke check consumes that contract and never presents fixture data as live
Release metadata.

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
`manage_modding_api.py` owns check/update behavior. Its compatibility wrappers
expose the existing operation model:

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
`modding_api_reference_selector` from selected preferences file, unless
`--target-path`/`-TargetPath` or `--selector`/`-Selector` is supplied. It also
accepts same `--scope`/`-Scope` and `--preferences-file`/`-PreferencesFile`
options as fresh-clone command. When none of those three routing options
is supplied, it uses active preferences context selected by [Invocation
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
game-source boundary, and both preferences outcomes: configured local path
selects local route, while skipped local setup selects release-aware
remote route. It also reports the selected preference selector, local lock
selector, local lock version, remote preference/resolution version, matching
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
