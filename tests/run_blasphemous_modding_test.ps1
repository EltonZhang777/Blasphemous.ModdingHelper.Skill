[CmdletBinding()]
param(
    [string]$Python
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$cli = Join-Path $repoRoot "skills\blasphemous-modding-helper\scripts\blasphemous_modding_test.py"

if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = $env:BLASPHEMOUS_PYTHON
}

if ([string]::IsNullOrWhiteSpace($Python)) {
    Write-Error "Python 3 path is required. Re-run with -Python PATH or set BLASPHEMOUS_PYTHON." -ErrorAction Continue
    exit 2
}

Write-Output "Shell: native PowerShell"
Write-Output "Python: $Python"

$status = 0
Push-Location $repoRoot
try {
    & $Python $cli --help
    $status = $LASTEXITCODE
    if ($status -eq 0) {
        foreach ($command in @("run", "stop", "clean", "logs", "status")) {
            & $Python $cli $command --help
            $status = $LASTEXITCODE
            if ($status -ne 0) {
                break
            }
        }
    }
    if ($status -eq 0) {
        & $Python -m unittest discover -s tests -p test_blasphemous_modding_test.py
        $status = $LASTEXITCODE
    }
}
finally {
    Pop-Location
}

exit $status
