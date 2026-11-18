# Unity project navigation acceptance

This record separates the synthetic Unity navigation suite from the opt-in real exported project gate. A synthetic pass MUST NOT be reported as real-project evidence. A missing or unreadable real export is `blocked`, not passed.

## Synthetic gate

The synthetic gate uses fixtures and does not require a game export:

```text
<python3> tests/test_modding_api_acceptance.py
```

The full repository suite covers configuration, project summary, asset and GUID lookup, complete and standalone scene sets, flattened Prefabs, script assets, and serialized references. The six navigation topics are `topology.md`, `assets-and-guids.md`, `scripts.md`, `scenes.md`, `prefabs.md`, and `component-relations.md`.

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

The fixed manifest is `tests/fixtures/unity-real-project-smoke.json`. It locks the Unity version, real-tree counts, one complete five-layer scene set, one standalone scene, one flattened Prefab, one script asset, one GUID lookup, one outgoing serialized-reference chain, one incoming local-reference edge, both source and target identities for every fixed edge, and the representative files used for content hashing.

The runner exits with:

- `0` when every real-project assertion and read-only check passes.
- `2` with `status: "blocked"` when the export is missing, unreadable, lacks `Assets`, or lacks `ProjectSettings/ProjectVersion.txt`.
- `1` with `status: "failed"` when the export is readable but baseline counts, fixed identities, query evidence, or read-only evidence drift.

The JSON report names `evidence_mode: "real_project"` and records the exact scanner commands, statuses, completion evidence, blocked reason when applicable, and next action. Synthetic evidence is named separately and is never substituted for a blocked real run.

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

The fixed smoke resolves:

- Complete scene set `D01BZ01S01` with 1,599 objects and 9,037 references.
- Standalone scene `Assets/#Design/Scenes/Platform/Preload_Windows.unity` with 5 objects and 21 references.
- Flattened Prefab `Assets/Resources/inventory/questitem/QI78.prefab` with GUID `01ed6fc6d86656c449f2e9902e9bbb8a`.
- Script asset `Assets/Plugins/Assembly-CSharp-firstpass/BaseCRTEffect.cs` with no C# parsing.
- GUID lookup from `01ed6fc6d86656c449f2e9902e9bbb8a` to the QI78 Prefab.
- Outgoing serialized-reference chain from QI78 object `114940650439655525` through `Assets/Sprite/qi78.asset` to the texture reference in `Assets/Texture2D/items-icons-spritesheet.png`.
- Incoming local `m_Component.component` edge from QI78 object `1810135827502625` to object `114940650439655525`.

## Read-only evidence

The runner snapshots the complete project path inventory before and after all queries. It fails if any file or directory is added or removed. It also hashes every representative queried file, including `.meta` evidence, before and after; a content change fails the gate. The navigation command contract remains read-only; the gate does not hash every project file outside the fixed representative set.

## Current record

Observed on 2026-11-17 on native Windows with the supplied export:

- Assets inventory: 94,153 files.
- Unity version: `2017.4.40f1`.
- Complete scene sets: 393; standalone scenes: 5.
- Real-project extra-file count after the smoke: 0.
- Representative file content changes after the smoke: 0.
- Outgoing reference query: `ok`, complete, 7 nodes and 9 edges; no timeout or limit.
- Incoming reference query: `ok`, complete, 2 nodes and 1 local edge; no timeout or limit.

The real-project report is separate from the synthetic suite and does not claim C# behavior, runtime state, or gameplay.

The real report is asset and serialized evidence only. C# behavior, dependencies, and class semantics remain owned by the [Source Analyzer](../../skills/blasphemous-modding-helper/references/sub-skills/source-analyzer.md); a Unity `.cs` file is not behavioral proof.

## Completion criteria

Real-project acceptance is complete only when the synthetic suite passes separately, the real runner exits `0`, the full path inventory is unchanged, every representative hash is unchanged, and the report names the commands, evidence, and next action. A blocked or failed real run remains incomplete.

## Next action

For `blocked`, provide a readable export containing `Assets` and `ProjectSettings/ProjectVersion.txt`, then rerun. For `failed`, inspect the first failed baseline or query identity and update the export or the reviewed manifest deliberately; do not weaken the gate and do not report the synthetic suite as real evidence.
