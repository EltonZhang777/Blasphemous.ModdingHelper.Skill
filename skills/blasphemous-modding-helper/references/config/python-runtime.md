---
name: python-runtime
description: Python interpreter, dependency, diagnostic, and command-boundary contract
---

# Python Runtime

This reference owns the Python runtime gate shared by future Skill entry points. It is the single source of truth for interpreter selection, dependency validation, configuration diagnostics, and direct external command execution.

The final configuration vocabulary is fixed: the active file is `config.yml`; `last_checked_time` and `last_checked_version` are validation metadata; `check_period_days` is the validation period; and `last_checked_version` comes from the installed Skill version source, [`version.yml`](../../version.yml). These names MUST be used in setup and validation reports.

## Interpreter-only cold start

When an operational request has no validated Python context, the agent MUST run one interpreter-only preflight before invoking Skill scripts. Invoke the helper in isolated mode with any usable host Python; the helper applies the established explicit `--python`, `PYTHON3` environment, then host resolution order:

```powershell
& 'C:\path\to\python.exe' -I (Join-Path $SkillRoot 'scripts\check_python_environment.py') --interpreter-only
```

```bash
'/path/to/python3' -I "$SKILL_ROOT/scripts/check_python_environment.py" --interpreter-only
```

Pass a user-supplied candidate as `--python <PATH>` when it MUST take precedence over the environment and host.

Interpreter-only mode accepts Python 3.9 or newer. An absent or blank explicit or environment candidate advances to the next source. A present candidate that is missing, unusable, fails to launch, returns an unreadable probe response, or reports a version below 3.9 stops resolution and MUST NOT fall back. `--requirements` cannot be combined with `--interpreter-only`.

Interpreter-only mode MUST NOT read configuration or the dependency manifest, inspect installed packages, perform network work, or persist interpreter state. Reuse the returned absolute executable path for Skill scripts in the current top-level request, and reapply it if the shell loses its variable. A new top-level request starts cold. First-time setup retains the full preflight and default behavior remains unchanged.

The bootstrap stops after one failure and MUST NOT retry automatically. A selected interpreter that later fails to launch, fails probing, or no longer satisfies Python 3.9+ is a Python-environment failure when observed. Only a classified `PythonEnvironmentError` permits later full-gate recovery; `CommandExecutionError` and unrelated domain failures do not. A failed script MUST NOT be replayed automatically.

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

The [Dependencies](invocation-preflight.md#dependencies) section identifies the declared post-install package and its workflow scope. Supported entries are a package name with an optional `==`, `!=`, `~=`, `>=`, `<=`, `>`, or `<` version constraint. Unsupported pip directives are configuration errors.

## Result contract

Interpreter-only success returns exit code `0` and emits these stable fields:

```text
PYTHON_RUNTIME_STATUS=ok
PYTHON3=<absolute executable>
PYTHON_VERSION=<major.minor.micro>
PYTHON_RUNTIME_SOURCE=<explicit|PYTHON3|host>
```

Full preflight success also emits the dependency fields:

```text
PYTHON_REQUIREMENTS=<absolute manifest>
PYTHON_DEPENDENCY_COUNT=<count>
```

Missing or unusable Python and an old interpreter return configuration exit code `78` in both modes. In full mode, an invalid or missing manifest and missing or incompatible dependencies also return code `78`. The diagnostic starts with `Error [configuration/python-runtime]`, includes a stable `Reason:` line, and ends with an actionable `Action:` line. The error path reports that packages were not installed when dependency repair is needed.

After a successful cold start or first-time setup gate, normal Skill branches MUST reuse the resolved interpreter context. They MUST NOT repeat runtime validation for unrelated source, Git, network, dotnet, game, profile, log, or Mod failures. A later Python entry point MAY route back to the full gate only after raising a classified `PythonEnvironmentError` such as an interpreter, manifest, import, or dependency failure. Known Skill-dependency import failures SHOULD be converted with the shared `classify_import_failure` helper before retrying setup.

## Shared command boundary

Future Python entry points SHOULD import the shared runtime package and use its direct command helper. Commands are argument sequences, paths are separate arguments, and `shell=False` is mandatory. Nonzero exit codes, missing external tools, and timeouts are returned as `CommandResult` values or raised as `CommandExecutionError` when the caller explicitly requires success; they are not Python-environment failures.

Completion criterion: cold start has a validated Python 3.9+ interpreter and either a successful result report or the stable configuration diagnostic with a retry action. Full setup also has a validated dependency manifest. The result report MUST name the completion evidence, the blocked reason when validation fails, and the next action.
