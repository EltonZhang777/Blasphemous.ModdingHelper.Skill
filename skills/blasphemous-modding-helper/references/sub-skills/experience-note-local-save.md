# Experience note local save

This reference owns user approval and local storage for unique Blasphemous 1 experience-note candidates. It follows [Invocation preflight](../config/invocation-preflight.md), reuses the note lifecycle in [Modding knowledge](../modding-knowledge.md) and the read-only outcome from [Experience note comparison](experience-note-comparison.md), and does not authorize a pull request.

## Eligibility and review

- Only a `unique` candidate returned by a completed comparison may enter this workflow. Exact duplicates, deferred candidates, stale notes, conflicts, and Blasphemous 2 findings MUST NOT be offered for saving.
- At task end, the main task MUST present every unique candidate together in one batch, including the exact full Markdown content proposed for each local note.
- Each candidate MUST receive its own explicit yes/no question. Approval of one note MUST NOT approve another. A clear yes for a specific note is required; no, an unclear response, or silence means that note is not saved.
- The exact content shown for a note MUST be the content saved. If it needs to change after approval, the main task MUST show the changed content and ask again for that note's approval.
- The main task MUST finish its requested work and review the comparison results before presenting the batch. It MUST NOT wait for candidate approval to finish unrelated task work.

## Note content and storage

Each proposed note MUST use a lowercase topic-slug `.md` filename that is not a Windows-reserved device name, and the canonical three-field frontmatter, with `status: candidate`. The body MUST contain non-empty sections for the finding, applicable Blasphemous 1 version, route, evidence, reproduction steps, verification result, and limitations. The evidence section MUST identify and summarize the evidence source. The version section MUST say when the version is unknown. The date MUST represent when the current evidence was verified, not merely when the note was saved.

Before showing the note, the main task MUST generalize the finding and remove raw logs or configuration, credentials, personal or machine identifiers, and absolute paths. Evidence references MUST use safe source identifiers, repository-relative paths, or public URLs. Reproduction steps MUST be sufficient to repeat the observation, or state why the available evidence cannot be reproduced.

After a specific yes, the main task MUST pass the `config.yml` path already selected by invocation preflight to `scripts/save_experience_note.py`. The note is stored at `<selected-config-directory>/modding-knowledge/<topic-slug>.md`; the selected config's parent is the Skill configuration directory. When both project and user configuration exist, invocation preflight selects project scope. The save workflow MUST consume that selected path and MUST NOT search for another configuration file. It MUST NOT overwrite an existing note. If a target already exists or cannot be written, report the failure without changing that file.

The script accepts the proposed note on standard input and writes only when both `--comparison-outcome unique` and `--decision yes` are supplied. A no, unclear response, silence, or missing decision MUST NOT invoke it. The script contains no pull-request operation: local-save approval MUST NOT be treated as permission to create or propose a pull request.

The main task MUST use the resolved Python interpreter and installed Skill root from invocation preflight, with the caller's Mod repository as the current directory:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/save_experience_note.py" --preferences-file "$PREFERENCES_FILE" --slug topic-slug --comparison-outcome unique --decision yes <<'NOTE'
<exact approved note content>
NOTE
```

```powershell
@'
<exact approved note content>
'@ | & $PYTHON3 (Join-Path $SkillRoot 'scripts\save_experience_note.py') --preferences-file $PreferencesFile --slug topic-slug --comparison-outcome unique --decision yes
```

The main task MUST NOT invoke the save command for declined or unapproved candidates. Saving one or more local notes completes this workflow; it does not start publication review.

## Completion criteria

Done when all unique candidates have been shown together, each has a separate decision, every explicit yes has been saved under the selected configuration directory, and no other candidate has been written. The main task MUST report saved filenames and any declined or failed saves. If no unique candidates remain, the main task MUST NOT prompt for approval.

The next action is to finish the main task. Local notes remain candidate material outside the repository's canonical indexes and read-only lookup until maintainer review.
