<#
.SYNOPSIS
    Resolve a ModdingAPI selector to a stable reference and canonical URLs.

.DESCRIPTION
    The implicit latest selector is backed by the official GitHub Releases API.
    It excludes draft and prerelease Releases and never silently selects main.
#>

[CmdletBinding()]
param(
    [string]$Selector = "latest",
    [string]$MetadataFile = "",
    [switch]$Help
)

$ErrorActionPreference = "Stop"

$Repository = "https://github.com/BrandenEK/Blasphemous.ModdingAPI.git"
$WebRepository = "https://github.com/BrandenEK/Blasphemous.ModdingAPI"
$ReleaseApi = "https://api.github.com/repos/BrandenEK/Blasphemous.ModdingAPI/releases/latest"

function Write-Usage {
    @"
Usage:
  resolve_modding_api.ps1 [-Selector SELECTOR] [-MetadataFile PATH]

Selectors:
  latest             Resolve the newest stable GitHub Release.
  tag:REF            Resolve an explicit Git tag.
  branch:REF         Resolve an explicit Git branch.
  commit:SHA         Resolve an exact 40-character commit.

Options:
  -MetadataFile PATH
      Read Release-shaped JSON from PATH instead of the GitHub Releases API.
      This is intended for deterministic tests and offline fixture use.
  -Help
"@
}

function Fail-Resolution {
    param(
        [int]$ExitCode,
        [string]$Cause,
        [string]$NextStep
    )

    [Console]::Error.WriteLine("[ERROR REPORT]")
    [Console]::Error.WriteLine("operation: resolve_modding_api")
    [Console]::Error.WriteLine("selector: $Selector")
    [Console]::Error.WriteLine("cause: $Cause")
    [Console]::Error.WriteLine("next_step: $NextStep")
    exit $ExitCode
}

function Test-ValidRef {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }
    if ($Value -notmatch "^[A-Za-z0-9][A-Za-z0-9._/-]*$") {
        return $false
    }
    if ($Value.Contains("..") -or $Value.EndsWith("/") -or $Value.Contains("//") -or $Value.Contains("@{")) {
        return $false
    }
    return $true
}

function Assert-ValidRef {
    param(
        [string]$Value,
        [string]$Description
    )

    if (-not (Test-ValidRef $Value)) {
        Fail-Resolution 2 ("invalid " + $Description + ": " + $Value) "Use a valid non-empty Git reference."
    }
}

function Test-ValidCommit {
    param([string]$Value)

    return $Value -match "^[0-9a-fA-F]{40}$"
}

function Assert-ValidCommit {
    param(
        [string]$Value,
        [int]$ExitCode = 2,
        [string]$Description = "commit"
    )

    if (-not (Test-ValidCommit $Value)) {
        Fail-Resolution $ExitCode ("invalid " + $Description + ": " + $Value) "Use exactly 40 hexadecimal characters."
    }
}

