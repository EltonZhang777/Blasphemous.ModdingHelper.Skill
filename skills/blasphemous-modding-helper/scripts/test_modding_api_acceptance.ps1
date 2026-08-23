<#
.SYNOPSIS
    Cross-platform ModdingAPI acceptance gate; behavior lives in Node.
#>

[CmdletBinding()]
param(
    [switch]$RequireClean
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Core = Join-Path $ScriptDir "test_modding_api_acceptance.js"
$Node = $env:MODDING_API_NODE
if ([string]::IsNullOrWhiteSpace($Node)) {
    $Node = "node"
}

$Arguments = @($Core)
if ($RequireClean) {
    $Arguments += "--require-clean"
}

& $Node @Arguments
exit $LASTEXITCODE
