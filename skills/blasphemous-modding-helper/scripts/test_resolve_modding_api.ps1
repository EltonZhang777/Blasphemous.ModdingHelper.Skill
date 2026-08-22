<#
.SYNOPSIS
    Public-behavior tests for resolve_modding_api.ps1.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Resolver = Join-Path $ScriptDir "resolve_modding_api.ps1"
$Fixtures = Join-Path ([System.IO.Path]::GetTempPath()) ("modding-api-resolver-test-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $Fixtures | Out-Null

Set-Content -LiteralPath (Join-Path $Fixtures "modding-api-release-latest.json") -Value '{"tag_name":"3.0.1","draft":false,"prerelease":false,"resolved_ref":"3.0.1","resolved_commit":"0123456789012345678901234567890123456789"}'
Set-Content -LiteralPath (Join-Path $Fixtures "modding-api-selector-tag.json") -Value '{"resolved_ref":"2.5.0","resolved_commit":"1111111111111111111111111111111111111111"}'
Set-Content -LiteralPath (Join-Path $Fixtures "modding-api-selector-branch.json") -Value '{"resolved_ref":"main","resolved_commit":"2222222222222222222222222222222222222222"}'
Set-Content -LiteralPath (Join-Path $Fixtures "modding-api-release-prerelease.json") -Value '{"tag_name":"3.0.2","draft":false,"prerelease":true,"resolved_commit":"3333333333333333333333333333333333333333"}'
Set-Content -LiteralPath (Join-Path $Fixtures "modding-api-release-draft.json") -Value '{"tag_name":"3.0.3","draft":true,"prerelease":false,"resolved_commit":"4444444444444444444444444444444444444444"}'
Set-Content -LiteralPath (Join-Path $Fixtures "modding-api-release-malformed.json") -Value '{"draft":false,"prerelease":false}'
Set-Content -LiteralPath (Join-Path $Fixtures "modding-api-release-invalid-json.json") -Value '{not-json'

function Fail-Test([string]$Message) {
    Write-Error "[FAIL] $Message"
    exit 1
}

function Assert-Contains([string]$Haystack, [string]$Needle) {
    if (-not $Haystack.Contains($Needle)) {
        Fail-Test "Expected output to contain: $Needle"
    }
}

function Invoke-Resolver([string]$Selector, [string]$MetadataFile) {
    $shell = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
    if ([string]::IsNullOrWhiteSpace($shell)) {
        $shell = (Get-Command powershell.exe -ErrorAction Stop).Source
    }
    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $Resolver,
        "-Selector",
        $Selector,
        "-MetadataFile",
        $MetadataFile
    )
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = @(& $shell @arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    [pscustomobject]@{
        Text = ($output -join "`n")
        ExitCode = $exitCode
    }
}

$latest = Invoke-Resolver "latest" (Join-Path $Fixtures "modding-api-release-latest.json")
if ($latest.ExitCode -ne 0) { Fail-Test "latest selector should succeed" }
Assert-Contains $latest.Text "MODDING_API_SELECTOR=latest"
Assert-Contains $latest.Text "MODDING_API_SELECTOR_KIND=release"
Assert-Contains $latest.Text "MODDING_API_RESOLVED_TAG=3.0.1"
Assert-Contains $latest.Text "MODDING_API_RESOLVED_COMMIT=0123456789012345678901234567890123456789"
Assert-Contains $latest.Text "MODDING_API_DOCS_URL=https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/3.0.1/docs"
Assert-Contains $latest.Text "MODDING_API_SOURCE_URL=https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/3.0.1"

$tag = Invoke-Resolver "tag:2.5.0" (Join-Path $Fixtures "modding-api-selector-tag.json")
if ($tag.ExitCode -ne 0) { Fail-Test "tag selector should succeed" }
Assert-Contains $tag.Text "MODDING_API_SELECTOR_KIND=tag"
Assert-Contains $tag.Text "MODDING_API_RESOLVED_REF=2.5.0"
Assert-Contains $tag.Text "MODDING_API_RESOLVED_COMMIT=1111111111111111111111111111111111111111"
Assert-Contains $tag.Text "MODDING_API_DOCS_URL=https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/2.5.0/docs"

$mismatch = Invoke-Resolver "tag:2.5.0" (Join-Path $Fixtures "modding-api-release-latest.json")
if ($mismatch.ExitCode -eq 0) { Fail-Test "mismatched selector metadata should fail" }
Assert-Contains $mismatch.Text "[ERROR REPORT]"
Assert-Contains $mismatch.Text "resolved_ref"

$branch = Invoke-Resolver "branch:main" (Join-Path $Fixtures "modding-api-selector-branch.json")
if ($branch.ExitCode -ne 0) { Fail-Test "branch selector should succeed" }
Assert-Contains $branch.Text "MODDING_API_SELECTOR_KIND=branch"
Assert-Contains $branch.Text "MODDING_API_RESOLVED_REF=main"
Assert-Contains $branch.Text "MODDING_API_RESOLVED_COMMIT=2222222222222222222222222222222222222222"
Assert-Contains $branch.Text "MODDING_API_SOURCE_URL=https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/main"

$commit = "0123456789012345678901234567890123456789"
$commitResult = Invoke-Resolver "commit:$commit" (Join-Path $Fixtures "modding-api-release-latest.json")
if ($commitResult.ExitCode -ne 0) { Fail-Test "commit selector should succeed" }
Assert-Contains $commitResult.Text "MODDING_API_SELECTOR_KIND=commit"
Assert-Contains $commitResult.Text "MODDING_API_RESOLVED_COMMIT=$commit"
Assert-Contains $commitResult.Text "MODDING_API_DOCS_URL=https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/$commit/docs"

$prerelease = Invoke-Resolver "latest" (Join-Path $Fixtures "modding-api-release-prerelease.json")
if ($prerelease.ExitCode -eq 0) { Fail-Test "prerelease metadata should fail" }
Assert-Contains $prerelease.Text "[ERROR REPORT]"
Assert-Contains $prerelease.Text "prerelease"

$draft = Invoke-Resolver "latest" (Join-Path $Fixtures "modding-api-release-draft.json")
if ($draft.ExitCode -eq 0) { Fail-Test "draft metadata should fail" }
Assert-Contains $draft.Text "[ERROR REPORT]"
Assert-Contains $draft.Text "draft"

$invalid = Invoke-Resolver "main" (Join-Path $Fixtures "modding-api-release-latest.json")
if ($invalid.ExitCode -eq 0) { Fail-Test "invalid selector should fail" }
Assert-Contains $invalid.Text "[ERROR REPORT]"
Assert-Contains $invalid.Text "selector"

$malformed = Invoke-Resolver "latest" (Join-Path $Fixtures "modding-api-release-malformed.json")
if ($malformed.ExitCode -eq 0) { Fail-Test "malformed metadata should fail" }
Assert-Contains $malformed.Text "[ERROR REPORT]"
Assert-Contains $malformed.Text "tag_name"

$invalidJson = Invoke-Resolver "latest" (Join-Path $Fixtures "modding-api-release-invalid-json.json")
if ($invalidJson.ExitCode -eq 0) { Fail-Test "invalid JSON metadata should fail" }
Assert-Contains $invalidJson.Text "[ERROR REPORT]"
Assert-Contains $invalidJson.Text "parse"

Remove-Item -LiteralPath $Fixtures -Recurse -Force
Write-Output "[OK] resolve_modding_api.ps1 public behavior"
