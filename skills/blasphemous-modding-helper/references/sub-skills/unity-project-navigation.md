# Unity project navigation

This read-only route inspects exported Unity project topology without opening Unity Editor. It owns project structure and scene-set summary evidence. It does not own C# behavior.

## Entry gate

Before using this route, the agent MUST complete [Invocation preflight](../config/invocation-preflight.md). The selected configuration MUST provide a valid `unity_project_path`. Other operational routes MUST NOT require this optional field.

When a valid configuration omits `unity_project_path`, the agent MUST ask only for the Unity project path and MUST keep every unrelated answer and YAML field unchanged. The agent MUST validate and save the answer with:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/check_preferences.py" --set-unity-project-path "<UNITY_PROJECT_ROOT>"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\check_preferences.py') --set-unity-project-path '<UNITY_PROJECT_ROOT>'
```

An invalid path MUST repeat only the Unity-path question. Invalid YAML MUST use the existing full first-time setup flow.
An invalid path result reports `PREFERENCES_NEXT_ACTION=retry-unity-project-path`; invalid YAML reports `PREFERENCES_SETUP=required`.

## Evidence ownership

- The exported Unity project is authoritative only for exported asset topology and serialized evidence.
- The configured lightweight or full source tree remains authoritative for C# behavior, dependencies, class semantics, and runtime call flow through [Source analyzer](source-analyzer.md).
- A Unity `.cs` asset identifies file placement only. It MUST NOT be presented as behavioral proof, even when its relative path matches the authoritative source tree.
- If a behavior request has no authoritative source coverage, the agent MUST report the source gap as blocked and MUST NOT infer behavior from the Unity export.
- When one request spans assets and behavior, the agent MUST report the asset evidence and source evidence separately.

## Workflow

1. Open [Unity project navigation](../unity-project-navigation/MAIN.md) and select the topology topic.
2. Resolve the configured root and invoke the public scanner with an explicit `--project`.
3. The agent MUST read the versioned JSON envelope and report `status`, warnings, evidence paths, and incomplete conditions.
4. Hand behavior or dependency questions to [Source analyzer](source-analyzer.md).

Start with a project summary:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" project --project "<UNITY_PROJECT_ROOT>"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') project --project '<UNITY_PROJECT_ROOT>'
```

The scanner reads the configured directory and writes no index, cache, lock, log, copied asset, or project file. The agent MUST NOT start Unity Editor or modify, repair, or reserialize the project.

## Completion criteria

This route is complete only when:

1. The selected configuration and Unity project root are identified.
2. The narrowest navigation topic and exact scanner query are reported.
3. Every cited asset path is project-relative with forward slashes.
4. Every warning, ambiguity, truncation, timeout, missing identity, or blocked behavior result is explicit.
5. Behavior evidence remains attributed to the configured source analyzer.

Every result MUST report `status`, completion evidence, the blocked reason when applicable, and the next source, asset, or recovery action.
