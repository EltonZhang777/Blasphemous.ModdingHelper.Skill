# Unity project navigation acceptance

This record separates the synthetic Unity navigation suite from the opt-in real exported project gate. A synthetic pass MUST NOT be reported as real-project evidence. A missing or unreadable real export is `blocked`, not passed.

## Synthetic gate

The synthetic gate uses fixtures and does not require a game export:

```text
<python3> tests/test_modding_api_acceptance.py
```

The full repository suite covers configuration, project summary, asset and GUID lookup, complete and standalone scene sets, flattened Prefabs, script assets, serialized references, and direct component-script bindings. The seven navigation topics are `topology.md`, `assets-and-guids.md`, `scripts.md`, `scenes.md`, `prefabs.md`, `component-relations.md`, and `bindings.md`.

The synthetic result remains a fixture result even when every test passes. It does not prove the supplied export has the expected topology.

## Real-project gate

Provide the UTinyRipper export through `--project` or `BLASPHEMOUS_UNITY_PROJECT_PATH`, then run:

```text
<python3> tests/run_unity_real_project_acceptance.py --project <UNITY_PROJECT_ROOT>
```

PowerShell:

```powershell
& $PYTHON3 tests\run_unity_real_project_acceptance.py --project '<UNITY_PROJECT_ROOT>'
```

The operator-local manifest is `tests/fixtures/unity-real-project-smoke.json`; it is ignored and MUST NOT be committed. It locks the Unity version, real-tree counts, fixed sample identities, the component-binding census aggregate, and the representative files used for content hashing. The committed `tests/fixtures/unity-real-project-smoke.example.json` documents the required shape with placeholders and aggregate counts only.

The runner exits with:

- `0` when every real-project assertion and read-only check passes.
- `2` with `status: "blocked"` when the export is missing, unreadable, lacks `Assets`, or lacks `ProjectSettings/ProjectVersion.txt`.
- `1` with `status: "failed"` when the export is readable but baseline counts, fixed identities, query evidence, or read-only evidence drift.

The JSON report names `evidence_mode: "real_project"` and records the exact scanner commands, statuses, completion evidence, blocked reason when applicable, and next action. When a project is supplied, public project-root fields use `.` and omit the absolute export location; a run without a supplied project reports `null`. Synthetic evidence is named separately and is never substituted for a blocked real run.

## Full binding census

The default real-project gate is a bounded smoke and does not run the complete binding census. Run the acceptance census only with explicit authorization:

```powershell
& $PYTHON3 tests\run_unity_real_project_acceptance.py --project '<UNITY_PROJECT_ROOT>' --bindings-census
```

The census uses only the public `bindings` command. One opt-in `--census-summary` scan MUST report `status: "ok"` and `scan_coverage: "complete"`. The summary MUST return aggregate counts and deterministic samples from the same full scan without following the complete cursor chain.

Census mode runs the project summary, the full binding census, and the before-and-after read-only gate. It does not rerun the unrelated scene, Prefab, GUID, script-asset, or serialized-reference smoke chains. Those remain owned by the default real-project smoke.

The report records the Unity version, Skill and schema versions, invocation parameters, UTC start and end timestamps, a path-free snapshot identifier, source-file candidate counts, binding row counts by source kind, reference shape, target category, target-asset resolution, target-object resolution, warning counts, and all page statuses and coverage states. Aggregate counts are compared with the reviewed manifest.

The census selects deterministic first matches for a C# target, a DLL target, an unresolved target, a null reference, a non-typical script file ID, an `.asset` source, malformed evidence when present, and a `Packages` binding when package source candidates exist. Each sample is checked for the expected binding-chain state. A state absent from the export is reported as not observed instead of fabricated.

The page benchmark separately runs the first and second page at the default 200-row limit and at the maximum 1000-row limit. Each run records the UTF-8 serialized byte size, elapsed time, cursor presence, and a changed boundary identity. The benchmark does not follow the complete cursor chain.

