# Blasphemous 1 modding knowledge

This is the sole authority for the base note contract and the Skill's read-only lookup. Notes are advisory and MUST NOT replace route-specific Skill instructions or direct source, runtime, or gameplay evidence.

## Canonical note contract

Canonical notes MUST live directly under `docs/modding-knowledge/` in lowercase topic-slug `.md` files. The YAML frontmatter MUST contain exactly these three one-line fields, in this order, using plain scalar values:

```yaml
---
title: A concise topic title
status: verified
date: YYYY-MM-DD
---
```

`status` MUST be one of `candidate`, `verified`, `superseded`, or `withdrawn`. The `date` records when the current evidence was last verified. Generated indexes MUST include verified canonical notes and MUST exclude all other statuses. Candidate material belongs under `docs/modding-knowledge/candidates/` and stays outside the normal index and retrieval flow.

The note body MUST include non-empty sections for:

- `## Applicable Blasphemous 1 version` and `## Applicable Mod version` — each section's first non-empty line MUST start with `Version:` and name the supported build/version or explicitly say `unknown` or `not applicable`; name the Mod when one applies.
- `## Route` — identify the relevant Skill route and how to use the finding.
- `## Evidence` — cite each exact source path or record on its own line beginning with `Static source inspection:`, `Runtime evidence:`, `Manual/in-game evidence:`, or `Localization evidence:` as applicable.
- `## Verification result` — state the method and outcome, including checks that were not performed.
- `## Evidence history` — include dated verification/correction entries; later corrections MUST be appended without removing earlier evidence history.
- `## Limitations` — identify versions, behavior, or inferences the evidence does not establish.

Notes MUST contain only evidence-backed claims and MUST keep localization evidence separate from gameplay evidence. Notes MUST NOT contain credentials, private paths, profiles, logs, or caller data.

## Versioned evidence and screenshots

Agents MUST compare a note's game version, Mod version, route, and task with the user's request and environment before applying its claims. A note MUST state exact versions or explicitly mark a version unknown or not applicable. If its evidence does not cover the user's version or task, the agent MUST say so and MUST NOT present the claim as verified for that case. The agent MUST use the selected route's direct evidence or report what remains unverified. Blasphemous 1 notes MUST NOT be applied to Blasphemous 2.

Evidence labels MUST remain distinct: static source inspection establishes what the inspected source says; runtime evidence establishes only the observed runtime output; manual/in-game evidence establishes the observed gameplay result; localization evidence establishes text in the cited localization source. Short evidence excerpts MAY quote cited source or localization text, but MUST NOT reproduce logs; log observations MUST be paraphrased or supported by a screenshot. Logs alone MUST NOT be presented as gameplay proof. The verification result MUST identify its method and outcome and name unperformed checks.

Dated corrections MUST preserve earlier entries and their evidence. When behavior materially differs by game or Mod version, the note MUST scope the behavior explicitly or use separate notes.

Notes MAY include relevant screenshots of Blasphemous 1 gameplay, BepInEx console output, error dialogs, or other supporting pages. Candidate screenshots MUST be stored under `docs/modding-knowledge/screenshots/` and linked from a candidate note with a relative Markdown image link whose destination is `../screenshots/<topic>/gameplay.png`. Each PNG, JPEG, or WebP file MUST be strictly smaller than 1.5 MiB. Promotion normalizes the link to `screenshots/<topic>/gameplay.png` when the note moves to the canonical directory. Screenshot preflight requires the optional maintainer dependency in `ci/requirements-image-validation.txt`; it fully decodes each file and checks the format against its extension. Screenshots MUST be minimally cropped to retain relevant context and MUST follow the same privacy and redaction rules as inline evidence: remove credentials, private/user-specific paths, and unrelated caller-owned data. Human review MUST confirm the redactions; the workflow MUST NOT redact automatically. Standalone extracted game assets and raw log attachments remain prohibited.

## Candidate review and promotion

These maintainer commands run from the Skill source repository root; their `ci/` scripts are not included in the installed Skill. Resolve Python 3 as `PYTHON3` using [Python Runtime](config/python-runtime.md), then replace `<python3>` below with `& $PYTHON3` in PowerShell or `"$PYTHON3"` in Bash.

Prepare unapproved notes only as direct-child Markdown files under `docs/modding-knowledge/candidates/`, with `status: candidate`. Run the local preflight against the exact note paths or named batch:

```text
<python3> ci/modding_knowledge_candidates.py preflight docs/modding-knowledge/candidates/<topic>.md
```

Preflight reuses the canonical note parser and checks the candidate path and lifecycle state, evidence sections and dated history, screenshot links, local image files and size limit, obvious private paths and credentials, BepInEx-style `[level: source]` and timestamped severity lines (including common Markdown wrappers), and links to raw logs, game files, extracted assets, decompiled dumps, ROMs, or ISOs. It warns when a fenced code block exceeds 60 lines or a note exceeds 120 KiB, and rejects a fenced block over 150 lines. Preflight does not modify notes or indexes. Candidates remain outside the canonical index and read-only lookup.