function Get-JsonPropertyValue {
    param(
        [object]$Object,
        [string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }
    return $property.Value
}

function Test-JsonProperty {
    param(
        [object]$Object,
        [string]$Name
    )

    if ($null -eq $Object) {
        return $false
    }
    return $null -ne $Object.PSObject.Properties[$Name]
}

function Read-ReleaseMetadata {
    param(
        [string]$Path,
        [bool]$RequireReleaseFields
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        try {
            $json = Invoke-RestMethod -Uri $ReleaseApi -Headers @{ "User-Agent" = "blasphemous-modding-helper" } -UseBasicParsing
        }
        catch {
            Fail-Resolution 1 "could not retrieve the official GitHub latest Release metadata" "Check network access and retry, or provide an explicit selector."
        }
    }
    else {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            Fail-Resolution 2 "metadata file does not exist: $Path" "Provide a readable Release metadata file or omit -MetadataFile."
        }
        try {
            $json = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        }
        catch {
            Fail-Resolution 2 "could not parse metadata file: $Path" "Repair the JSON fixture and retry."
        }
    }

    $tag = Get-JsonPropertyValue $json "tag_name"
    $draft = Get-JsonPropertyValue $json "draft"
    $prerelease = Get-JsonPropertyValue $json "prerelease"
    $resolvedRef = Get-JsonPropertyValue $json "resolved_ref"
    $resolvedCommit = Get-JsonPropertyValue $json "resolved_commit"

    if ($RequireReleaseFields) {
        if (-not (Test-JsonProperty $json "tag_name") -or [string]::IsNullOrWhiteSpace([string]$tag)) {
            Fail-Resolution 2 "Release metadata is missing tag_name" "Use the official Releases response or repair the fixture."
        }
        Assert-ValidRef ([string]$tag) "Release tag"
        if (-not (Test-JsonProperty $json "draft") -or ($draft -isnot [bool])) {
            Fail-Resolution 2 "Release metadata is missing a boolean draft field" "Use the official Releases response or repair the fixture."
        }
        if (-not (Test-JsonProperty $json "prerelease") -or ($prerelease -isnot [bool])) {
            Fail-Resolution 2 "Release metadata is missing a boolean prerelease field" "Use the official Releases response or repair the fixture."
        }
        if ([bool]$draft) {
            Fail-Resolution 2 "the selected latest Release is a draft" "Publish a stable Release or choose an explicit selector."
        }
        if ([bool]$prerelease) {
            Fail-Resolution 2 "the selected latest Release is a prerelease" "Publish a stable Release or choose an explicit selector."
        }
    }

    if ($null -ne $resolvedCommit -and -not [string]::IsNullOrWhiteSpace([string]$resolvedCommit)) {
        Assert-ValidCommit ([string]$resolvedCommit) 2 "resolved_commit"
    }
    if ($null -ne $resolvedRef -and -not [string]::IsNullOrWhiteSpace([string]$resolvedRef)) {
        Assert-ValidRef ([string]$resolvedRef) "resolved_ref"
    }

    return [pscustomobject]@{
        Tag = if ($null -eq $tag) { $null } else { [string]$tag }
        Draft = $draft
        Prerelease = $prerelease
        ResolvedRef = if ($null -eq $resolvedRef -or [string]::IsNullOrWhiteSpace([string]$resolvedRef)) { $null } else { [string]$resolvedRef }
        ResolvedCommit = if ($null -eq $resolvedCommit -or [string]::IsNullOrWhiteSpace([string]$resolvedCommit)) { $null } else { [string]$resolvedCommit }
    }
}

function Get-OptionalMetadataCommit {
    param([string]$ExpectedRef)

    if ([string]::IsNullOrWhiteSpace($MetadataFile)) {
        return $null
    }

    $metadata = Read-ReleaseMetadata $MetadataFile $false
    if ($null -ne $metadata.ResolvedCommit -and $metadata.ResolvedRef -ne $ExpectedRef) {
        Fail-Resolution 2 ("metadata resolved_ref does not match the requested reference: " + $ExpectedRef) "Repair the fixture or omit -MetadataFile."
    }
    return $metadata.ResolvedCommit
}

