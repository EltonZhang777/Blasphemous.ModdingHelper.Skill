<#
.SYNOPSIS
    Manual live Release smoke; behavior lives in Node.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Core = Join-Path $ScriptDir "test_modding_api_live.js"
$Node = $env:MODDING_API_NODE
if ([string]::IsNullOrWhiteSpace($Node)) {
    $Node = "node"
}

& $Node $Core
exit $LASTEXITCODE
