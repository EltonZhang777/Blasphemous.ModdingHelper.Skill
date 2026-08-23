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
