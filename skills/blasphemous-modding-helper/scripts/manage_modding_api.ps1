<#
.SYNOPSIS
    Cross-platform entry point for the shared ModdingAPI lifecycle manager.
#>

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Core = Join-Path $ScriptDir "manage_modding_api.js"
$Node = (Get-Command node -ErrorAction SilentlyContinue).Source
if ([string]::IsNullOrWhiteSpace($Node)) {
    [Console]::Error.WriteLine("[ERROR REPORT]")
    [Console]::Error.WriteLine("operation: manage_modding_api")
    [Console]::Error.WriteLine("target_path: <unset>")
    [Console]::Error.WriteLine("selector: <unset>")
    [Console]::Error.WriteLine("current_head: <unavailable>")
    [Console]::Error.WriteLine("worktree_state: unknown")
    [Console]::Error.WriteLine("network_state: unknown")
    [Console]::Error.WriteLine("cause: Node.js is required to run the shared lifecycle manager")
    [Console]::Error.WriteLine("next_step: Install Node.js 18 or newer, then retry.")
    exit 1
}
if (-not (Test-Path -LiteralPath $Core -PathType Leaf)) {
    [Console]::Error.WriteLine("[ERROR REPORT]")
    [Console]::Error.WriteLine("operation: manage_modding_api")
    [Console]::Error.WriteLine("target_path: <unset>")
    [Console]::Error.WriteLine("selector: <unset>")
    [Console]::Error.WriteLine("current_head: <unavailable>")
    [Console]::Error.WriteLine("worktree_state: unknown")
    [Console]::Error.WriteLine("network_state: unknown")
    [Console]::Error.WriteLine("cause: shared lifecycle manager is missing: $Core")
    [Console]::Error.WriteLine("next_step: Reinstall the skill package, then retry.")
    exit 1
}

$NodeArguments = @($Core) + @($args)

& $Node @NodeArguments
exit $LASTEXITCODE
