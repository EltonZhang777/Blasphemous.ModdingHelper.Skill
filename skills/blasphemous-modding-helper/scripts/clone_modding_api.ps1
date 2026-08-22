<#
.SYNOPSIS
    Create a fresh, shallow local ModdingAPI reference checkout.

.DESCRIPTION
    Existing paths are never replaced. Update/check behavior belongs to the
    later lifecycle script; this command only creates a missing reference.
#>

[CmdletBinding()]
param(
    [ValidateSet("project", "user")]
    [string]$Scope = "",

    [string]$TargetPath = "",

    [string]$PreferencesFile = "",

    [string]$Selector = "",

    [string]$MetadataFile = "",

    [switch]$Help
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Resolver = Join-Path $ScriptDir "resolve_modding_api.ps1"
$SelectorWasExplicit = -not [string]::IsNullOrWhiteSpace($Selector)
$TargetWasExplicit = -not [string]::IsNullOrWhiteSpace($TargetPath)
$PreferencesWasExplicit = -not [string]::IsNullOrWhiteSpace($PreferencesFile)

function Write-Usage {
    @"
Usage:
  clone_modding_api.ps1 [options]

Options:
  -Scope project|user       Use the approved project or user reference path.
  -TargetPath PATH          Override the reference checkout path.
  -PreferencesFile PATH     Write the selected path and selector to preferences.md.
  -Selector SELECTOR        latest, tag:REF, branch:REF, or commit:SHA.
  -MetadataFile PATH        Read resolver metadata from a deterministic fixture.
  -Help                     Show this help.

If -TargetPath is omitted, the path is read from modding_api_reference_path
in the selected preferences file, or derived from -Scope. Existing paths are
never overwritten.
"@
}

function Fail-Clone {
    param(
        [int]$ExitCode,
        [string]$Cause,
        [string]$NextStep
    )

    [Console]::Error.WriteLine("[ERROR REPORT]")
    [Console]::Error.WriteLine("operation: clone_modding_api")
    [Console]::Error.WriteLine("target_path: $TargetPath")
    [Console]::Error.WriteLine("selector: $Selector")
    [Console]::Error.WriteLine("cause: $Cause")
    [Console]::Error.WriteLine("next_step: $NextStep")
    exit $ExitCode
}

function Resolve-AbsolutePath {
    param([string]$Path)

    $expanded = $Path
    if ($expanded -eq "~") {
        $expanded = $HOME
    }
    elseif ($expanded.StartsWith("~/") -or $expanded.StartsWith("~\")) {
        $expanded = Join-Path $HOME $expanded.Substring(2)
    }
    if (-not [System.IO.Path]::IsPathRooted($expanded)) {
        $expanded = Join-Path (Get-Location) $expanded
    }
    return [System.IO.Path]::GetFullPath($expanded)
}

function Get-PreferenceValue {
    param(
        [string]$Path,
        [string]$Key
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    $escapedKey = [regex]::Escape($Key)
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ([string]$line -match "^\s*$escapedKey\s*:\s*(.*)$") {
            return $Matches[1].TrimEnd([char]13)
        }
    }
    return $null
}

function Set-Preferences {
    param(
        [string]$Path,
        [string]$ReferencePath,
        [string]$ReferenceSelector
    )

    $parent = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }

    $lines = @()
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        $lines = @(Get-Content -LiteralPath $Path)
    }

    $updated = @()
    $pathSeen = $false
    $selectorSeen = $false
    foreach ($line in $lines) {
        $text = [string]$line
        if ($text -match '^\s*modding_api_reference_path\s*:') {
            $updated += "modding_api_reference_path: $ReferencePath"
            $pathSeen = $true
        }
        elseif ($text -match '^\s*modding_api_reference_selector\s*:') {
            $updated += "modding_api_reference_selector: $ReferenceSelector"
            $selectorSeen = $true
        }
        else {
            $updated += $text
        }
    }
    if (-not $pathSeen) {
        $updated += "modding_api_reference_path: $ReferencePath"
    }
    if (-not $selectorSeen) {
        $updated += "modding_api_reference_selector: $ReferenceSelector"
    }

    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, (($updated -join [Environment]::NewLine) + [Environment]::NewLine), $encoding)
}

