---
status: accepted
---

# Use Python as the Skill script runtime

The Skill currently duplicates behavior across JavaScript, PowerShell, and Bash, which makes the Bash acceptance path difficult to validate and maintain. We will migrate every script under `skills/blasphemous-modding-helper/scripts/` and the repository's root test runners to Python, while leaving the repository-level `bin/install.js` installer in Node.js. Python 3.9 or newer and the standard library are the runtime baseline; `skills/blasphemous-modding-helper/requirements.txt` records runtime dependencies, initially none, and setup checks them without automatic installation. Public commands, arguments, exit codes, output fields, error reports, lifecycle states, and log evidence remain compatible. Independent Python entry points will use a shared package, platform adapters will handle unavoidable OS differences, and external tools will be invoked directly with `shell=False`. Python is checked during first-time setup and again only after a classified Python-environment failure. Documentation will point only to Python entry points. Tests will be Python `unittest` plus subprocess contract tests, with native Windows/Linux/macOS coverage; issue #64 will verify this Python matrix rather than Bash/PowerShell parity. Legacy implementations will be removed only in the final migration ticket; Git history is the rollback source.

## Considered options

- Retaining JavaScript, PowerShell, or Bash implementations as compatibility fallbacks would preserve duplicate behavior and the original maintenance problem.
- Checking Python on every Skill invocation would burden sub-features that do not execute scripts and would misclassify ordinary command failures.
- Automatically installing Python packages would mutate the user's environment without explicit approval.

## Consequences

- The Skill documentation, setup flow, test commands, and issue #64 contract must be updated together with the implementation.
- Process ownership, Steam launch, decompilation, file replacement, and path behavior require explicit platform adapters and regression tests.
- `bin/install.js` remains a deliberate Node.js boundary and is tested separately.
