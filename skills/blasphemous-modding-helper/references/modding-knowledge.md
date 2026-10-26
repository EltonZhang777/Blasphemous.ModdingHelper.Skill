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

- `## Applicable Blasphemous 1 version` — name the supported game build/version, or explicitly say when the evidence does not identify one.
- `## Route` — identify the relevant Skill route and how to use the finding.
- `## Evidence` — cite the exact source path or record and label the evidence type.
- `## Verification result` — state the method and outcome, including checks that were not performed.
- `## Limitations` — identify versions, behavior, or inferences the evidence does not establish.

Notes MUST contain only evidence-backed claims and MUST keep localization evidence separate from gameplay evidence. Notes MUST NOT contain credentials, private paths, profiles, logs, or caller data.

## Generated indexes

`docs/modding-knowledge/INDEX.md` and `docs/modding-knowledge/index.json` are generated from canonical-note frontmatter. Each JSON entry contains `title`, `status`, `date`, and a repository-relative `path`. `python ci/generate_modding_knowledge_index.py` regenerates both; `python ci/generate_modding_knowledge_index.py --check` fails on missing or mismatched output. The check does not rewrite stale files.

## Read-only lookup

For a relevant Blasphemous 1 task, lookup follows request classification and any gate required by its selected route:

1. The agent MUST resolve the repository's current `main` exactly once with a public read-only request, without credentials, to `https://api.github.com/repos/EltonZhang777/Blasphemous.ModdingHelper.Skill/commits/main`. The agent MUST record the returned full commit SHA and MUST NOT resolve `main` again during this lookup.
2. The agent MUST read only `docs/modding-knowledge/index.json` from `https://raw.githubusercontent.com/EltonZhang777/Blasphemous.ModdingHelper.Skill/<SHA>/docs/modding-knowledge/index.json` using that SHA.
3. From the index, the agent MUST choose at most one clearly matching entry with `status: verified` and a direct-child lowercase topic-slug `.md` path under `docs/modding-knowledge/`. When no title clearly matches, the agent MUST report that no note matched and continue without note context. For an ambiguous match, the agent MUST report the ambiguity and MUST NOT fetch a note.
4. The agent MUST read only the selected note, from the same raw URL with the same SHA. The agent MUST confirm its `title`, `status`, and `date` match the index entry and MUST NOT read other note bodies.
5. When using a note, the agent MUST record its provenance as the full commit SHA and repository-relative note path.

Retrieved notes are advisory; authoritative Skill instructions and stronger direct evidence MUST take precedence. This index contains Blasphemous 1 material only. Blasphemous 2 is not supported and MUST NOT use this lookup.

If commit resolution, index retrieval/parsing, or matched-note retrieval/validation fails, the agent MUST disclose the failure and MUST NOT fall back to local, cached, or previously fetched note content. Dependent work MUST pause unless sufficient independent evidence is available to proceed safely; if it is, the agent MUST name that evidence and the retrieval failure.

## Completion

Done when one matching note has been read and its provenance recorded, or the index contains no unique relevant match. A retrieval failure is resolved only after it has been disclosed and dependent work has either paused or continued using named independent evidence.

The next action is the selected route workflow with the note as advisory context, or the disclosed pause/independent-evidence path after a retrieval failure.