function Resolve-RemoteCommit {
    param(
        [string]$Kind,
        [string]$Ref
    )

    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if ($null -eq $gitCommand) {
        Fail-Resolution 1 ("git is required to resolve the explicit " + $Kind + " selector") "Install Git or use an exact commit selector."
    }

    if ($Kind -eq "tag") {
        $plainRef = "refs/tags/$Ref"
        $peeledRef = "$plainRef^{}"
        $gitArguments = @("ls-remote", "--tags", $Repository, $plainRef, $peeledRef)
    }
    else {
        $plainRef = "refs/heads/$Ref"
        $peeledRef = $null
        $gitArguments = @("ls-remote", "--heads", $Repository, $plainRef)
    }

    try {
        $lines = @(& $gitCommand.Source @gitArguments 2>$null)
        $gitExitCode = $LASTEXITCODE
    }
    catch {
        Fail-Resolution 1 ("could not run git while resolving " + $Kind + ": " + $Ref) "Install Git and retry."
    }
    if ($gitExitCode -ne 0) {
        Fail-Resolution 1 ("could not query the ModdingAPI Git repository for " + $Kind + " " + $Ref) "Check network access and the reference name."
    }

    $plainCommit = $null
    $peeledCommit = $null
    foreach ($line in $lines) {
        $parts = ([string]$line) -split "\s+", 2
        if ($parts.Count -lt 2) {
            continue
        }
        if ($null -ne $peeledRef -and $parts[1] -eq $peeledRef) {
            $peeledCommit = $parts[0]
            break
        }
        if ($parts[1] -eq $plainRef) {
            $plainCommit = $parts[0]
        }
    }

    $commit = if ($null -ne $peeledCommit) { $peeledCommit } else { $plainCommit }
    if ([string]::IsNullOrWhiteSpace($commit)) {
        Fail-Resolution 1 ("the ModdingAPI " + $Kind + " " + $Ref + " was not found or did not resolve to a commit") "Check the selector spelling or choose a known reference."
    }
    Assert-ValidCommit $commit 1 ("remote " + $Kind + " resolution")
    return $commit
}

if ($Help) {
    Write-Usage
    exit 0
}

$selectorKind = $null
$resolvedRef = $null
$resolvedTag = ""
$resolvedCommit = $null

switch -Regex -CaseSensitive ($Selector) {
    "^latest$" {
        $selectorKind = "release"
        $metadata = Read-ReleaseMetadata $MetadataFile $true
        $resolvedTag = $metadata.Tag
        $resolvedRef = $metadata.Tag
        if ($null -ne $metadata.ResolvedCommit) {
            $resolvedCommit = $metadata.ResolvedCommit
        }
        else {
            $resolvedCommit = Resolve-RemoteCommit "tag" $resolvedTag
        }
        break
    }
    "^tag:(.*)$" {
        $selectorKind = "tag"
        $resolvedTag = $Matches[1]
        Assert-ValidRef $resolvedTag "tag selector"
        $resolvedRef = $resolvedTag
        $fixtureCommit = Get-OptionalMetadataCommit $resolvedTag
        if ($null -ne $fixtureCommit) {
            $resolvedCommit = $fixtureCommit
        }
        else {
            $resolvedCommit = Resolve-RemoteCommit "tag" $resolvedTag
        }
        break
    }
    "^branch:(.*)$" {
        $selectorKind = "branch"
        $branchRef = $Matches[1]
        Assert-ValidRef $branchRef "branch selector"
        $resolvedRef = $branchRef
        $fixtureCommit = Get-OptionalMetadataCommit $branchRef
        if ($null -ne $fixtureCommit) {
            $resolvedCommit = $fixtureCommit
        }
        else {
            $resolvedCommit = Resolve-RemoteCommit "branch" $branchRef
        }
        break
    }
    "^commit:(.*)$" {
        $selectorKind = "commit"
        $resolvedCommit = $Matches[1]
        Assert-ValidCommit $resolvedCommit 2 "commit selector"
        $resolvedRef = $resolvedCommit
        break
    }
    default {
        Fail-Resolution 2 "invalid selector: $Selector" "Use latest, tag:REF, branch:REF, or commit:SHA; main is not an implicit selector."
    }
}

$docsUrl = "$WebRepository/tree/$resolvedRef/docs"
$sourceUrl = "$WebRepository/tree/$resolvedRef"

Write-Output "MODDING_API_REPOSITORY=$Repository"
Write-Output "MODDING_API_SELECTOR=$Selector"
Write-Output "MODDING_API_SELECTOR_KIND=$selectorKind"
Write-Output "MODDING_API_RESOLVED_REF=$resolvedRef"
Write-Output "MODDING_API_RESOLVED_TAG=$resolvedTag"
Write-Output "MODDING_API_RESOLVED_COMMIT=$resolvedCommit"
Write-Output "MODDING_API_DOCS_URL=$docsUrl"
Write-Output "MODDING_API_SOURCE_URL=$sourceUrl"
