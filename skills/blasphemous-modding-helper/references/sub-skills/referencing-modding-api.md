# Referencing ModdingAPI

Use this sub-skill whenever a task needs ModdingAPI documentation, source
guidance, or coding conventions. Resolve the reference before browsing it.

## Reference selection

1. Read the selected `preferences.md`.
2. If `modding_api_reference_path` is present, use that local checkout. The
   path is authoritative for the task; do not clone or update it during an
   ordinary question. If its selector is absent, treat it as `latest` for
   explicit local-reference lifecycle commands.
3. If the local fields are absent, use the release-aware remote fallback below.
   This is valid for legacy preferences and for a first-time setup where the
   user selected **Skip** for the local checkout.

The optional fields, normalized-path rule, and approved user/project scope
locations are defined in [preferences-schema.md](../config/preferences-schema.md).
The explicit local-checkout setup flow is in
[first-time-setup.md#q6-local-moddingapi-reference](../config/first-time-setup.md#q6-local-moddingapi-reference).

## Routing contract

The selected reference is the sole ModdingAPI authority for the task. Start at
the upstream development index and follow only the linked page needed for the
question:

- Local checkout: `<modding_api_reference_path>/docs/development/main.md`.
- Remote fallback: `<MODDING_API_DOCS_URL>/development/main.md`, where
  `MODDING_API_DOCS_URL` comes from the resolver for the selected reference.

The `main.md` name identifies the documentation index. It is not a request to
read an unqualified Git branch. The resolver's tag, branch, or commit remains
part of every remote URL and every local-reference decision.

## Stable API topic routing

Use this table as the first route for ordinary ModdingAPI work. Open the
selected reference's `docs/development/main.md`, then load the named page and
any directly linked page required by the question.

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

The table is a route, not a replacement API reference. Confirm version-sensitive
signatures and behavior against the actual referenced assembly and matching
source before writing code.

## Advanced and archived topics

Load these pages only when the task names the topic or the stable route points
to it. The upstream index currently labels them `Services (Archive)`:

| Topic | First page | Handling |
| --- | --- | --- |
| Console commands | `docs/development/console.md` | Read on demand; verify current command types in source |
| Custom items | `docs/development/items.md` | Read on demand; verify current item APIs in source |
| Level modifications | `docs/development/levels.md` | Read on demand; label active-development behavior as version-sensitive |
| Custom penitences | `docs/development/penitence.md` | Read on demand; verify current types in source |

For a topic absent from both tables, use the selected reference's
`docs/development/main.md` as an index, follow the exact linked page on demand,
and record the resolved reference before relying on its guidance. Do not copy
the upstream documentation tree into this Skill.

## Game-source separation

Keep the two source routes distinct:

- ModdingAPI API, lifecycle, logging, and framework behavior use this
  release-aware reference route.
- Decompiled Blasphemous game classes use
  [Blasphemous Source Code Navigation](../source_code_navigation/MAIN.md) and
  its source-analyzer branch.

A task may load both routes when it compares framework behavior with a game
class, but each claim must remain tied to the route that owns it.

## Release-aware remote fallback

The official upstream is
`https://github.com/BrandenEK/Blasphemous.ModdingAPI.git`. Resolve the remote
reference before opening documentation or source:

```bash
bash scripts/resolve_modding_api.sh --selector latest
```

```powershell
& .\scripts\resolve_modding_api.ps1 -Selector latest
```

Use the resolver's `MODDING_API_DOCS_URL` and `MODDING_API_SOURCE_URL` outputs
for remote browsing. The `latest` selector is resolved from the official
GitHub Releases endpoint and accepts only the newest non-draft,
non-prerelease Release. It does not silently use `main` or another moving
branch. If the user deliberately selected a different reference, pass exactly
one of:

- `tag:REF` for a named Git tag;
- `branch:REF` for an explicit branch, including `branch:main` when requested;
- `commit:SHA` for an exact 40-character commit.

Both resolver scripts emit the same `MODDING_API_*` fields. A nonzero exit
prints a terminal `[ERROR REPORT]` with the cause and next step. Preserve that
report, do not invent a URL, and ask for a corrected selector, local checkout,
or a retry when the Release lookup fails.

## Local checkout use

When setup succeeds, use the stored absolute path for documentation and source
lookups. The fresh-clone commands are explicit operations and create a shallow
checkout pinned to the stored selector. They also write the sibling lock state
`<reference-path>.lock`; the lock is outside the checkout and records the
selector, resolved tag, resolved commit, check time, and supported repository:

- Bash: `scripts/clone_modding_api.sh`
- PowerShell: `scripts/clone_modding_api.ps1`

Tags and commits are detached; explicit branches track their corresponding
`origin/<branch>`. Existing targets are not replaced.

## Explicit lifecycle operations

Use the lifecycle manager only when the user explicitly asks to check or
update a local checkout. Ordinary ModdingAPI questions must not mutate the
checkout. The shared `scripts/clone_modding_api.js` and
`scripts/manage_modding_api.js` implementations own clone and lifecycle
behavior; Bash and PowerShell expose thin equivalent entry points. Both
script surfaces expose the same operation model:

```bash
bash scripts/manage_modding_api.sh --operation check
bash scripts/manage_modding_api.sh --operation update
bash scripts/manage_modding_api.sh --operation update --dry-run
bash scripts/manage_modding_api.sh --operation check --offline
```

```powershell
& .\scripts\manage_modding_api.ps1 -Operation check
& .\scripts\manage_modding_api.ps1 -Operation update
& .\scripts\manage_modding_api.ps1 -Operation update -DryRun
& .\scripts\manage_modding_api.ps1 -Operation check -Offline
```

The manager reads `modding_api_reference_path` and
`modding_api_reference_selector` from the selected preferences file, unless
`--target-path`/`-TargetPath` or `--selector`/`-Selector` is supplied. It also
accepts the same `--scope`/`-Scope` and `--preferences-file`/`-PreferencesFile`
options as the fresh-clone command. When none of those three routing options
is supplied, it discovers project preferences in the current directory first,
then user preferences; an explicit scope always selects its approved path.

`check` resolves the requested selector, verifies a clean worktree and the
official origin, confirms the checkout shape and current HEAD, and writes a
fresh lock state when the checkout matches. `update` is the only operation
that fetches and changes a checkout: fixed references fetch the resolved
commit and remain detached; explicit branches fetch their remote-tracking
branch and advance only with a fast-forward. A dirty worktree, invalid
repository, wrong origin, divergent history, wrong checkout shape, or missing
reference stops before destructive recovery. The manager never resets,
stashes, deletes, or replaces a checkout. A shallow branch checkout may be
deepened during update so Git can prove that the fast-forward is safe; fixed
reference updates remain shallow by default.

`--dry-run` resolves and validates the planned operation but performs no
fetch, checkout, merge, or lock-state write. A matching `check --offline`
uses only the sibling lock and local Git state; it succeeds only when the
selector, resolved commit/tag, origin, clean worktree, checkout shape, and
current HEAD agree. For a branch dry-run whose local remote-tracking ref is
absent, the operation remains non-mutating and emits
`MODDING_API_PLAN_REQUIRES_FETCH=true`. An offline update fails because it
cannot refresh the reference. If an online `check` loses network access, it may fall back to
that same matching lock validation; missing or mismatching offline state is
an error and must not be presented as a verified version.

Exit codes are stable across Bash and PowerShell: `0` means success, `2`
means usage or configuration failure, and `1` means a runtime, Git, network,
offline, or reference-state failure. Every failure prints a terminal text
`[ERROR REPORT]` containing `operation`, `target_path`, `selector`,
`current_head`, `worktree_state`, `network_state`, `cause`, and `next_step`.

## Documentation smoke check

Run the deterministic documentation smoke check from the skill directory:

```bash
bash scripts/test_referencing_modding_api.sh
```

```powershell
& .\scripts\test_referencing_modding_api.ps1
```

It verifies the top-level pointer, the stable and archived route tables, the
game-source boundary, and both preferences outcomes: a configured local path
selects the local route, while skipped local setup selects the release-aware
remote route.

## Cross-platform acceptance gate

Run the deterministic acceptance gate before publishing changes to the
reference workflow:

```bash
bash scripts/test_modding_api_acceptance.sh
```

```powershell
& .\scripts\test_modding_api_acceptance.ps1
```

The gate runs the resolver, clone, lifecycle, and documentation suites through
both Bash and PowerShell. Their fixture scenarios cover annotated tags,
branches, exact commits, clean updates, dirty worktrees, wrong origins,
missing references, network failure, offline locks, output fields, and exit
codes. It also checks resolver parity, installer dry-runs, local Markdown links,
and `git diff --check`. It never contacts GitHub and never uses a user's
reference checkout.

The final verification invocation may require a clean worktree:

```bash
bash scripts/test_modding_api_acceptance.sh --require-clean
```

```powershell
& .\scripts\test_modding_api_acceptance.ps1 -RequireClean
```

The live network check is separate and manual. It resolves the actual latest
non-draft, non-prerelease Release through both script surfaces, compares the
resolved tag and commit, and verifies tag-specific documentation and source
URLs:

```bash
bash scripts/test_modding_api_live.sh
```

```powershell
& .\scripts\test_modding_api_live.ps1
```

Run the live check only when network access is available. A failure is not a
reason to substitute `main`; preserve the resolver error report and retry or
use an explicit selector.