The local report can contain real project-relative sample paths so the operator can inspect the selected chains. Do not commit or upload those paths, sample GUID hashes, asset copies, or the raw acceptance log. Publish only aggregate counts, statuses, timestamps, page sizes, and the path-free snapshot identifier.

## Real baseline

| Evidence | Expected |
| --- | --- |
| Unity version | `2017.4.40f1` |
| Files under `Assets` | 94,153 |
| Scanner total including included `Packages` files | 94,154 |
| `.unity` files | 1,970 |
| `.prefab` files | 729 |
| `.asset` files | 32,617 |
| `.cs` files | 5,308 |
| `.meta` files | 47,685 |
| Complete five-layer scene sets | 393 |
| Incomplete scene sets | 0 |
| Standalone scenes | 5 |
| Binding rows | 75,147 |
| Binding sources: scenes / Prefabs / assets | 69,267 / 4,803 / 1,077 |
| Structured / null / malformed references | 75,146 / 1 / 0 |
| C# / DLL / unresolved / null / malformed targets | 68,660 / 2,356 / 4,130 / 1 / 0 |
| Distinct / non-typical `m_Script.fileID` values | 50 / 6,484 rows |

The operator-local manifest selects one complete five-layer scene set, one standalone scene, one flattened Prefab, one script asset, one GUID lookup, one outgoing serialized-reference chain, and the representative files used for content hashing. Those identities remain local and are not part of this record.

## Read-only evidence

The runner snapshots the complete project path inventory before and after all queries. It fails if any file or directory is added or removed. The full binding census runs inside the same before-and-after inventory window. The runner also hashes every representative queried file, including `.meta` evidence, before and after; a content change fails the gate. The navigation command contract remains read-only; the gate does not hash every project file outside the fixed representative set.

## Current record

Observed on 2026-11-16 on native Windows with the supplied export:

- Assets inventory: 94,153 files.
- Unity version: `2017.4.40f1`.
- Complete scene sets: 393; standalone scenes: 5.
- Real-project extra-file count after the smoke: 0.
- Representative file content changes after the smoke: 0.
- Full binding census: passed with one `--census-summary` scan in 40.53 seconds: 75,147 rows, 35,316 candidate source files, and `scan_coverage: "complete"`.
- Snapshot identifier: `5272524ba74c0570e2e80643c735a04ccc7f1e19e172c92d13a871e2f5730c02`.
- 200-row benchmark: 126,820 UTF-8 bytes, first page 43.52 seconds, second page 46.76 seconds, changed boundary identity.
- 1,000-row benchmark: 628,184 UTF-8 bytes, first page 61.84 seconds, second page 51.30 seconds, changed boundary identity.
- Read-only census check: no added or removed paths and no representative content changes.

The real-project report is separate from the synthetic suite and does not claim C# behavior, runtime state, or gameplay.

The real report is asset and serialized evidence only. C# behavior, dependencies, and class semantics remain owned by the [Source Analyzer](../../skills/blasphemous-modding-helper/references/sub-skills/source-analyzer.md); a Unity `.cs` file is not behavioral proof.

## Completion criteria

Real-project acceptance is complete only when the synthetic suite passes separately, the real runner exits `0`, the full path inventory is unchanged, every representative hash is unchanged, and the report names the commands, evidence, and next action. Component-binding acceptance additionally requires one opt-in census summary to complete with full coverage, match the aggregate baseline, cover every observed sample state, record both two-page benchmarks, and leave the project path inventory unchanged. A blocked, timed-out, partial, or failed real run remains incomplete.

## Next action

For `blocked`, provide a readable export containing `Assets` and `ProjectSettings/ProjectVersion.txt`, then rerun. For `failed`, inspect the first failed baseline, query identity, sample chain, or cursor transition and update the export or the reviewed manifest deliberately; do not weaken the gate and do not report the synthetic suite as real evidence. A timeout or partial scan is not a complete census.
