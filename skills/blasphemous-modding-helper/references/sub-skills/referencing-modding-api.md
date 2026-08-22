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
checkout pinned to the stored selector:

- Bash: `scripts/clone_modding_api.sh`
- PowerShell: `scripts/clone_modding_api.ps1`

Tags and commits are detached; explicit branches track their corresponding
`origin/<branch>`. Existing targets are not replaced. Update, lock, and
offline lifecycle behavior belongs to the later lifecycle specification; this
sub-skill only defines how to choose the reference for the current task.