function Invoke-GitChecked {
    param(
        [string]$WorkingDirectory,
        [string[]]$Arguments
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = @(& git -C $WorkingDirectory @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($exitCode -ne 0) {
        $details = ($output | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
        Fail-Clone 1 "Git operation failed: $details" "Check network access, the selector, and the target path."
    }
    return $output
}

if ($Help) {
    Write-Usage
    exit 0
}

$projectTarget = Join-Path (Get-Location) ".skills\blasphemous-modding-helper\references\modding-api"
$projectPreferences = Join-Path (Get-Location) ".skills\blasphemous-modding-helper\preferences.md"
$homeDirectory = if ($env:MODDING_API_TEST_MODE -eq "1" -and -not [string]::IsNullOrWhiteSpace($env:MODDING_API_TEST_HOME)) { $env:MODDING_API_TEST_HOME } else { $HOME }
$userTarget = Join-Path $homeDirectory ".skills\blasphemous-modding-helper\references\modding-api"
$userPreferences = Join-Path $homeDirectory ".skills\blasphemous-modding-helper\preferences.md"
$defaultTarget = ""
$defaultPreferences = ""

if (-not [string]::IsNullOrWhiteSpace($Scope)) {
    if ($Scope -eq "project") {
        $defaultTarget = $projectTarget
        $defaultPreferences = $projectPreferences
    }
    else {
        $defaultTarget = $userTarget
        $defaultPreferences = $userPreferences
    }
    if ([string]::IsNullOrWhiteSpace($PreferencesFile)) {
        $PreferencesFile = $defaultPreferences
    }
}

if (-not [string]::IsNullOrWhiteSpace($PreferencesFile)) {
    $PreferencesFile = Resolve-AbsolutePath $PreferencesFile
    if (-not [string]::IsNullOrWhiteSpace($Scope) -and $PreferencesWasExplicit) {
        $expectedPreferences = Resolve-AbsolutePath $defaultPreferences
        if ($PreferencesFile -ne $expectedPreferences) {
            Fail-Clone 2 "preferences file scope does not match -Scope $Scope" "Use the preferences path belonging to the selected scope."
        }
    }
}

if (-not $TargetWasExplicit -and -not [string]::IsNullOrWhiteSpace($PreferencesFile)) {
    $configuredTarget = Get-PreferenceValue $PreferencesFile "modding_api_reference_path"
    if (-not [string]::IsNullOrWhiteSpace($configuredTarget)) {
        $TargetPath = $configuredTarget
    }
}

if ([string]::IsNullOrWhiteSpace($TargetPath)) {
    if ([string]::IsNullOrWhiteSpace($defaultTarget)) {
        Fail-Clone 2 "no local reference path was provided" "Use -TargetPath, -Scope, or configure modding_api_reference_path in preferences.md."
    }
    $TargetPath = $defaultTarget
}
$TargetPath = Resolve-AbsolutePath $TargetPath

if (-not $SelectorWasExplicit) {
    $configuredSelector = Get-PreferenceValue $PreferencesFile "modding_api_reference_selector"
    if (-not [string]::IsNullOrWhiteSpace($configuredSelector)) {
        $Selector = $configuredSelector
    }
    else {
        $Selector = "latest"
    }
}

if ($null -eq (Get-Command git -ErrorAction SilentlyContinue)) {
    Fail-Clone 1 "git is required to create a local reference" "Install Git and retry."
}
if (-not (Test-Path -LiteralPath $Resolver -PathType Leaf)) {
    Fail-Clone 1 "resolver script is missing: $Resolver" "Reinstall the skill package and retry."
}

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    if (-not [string]::IsNullOrWhiteSpace($MetadataFile)) {
        $resolverMetadataPath = Resolve-AbsolutePath $MetadataFile
        $resolverOutput = @(& $Resolver -Selector $Selector -MetadataFile $resolverMetadataPath 2>&1)
    }
    else {
        $resolverOutput = @(& $Resolver -Selector $Selector 2>&1)
    }
    $resolverExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
if ($resolverExitCode -ne 0) {
    $resolverOutput | ForEach-Object { [Console]::Error.WriteLine([string]$_) }
    Fail-Clone 1 "selector resolution failed" "Fix the selector or network/Release metadata problem, then retry."
}

$resolverValues = @{}
foreach ($line in $resolverOutput) {
    $text = [string]$line
    $separator = $text.IndexOf("=")
    if ($separator -gt 0) {
        $resolverValues[$text.Substring(0, $separator)] = $text.Substring($separator + 1)
    }
}

$repository = [string]$resolverValues["MODDING_API_REPOSITORY"]
$selectorKind = [string]$resolverValues["MODDING_API_SELECTOR_KIND"]
$resolvedRef = [string]$resolverValues["MODDING_API_RESOLVED_REF"]
$resolvedTag = [string]$resolverValues["MODDING_API_RESOLVED_TAG"]
$resolvedCommit = [string]$resolverValues["MODDING_API_RESOLVED_COMMIT"]
if ([string]::IsNullOrWhiteSpace($repository) -or
    [string]::IsNullOrWhiteSpace($selectorKind) -or
    [string]::IsNullOrWhiteSpace($resolvedRef) -or
    [string]::IsNullOrWhiteSpace($resolvedCommit)) {
    Fail-Clone 1 "resolver returned incomplete reference metadata" "Retry the selector resolution and inspect its error report."
}

# This environment variable is used only by repository-owned deterministic
# tests. Normal invocations always use the official repository returned above.
if (-not [string]::IsNullOrWhiteSpace($env:MODDING_API_TEST_REPOSITORY)) {
    if ($env:MODDING_API_TEST_MODE -ne "1") {
        Fail-Clone 2 "test repository override requires test mode" "Use the official repository or run repository-owned tests with test mode enabled."
    }
    $repository = $env:MODDING_API_TEST_REPOSITORY
}

if ($null -ne (Get-Item -LiteralPath $TargetPath -Force -ErrorAction SilentlyContinue)) {
    Fail-Clone 2 "target path already exists: $TargetPath" "Choose a missing directory or use the later update/check workflow."
}

$targetParent = Split-Path -Parent $TargetPath
try {
    New-Item -ItemType Directory -Force -Path $targetParent | Out-Null
}
catch {
    Fail-Clone 2 "cannot create target parent: $targetParent" "Check the path and permissions, then retry."
}
$leaf = Split-Path -Leaf $TargetPath
$stagingPath = Join-Path $targetParent (".$leaf.staging." + [guid]::NewGuid().ToString("N"))
$moved = $false

try {
    New-Item -ItemType Directory -Path $stagingPath | Out-Null
    Invoke-GitChecked $stagingPath @("init", "-q") | Out-Null
    Invoke-GitChecked $stagingPath @("remote", "add", "origin", $repository) | Out-Null

    switch ($selectorKind) {
        "release" {
            Invoke-GitChecked $stagingPath @("fetch", "--depth", "1", "origin", "refs/tags/${resolvedRef}:refs/tags/${resolvedRef}") | Out-Null
            Invoke-GitChecked $stagingPath @("checkout", "--detach", "refs/tags/$resolvedRef") | Out-Null
        }
        "tag" {
            Invoke-GitChecked $stagingPath @("fetch", "--depth", "1", "origin", "refs/tags/${resolvedRef}:refs/tags/${resolvedRef}") | Out-Null
            Invoke-GitChecked $stagingPath @("checkout", "--detach", "refs/tags/$resolvedRef") | Out-Null
        }
        "branch" {
            Invoke-GitChecked $stagingPath @("fetch", "--depth", "1", "origin", "refs/heads/${resolvedRef}:refs/remotes/origin/${resolvedRef}") | Out-Null
            Invoke-GitChecked $stagingPath @("checkout", "-q", "-b", $resolvedRef, "--track", "refs/remotes/origin/$resolvedRef") | Out-Null
        }
        "commit" {
            Invoke-GitChecked $stagingPath @("fetch", "--depth", "1", "origin", $resolvedCommit) | Out-Null
            Invoke-GitChecked $stagingPath @("checkout", "--detach", $resolvedCommit) | Out-Null
        }
        default {
            Fail-Clone 1 "resolver returned unsupported selector kind: $selectorKind" "Use latest, tag:REF, branch:REF, or commit:SHA."
        }
    }

    $actualCommit = (Invoke-GitChecked $stagingPath @("rev-parse", "HEAD") | Select-Object -First 1).Trim()
    if ($actualCommit -ne $resolvedCommit) {
        Fail-Clone 1 "checkout resolved to $actualCommit instead of $resolvedCommit" "Retry the clone and inspect the selected Git reference."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $stagingPath ".git\shallow"))) {
        Fail-Clone 1 "clone is not shallow" "Retry with a Git installation that supports shallow fetches."
    }

    if ($selectorKind -eq "branch") {
        $upstream = (Invoke-GitChecked $stagingPath @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}") | Select-Object -First 1).Trim()
        if ($upstream -ne "origin/$resolvedRef") {
            Fail-Clone 1 "branch does not track origin/$resolvedRef" "Retry the fresh clone with the requested branch selector."
        }
    }
    else {
        $headReference = @(& git -C $stagingPath symbolic-ref --quiet --short HEAD 2>$null)
        if ($LASTEXITCODE -eq 0) {
            Fail-Clone 1 "fixed reference is not detached" "Retry the fresh clone with the requested tag or commit selector."
        }
    }

    Move-Item -LiteralPath $stagingPath -Destination $TargetPath
    $moved = $true
    $stagingPath = $null

    if (-not [string]::IsNullOrWhiteSpace($PreferencesFile)) {
        try {
            Set-Preferences $PreferencesFile $TargetPath $Selector
        }
        catch {
            Fail-Clone 1 "clone succeeded but preferences could not be updated: $PreferencesFile" "Record the absolute path and selector in preferences.md, then retry future lookups."
        }
    }
}
finally {
    if (-not $moved -and -not [string]::IsNullOrWhiteSpace($stagingPath) -and (Test-Path -LiteralPath $stagingPath)) {
        Remove-Item -LiteralPath $stagingPath -Recurse -Force
    }
}

Write-Output "MODDING_API_OPERATION=clone"
Write-Output "MODDING_API_REPOSITORY=$repository"
Write-Output "MODDING_API_REFERENCE_PATH=$TargetPath"
Write-Output "MODDING_API_PREFERENCES_FILE=$PreferencesFile"
Write-Output "MODDING_API_SELECTOR=$Selector"
Write-Output "MODDING_API_SELECTOR_KIND=$selectorKind"
Write-Output "MODDING_API_RESOLVED_REF=$resolvedRef"
Write-Output "MODDING_API_RESOLVED_TAG=$resolvedTag"
Write-Output "MODDING_API_RESOLVED_COMMIT=$resolvedCommit"
Write-Output "MODDING_API_SHALLOW=true"
exit 0
