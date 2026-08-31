<#
.SYNOPSIS
    Cross-platform entry point for the Python ModdingAPI clone workflow.
#>

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Core = Join-Path $ScriptDir "clone_modding_api.py"
$Python = $env:PYTHON3
if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = $env:BLASPHEMOUS_PYTHON
}
if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = (Get-Command python3 -ErrorAction SilentlyContinue).Source
}
if ([string]::IsNullOrWhiteSpace($Python)) {
    [Console]::Error.WriteLine("[ERROR REPORT]")
    [Console]::Error.WriteLine("operation: clone_modding_api")
    [Console]::Error.WriteLine("target_path: <unset>")
    [Console]::Error.WriteLine("selector: <unset>")
    [Console]::Error.WriteLine("current_head: <unavailable>")
    [Console]::Error.WriteLine("worktree_state: unknown")
    [Console]::Error.WriteLine("network_state: unknown")
    [Console]::Error.WriteLine("cause: Python 3.9 or newer is required")
    [Console]::Error.WriteLine("next_step: Set PYTHON3 to a Python 3.9+ executable and retry.")
    exit 1
}
if (-not (Test-Path -LiteralPath $Core -PathType Leaf)) {
    [Console]::Error.WriteLine("[ERROR REPORT]")
    [Console]::Error.WriteLine("operation: clone_modding_api")
    [Console]::Error.WriteLine("target_path: <unset>")
    [Console]::Error.WriteLine("selector: <unset>")
    [Console]::Error.WriteLine("current_head: <unavailable>")
    [Console]::Error.WriteLine("worktree_state: unknown")
    [Console]::Error.WriteLine("network_state: unknown")
    [Console]::Error.WriteLine("cause: Python clone workflow is missing: $Core")
    [Console]::Error.WriteLine("next_step: Reinstall the skill package, then retry.")
    exit 1
}

$arguments = @($Core) + @($args)

& $Python @arguments
exit $LASTEXITCODE