Before promotion, inspect the exact candidate content, each screenshot's path, size, and digest, and the proposed generated indexes together:

```text
<python3> ci/modding_knowledge_candidates.py review docs/modding-knowledge/candidates/<topic>.md
```

For a named batch, pass every approved note path explicitly. The review output shows each note unchanged, its digest, and the generated `INDEX.md` and `index.json` diffs for that exact set. A human reviewer MUST check evidence accuracy, limitations, caller data, and the presence and adequacy of privacy redactions. The workflow does not apply or remove redactions automatically.

Promotion requires explicit human approval for exactly the reviewed note or batch:

```text
<python3> ci/modding_knowledge_candidates.py promote --approve --review-sha256 <review-sha256> docs/modding-knowledge/candidates/<topic>.md
```

Without `--approve`, or without the matching `--review-sha256` printed by `review`, promotion fails without writing. The digest binds the exact candidate contents and both proposed indexes, so a changed note or index requires another review. Promotion also requires the current generated indexes to be consistent, validates the complete selected set before writing, creates canonical copies with `status: verified`, and regenerates both indexes from verified canonical notes. If the current indexes are stale, regenerate them and repeat the exact review before approval. The original candidate drafts remain unchanged and excluded from retrieval. The command has no all-candidates mode and does not commit, push, or publish.

## Generated indexes

`docs/modding-knowledge/INDEX.md` and `docs/modding-knowledge/index.json` are generated from canonical-note frontmatter. Each JSON entry contains `title`, `status`, `date`, and a repository-relative `path`. `<python3> ci/generate_modding_knowledge_index.py` regenerates both; `<python3> ci/generate_modding_knowledge_index.py --check` fails on missing or mismatched output. The check does not rewrite stale files.

## Read-only lookup

For an operational Blasphemous 1 modding task, lookup follows request classification and any gate required by its selected route. The read-only Localization lookup route follows [Invocation preflight](config/invocation-preflight.md) and MUST NOT use this workflow. The agent MUST use the resolved Python interpreter and installed Skill root from invocation preflight. The lookup script makes public unauthenticated GET requests only and does not cache or write retrieved content.

1. The agent MUST resolve the repository's current `main` exactly once and read its index with the lookup command:

   ```bash
   "$PYTHON3" "$SKILL_ROOT/scripts/modding_knowledge_lookup.py" resolve
   ```

   ```powershell
   & $PYTHON3 (Join-Path $SkillRoot 'scripts\modding_knowledge_lookup.py') resolve
   ```

   The command reads only `docs/modding-knowledge/index.json` after resolving `main`, then returns the full commit SHA and verified index metadata without reading note bodies. The agent MUST retain that SHA for the rest of the lookup and MUST NOT resolve `main` again.
2. From the returned index, the agent MUST choose at most one clearly matching entry with `status: verified` and a direct-child lowercase topic-slug `.md` path under `docs/modding-knowledge/`. When no title clearly matches, the agent MUST report that no note matched and continue without note context. For an ambiguous match, the agent MUST report the ambiguity and MUST NOT fetch a note.
3. For one selected entry, the agent MUST fetch only that note with the exact SHA, path, title, and date returned by the index:

   ```bash
   "$PYTHON3" "$SKILL_ROOT/scripts/modding_knowledge_lookup.py" note --commit-sha "$COMMIT_SHA" --path "$INDEX_PATH" --title "$INDEX_TITLE" --date "$INDEX_DATE"
   ```

   ```powershell
   & $PYTHON3 (Join-Path $SkillRoot 'scripts\modding_knowledge_lookup.py') note --commit-sha $CommitSha --path $IndexPath --title $IndexTitle --date $IndexDate
   ```

   The command confirms the note's `title`, `status`, and `date` against the index and returns the note with its full SHA and repository-relative path. The agent MUST NOT read other note bodies.
4. When using a note, the agent MUST record its provenance as the full commit SHA and repository-relative note path.

Retrieved notes are advisory; authoritative Skill instructions and stronger direct evidence MUST take precedence. This index contains Blasphemous 1 material only. Blasphemous 2 is not supported and MUST NOT use this lookup.

If a lookup command exits unsuccessfully during commit resolution, index retrieval/parsing, or matched-note retrieval/validation, the agent MUST disclose the reported failure and MUST NOT fall back to local, cached, or previously fetched note content. Dependent work MUST pause unless sufficient independent evidence is available to proceed safely; if it is, the agent MUST name that evidence and the retrieval failure.

## Completion

Done when one matching note has been read and its provenance recorded, or the index contains no unique relevant match. A retrieval failure is resolved only after it has been disclosed and dependent work has either paused or continued using named independent evidence.

The next action is the selected route workflow with the note as advisory context, or the disclosed pause/independent-evidence path after a retrieval failure.
