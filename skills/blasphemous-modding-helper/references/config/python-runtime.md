---
name: python-runtime
description: Python interpreter, dependency, diagnostic, and command-boundary contract
---

# Python Runtime

This reference owns the Python runtime gate shared by future Skill entry points. It is the single source of truth for interpreter selection, dependency validation, configuration diagnostics, and direct external command execution.

## First-time setup gate

Before asking the first-time setup questions, the agent MUST resolve a Python interpreter and run the public preflight entry point from the installed Skill root:

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\check_python_environment.py') --python $PYTHON3 --requirements (Join-Path $SkillRoot 'requirements.txt')
```

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/check_python_environment.py" --python "$PYTHON3" --requirements "$SKILL_ROOT/requirements.txt"
```

`PYTHON3` means the selected executable, not an unverified shell command. Resolution order is:

1. An explicit interpreter supplied by the setup caller.
2. The `PYTHON3` environment variable.
3. The host interpreter running the setup helper.

The selected interpreter MUST be Python 3.9 or newer. The preflight MUST validate the Skill's `requirements.txt` in that interpreter environment and MUST NOT install or upgrade packages.

The manifest currently declares standard-library-only runtime behavior. Supported entries are a package name with an optional `==`, `!=`, `~=`, `>=`, `<=`, `>`, or `<` version constraint. Unsupported pip directives are configuration errors.

## Result contract

Success returns exit code `0` and emits these stable fields:

```text
PYTHON_RUNTIME_STATUS=ok
PYTHON3=<absolute executable>
PYTHON_VERSION=<major.minor.micro>
PYTHON_RUNTIME_SOURCE=<explicit|PYTHON3|host>
PYTHON_REQUIREMENTS=<absolute manifest>
PYTHON_DEPENDENCY_COUNT=<count>
```

Missing or unusable Python, an old interpreter, an invalid or missing manifest, and missing or incompatible dependencies return configuration exit code `78`. The diagnostic starts with `Error [configuration/python-runtime]`, includes a stable `Reason:` line, and ends with an actionable `Action:` line. The error path reports that packages were not installed when dependency repair is needed.

After a successful first-time setup gate, normal Skill branches MUST reuse the resolved interpreter context. They MUST NOT repeat runtime validation for unrelated source, Git, network, dotnet, game, profile, log, or Mod failures. A later Python entry point MAY route back to this gate only after raising a classified `PythonEnvironmentError` such as an interpreter, manifest, import, or dependency failure. Known Skill-dependency import failures SHOULD be converted with the shared `classify_import_failure` helper before retrying setup.

## Shared command boundary

Future Python entry points SHOULD import the shared runtime package and use its direct command helper. Commands are argument sequences, paths are separate arguments, and `shell=False` is mandatory. Nonzero exit codes, missing external tools, and timeouts are returned as `CommandResult` values or raised as `CommandExecutionError` when the caller explicitly requires success; they are not Python-environment failures.

Completion criterion: setup has a validated Python 3.9+ interpreter, a validated dependency manifest, and either a successful result report or the stable configuration diagnostic with a retry action.
