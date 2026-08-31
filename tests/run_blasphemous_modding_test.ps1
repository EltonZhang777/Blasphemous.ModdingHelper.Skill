[CmdletBinding()]
param(
    [string]$Python,
    [switch]$RequireClean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runner = Join-Path $repoRoot "tests\run_blasphemous_modding_test.py"

if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = $env:BLASPHEMOUS_PYTHON
}

if ([string]::IsNullOrWhiteSpace($Python)) {
    Write-Error "Python 3 path is required. Re-run with -Python PATH or set BLASPHEMOUS_PYTHON." -ErrorAction Continue
    exit 2
}

$arguments = @($runner, "--python", $Python)
if ($RequireClean) {
    $arguments += "--require-clean"
}

& $Python @arguments
exit $LASTEXITCODE
