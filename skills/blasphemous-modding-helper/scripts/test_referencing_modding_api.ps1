<#
.SYNOPSIS
    Public-behavior documentation smoke test for referencing ModdingAPI.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Core = Join-Path $ScriptDir "test_referencing_modding_api.js"
$Node = Get-Command node -ErrorAction SilentlyContinue

if ($null -eq $Node) {
    [Console]::Error.WriteLine("[ERROR REPORT]")
    [Console]::Error.WriteLine("operation: test_referencing_modding_api")
    [Console]::Error.WriteLine("cause: node >= 18 is required")
    [Console]::Error.WriteLine("next_step: install Node.js 18 or newer and retry")
    exit 1
}

& $Node.Source $Core @args
exit $LASTEXITCODE
