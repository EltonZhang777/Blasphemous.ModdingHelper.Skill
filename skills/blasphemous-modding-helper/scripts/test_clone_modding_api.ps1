<#
.SYNOPSIS
    Public-behavior tests for clone_modding_api.ps1.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Cloner = Join-Path $ScriptDir "clone_modding_api.ps1"
$Resolver = Join-Path $ScriptDir "resolve_modding_api.ps1"
$TestRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("modding-api-clone-test-" + [guid]::NewGuid().ToString("N"))

function Fail-Test([string]$Message) {
    Write-Error "[FAIL] $Message"
    exit 1
}

function Assert-Contains([string]$Haystack, [string]$Needle) {
    if (-not $Haystack.Contains($Needle)) {
        Fail-Test "Expected output to contain: $Needle"
    }
}

function Invoke-Git([string]$WorkingDirectory, [string[]]$Arguments) {
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
        throw (($output | ForEach-Object { [string]$_ }) -join "`n")
    }
    return (($output | ForEach-Object { [string]$_ }) -join "`n")
}

New-Item -ItemType Directory -Force -Path $TestRoot | Out-Null
$previousRepository = $env:MODDING_API_TEST_REPOSITORY
$previousHome = $env:MODDING_API_TEST_HOME
$previousTestMode = $env:MODDING_API_TEST_MODE
$env:MODDING_API_TEST_MODE = "1"

try {
    $remote = Join-Path $TestRoot "modding-api.git"
    $seed = Join-Path $TestRoot "seed"
    $project = Join-Path $TestRoot "project"
    $metadata = Join-Path $TestRoot "latest.json"

    Invoke-Git $TestRoot @("init", "--bare", $remote) | Out-Null
    Invoke-Git $TestRoot @("init", $seed) | Out-Null
    Invoke-Git $seed @("config", "user.email", "test@example.invalid") | Out-Null
    Invoke-Git $seed @("config", "user.name", "ModdingAPI test") | Out-Null
    Set-Content -LiteralPath (Join-Path $seed "README.md") -Value "stable" -NoNewline
    Invoke-Git $seed @("add", "README.md") | Out-Null
    Invoke-Git $seed @("commit", "-m", "initial stable reference") | Out-Null
    Invoke-Git $seed @("branch", "-M", "main") | Out-Null
    Invoke-Git $seed @("tag", "-a", "v1.0.0", "-m", "stable release") | Out-Null
    Invoke-Git $seed @("remote", "add", "origin", $remote) | Out-Null
    Invoke-Git $seed @("push", "--set-upstream", "origin", "main", "--tags") | Out-Null

    $releaseCommit = Invoke-Git $seed @("rev-parse", "refs/tags/v1.0.0^{commit}")
    Invoke-Git $seed @("checkout", "-b", "dev") | Out-Null
    Set-Content -LiteralPath (Join-Path $seed "README.md") -Value "development" -NoNewline
    Invoke-Git $seed @("commit", "-am", "development reference") | Out-Null
    Invoke-Git $seed @("push", "--set-upstream", "origin", "dev") | Out-Null
    $devCommit = Invoke-Git $seed @("rev-parse", "HEAD")
    Invoke-Git $seed @("checkout", "main") | Out-Null
    Set-Content -LiteralPath $metadata -Value (@{
        tag_name = "v1.0.0"
        draft = $false
        prerelease = $false
        resolved_ref = "v1.0.0"
        resolved_commit = $releaseCommit.Trim()
    } | ConvertTo-Json -Compress)
    Set-Content -LiteralPath (Join-Path $TestRoot "dev.json") -Value (@{
        resolved_ref = "dev"
        resolved_commit = $devCommit.Trim()
    } | ConvertTo-Json -Compress)

    $env:MODDING_API_TEST_MODE = "0"
    $fixtureGateOutput = @(& $Cloner -TargetPath (Join-Path $TestRoot "fixture-gate-reference") -Selector latest -MetadataFile $metadata 2>&1)
    if ($LASTEXITCODE -ne 2) {
        Fail-Test "clone metadata fixtures should require test mode and return exit code 2"
    }
    Assert-Contains (($fixtureGateOutput | ForEach-Object { [string]$_ }) -join "`n") "require test mode"

    $invalidScopeOutput = @(& $Cloner -Scope invalid -TargetPath (Join-Path $TestRoot "invalid-scope-reference") -Selector latest 2>&1)
    if ($LASTEXITCODE -ne 2) {
        Fail-Test "invalid scope should return configuration exit code 2"
    }
    $invalidScopeText = ($invalidScopeOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-Contains $invalidScopeText "[ERROR REPORT]"
    Assert-Contains $invalidScopeText "invalid scope"

    $unknownOptionOutput = @(& $Cloner -Bogus 2>&1)
    if ($LASTEXITCODE -ne 2) {
        Fail-Test "unknown PowerShell options should return configuration exit code 2"
    }
    Assert-Contains (($unknownOptionOutput | ForEach-Object { [string]$_ }) -join "`n") "unknown option"

    $env:MODDING_API_TEST_MODE = "1"

    $legacyDirectory = Join-Path $project ".skills\blasphemous-modding-helper"
    New-Item -ItemType Directory -Force -Path $legacyDirectory | Out-Null
    Set-Content -LiteralPath (Join-Path $legacyDirectory "preferences.md") -Value @(
        "lightweight_source_code_path: legacy-source",
        "modding_profile_path: legacy-profile"
    )

    $env:MODDING_API_TEST_REPOSITORY = $remote
    $blockedParent = Join-Path $TestRoot "blocked-preferences"
    Set-Content -LiteralPath $blockedParent -Value "not a directory" -NoNewline
    $rollbackTarget = Join-Path $TestRoot "rollback-reference"
    $rollbackOutput = @(& $Cloner -TargetPath $rollbackTarget -PreferencesFile (Join-Path $blockedParent "preferences.md") -Selector latest -MetadataFile $metadata 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "preferences failure should return runtime exit code 1"
    }
    Assert-Contains (($rollbackOutput | ForEach-Object { [string]$_ }) -join "`n") "preferences"
    if ((Test-Path -LiteralPath $rollbackTarget) -or (Test-Path -LiteralPath "$rollbackTarget.lock")) {
        Fail-Test "preferences failure should roll back the new checkout and lock"
    }

    $lockOnlyTarget = Join-Path $TestRoot "lock-only-reference"
    $lockOnlyPath = "$lockOnlyTarget.lock"
    Set-Content -LiteralPath $lockOnlyPath -Value "sentinel lock" -NoNewline
    $lockOnlyOutput = @(& $Cloner -TargetPath $lockOnlyTarget -Selector latest -MetadataFile $metadata 2>&1)
    if ($LASTEXITCODE -ne 2) {
        Fail-Test "an existing sibling lock should return configuration exit code 2"
    }
    Assert-Contains (($lockOnlyOutput | ForEach-Object { [string]$_ }) -join "`n") "lock path already exists"
    if ((Get-Content -LiteralPath $lockOnlyPath -Raw) -ne "sentinel lock") {
        Fail-Test "an existing sibling lock must not be replaced"
    }
    if (Test-Path -LiteralPath $lockOnlyTarget) {
        Fail-Test "a lock-only conflict must not create a checkout"
    }

    Push-Location $project
    try {
        $output = @(& $Cloner -Scope project -Selector latest -MetadataFile $metadata 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    if ($exitCode -ne 0) {
        Fail-Test "latest project clone should succeed: $($output -join "`n")"
    }
    $outputText = ($output | ForEach-Object { [string]$_ }) -join "`n"

    $target = Join-Path $project ".skills\blasphemous-modding-helper\references\modding-api"
    $preferences = Join-Path $project ".skills\blasphemous-modding-helper\preferences.md"
    $lockFile = Join-Path $project ".skills\blasphemous-modding-helper\references\modding-api.lock"
    $normalizedTarget = [System.IO.Path]::GetFullPath($target)

    Assert-Contains $outputText "MODDING_API_OPERATION=clone"
    Assert-Contains $outputText "MODDING_API_REFERENCE_PATH=$normalizedTarget"
    Assert-Contains $outputText "MODDING_API_SELECTOR=latest"
    Assert-Contains $outputText "MODDING_API_RESOLVED_TAG=v1.0.0"
    Assert-Contains $outputText "MODDING_API_RESOLVED_COMMIT=$($releaseCommit.Trim())"
    Assert-Contains $outputText "MODDING_API_SHALLOW=true"
    Assert-Contains $outputText "MODDING_API_LOCK_PATH=$lockFile"
    $lockText = Get-Content -LiteralPath $lockFile -Raw
    Assert-Contains $lockText "selector: latest"
    Assert-Contains $lockText "resolved_tag: v1.0.0"
    Assert-Contains $lockText "resolved_commit: $($releaseCommit.Trim())"
    Assert-Contains $lockText "checked_at: "
    if (-not (Test-Path -LiteralPath (Join-Path $target ".git\shallow"))) {
        Fail-Test "clone should use shallow history by default"
    }
    if ((Invoke-Git $target @("rev-parse", "HEAD")).Trim() -ne $releaseCommit.Trim()) {
        Fail-Test "clone should resolve the release commit"
    }
    $headName = @(& git -C $target symbolic-ref --quiet --short HEAD 2>$null)
    if ($LASTEXITCODE -eq 0) {
        Fail-Test "tag-based clone should use detached HEAD"
    }
    if ((Invoke-Git $target @("config", "--get", "remote.origin.url")).Trim() -ne $remote) {
        Fail-Test "clone should record the upstream origin"
    }

    $preferencesText = Get-Content -LiteralPath $preferences -Raw
    Assert-Contains $preferencesText "lightweight_source_code_path: legacy-source"
    Assert-Contains $preferencesText "modding_profile_path: legacy-profile"
    Assert-Contains $preferencesText "modding_api_reference_path: $normalizedTarget"
    Assert-Contains $preferencesText "modding_api_reference_selector: latest"

    $configuredTarget = Join-Path $TestRoot "preference-reference"
    $configuredPreferences = Join-Path $TestRoot "configured-preferences.md"
    Set-Content -LiteralPath $configuredPreferences -Value @(
        "modding_api_reference_path: $configuredTarget",
        "modding_api_reference_selector: tag:v1.0.0"
    )
    $configuredOutput = @(& $Cloner -PreferencesFile $configuredPreferences -MetadataFile $metadata 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "preferences-driven clone should succeed: $($configuredOutput -join [Environment]::NewLine)"
    }
    $configuredNormalizedTarget = [System.IO.Path]::GetFullPath($configuredTarget)
    Assert-Contains (($configuredOutput | ForEach-Object { [string]$_ }) -join "`n") "MODDING_API_REFERENCE_PATH=$configuredNormalizedTarget"
    Assert-Contains (($configuredOutput | ForEach-Object { [string]$_ }) -join "`n") "MODDING_API_SELECTOR=tag:v1.0.0"
    if ((Invoke-Git $configuredTarget @("rev-parse", "HEAD")).Trim() -ne $releaseCommit.Trim()) {
        Fail-Test "preferences selector should drive the requested tag"
    }

    $userHome = Join-Path $TestRoot "user-home"
    $env:MODDING_API_TEST_HOME = $userHome
    $userOutput = @(& $Cloner -Scope user -Selector latest -MetadataFile $metadata 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "user-scoped clone should succeed: $($userOutput -join [Environment]::NewLine)"
    }
    $userTarget = Join-Path $userHome ".skills\blasphemous-modding-helper\references\modding-api"
    $userPreferences = Join-Path $userHome ".skills\blasphemous-modding-helper\preferences.md"
    $userNormalizedTarget = [System.IO.Path]::GetFullPath($userTarget)
    Assert-Contains (($userOutput | ForEach-Object { [string]$_ }) -join "`n") "MODDING_API_REFERENCE_PATH=$userNormalizedTarget"
    if (-not (Test-Path -LiteralPath (Join-Path $userTarget ".git"))) {
        Fail-Test "user scope should use the approved reference path"
    }
    Assert-Contains (Get-Content -LiteralPath $userPreferences -Raw) "modding_api_reference_path: $userNormalizedTarget"
    if ($null -eq $previousHome) {
        Remove-Item Env:MODDING_API_TEST_HOME -ErrorAction SilentlyContinue
    }
    else {
        $env:MODDING_API_TEST_HOME = $previousHome
    }
    $tagTarget = Join-Path $TestRoot "tag-reference"
    $tagOutput = @(& $Cloner -TargetPath $tagTarget -Selector tag:v1.0.0 -MetadataFile $metadata 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "explicit tag clone should succeed: $($tagOutput -join [Environment]::NewLine)"
    }
    Assert-Contains (($tagOutput | ForEach-Object { [string]$_ }) -join "`n") "MODDING_API_SELECTOR_KIND=tag"
    if ((Invoke-Git $tagTarget @("rev-parse", "HEAD")).Trim() -ne $releaseCommit.Trim()) {
        Fail-Test "tag selector should resolve the tag commit"
    }
    @(& git -C $tagTarget symbolic-ref --quiet --short HEAD 2>$null)
    if ($LASTEXITCODE -eq 0) {
        Fail-Test "explicit tag clone should use detached HEAD"
    }

    $branchTarget = Join-Path $TestRoot "branch-reference"
    $branchPreferences = Join-Path $TestRoot "branch-preferences.md"
    $branchOutput = @(& $Cloner -TargetPath $branchTarget -PreferencesFile $branchPreferences -Selector branch:dev -MetadataFile (Join-Path $TestRoot "dev.json") 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "explicit branch clone should succeed: $($branchOutput -join [Environment]::NewLine)"
    }
    Assert-Contains (($branchOutput | ForEach-Object { [string]$_ }) -join "`n") "MODDING_API_SELECTOR_KIND=branch"
    if ((Invoke-Git $branchTarget @("rev-parse", "HEAD")).Trim() -ne $devCommit.Trim()) {
        Fail-Test "branch selector should resolve the branch commit"
    }
    if ((Invoke-Git $branchTarget @("branch", "--show-current")).Trim() -ne "dev") {
        Fail-Test "branch selector should create the requested local branch"
    }
    if ((Invoke-Git $branchTarget @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")).Trim() -ne "origin/dev") {
        Fail-Test "branch selector should track origin/dev"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $branchTarget ".git\shallow"))) {
        Fail-Test "branch clone should be shallow"
    }
    Assert-Contains (Get-Content -LiteralPath $branchPreferences -Raw) "modding_api_reference_selector: branch:dev"

    $commitTarget = Join-Path $TestRoot "commit-reference"
    $commitOutput = @(& $Cloner -TargetPath $commitTarget -Selector ("commit:" + $devCommit.Trim()) 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "explicit commit clone should succeed: $($commitOutput -join [Environment]::NewLine)"
    }
    Assert-Contains (($commitOutput | ForEach-Object { [string]$_ }) -join "`n") "MODDING_API_SELECTOR_KIND=commit"
    if ((Invoke-Git $commitTarget @("rev-parse", "HEAD")).Trim() -ne $devCommit.Trim()) {
        Fail-Test "commit selector should resolve the requested commit"
    }
    @(& git -C $commitTarget symbolic-ref --quiet --short HEAD 2>$null)
    if ($LASTEXITCODE -eq 0) {
        Fail-Test "explicit commit clone should use detached HEAD"
    }

    $powerShell = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
    if ([string]::IsNullOrWhiteSpace($powerShell)) {
        $powerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
    }
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $existingOutput = @(& $powerShell -NoProfile -ExecutionPolicy Bypass -File $Cloner -TargetPath $tagTarget -Selector tag:v1.0.0 -MetadataFile $metadata 2>&1)
        $existingExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($existingExitCode -eq 0) {
        Fail-Test "existing target should be rejected"
    }
    $existingText = ($existingOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-Contains $existingText "[ERROR REPORT]"
    Assert-Contains $existingText "already exists"
    Assert-Contains $existingText "current_head:"
    Assert-Contains $existingText "worktree_state:"
    Assert-Contains $existingText "network_state:"
    Assert-Contains $existingText "next_step:"

    $skipPreferences = Join-Path $TestRoot "skip-preferences.md"
    Set-Content -LiteralPath $skipPreferences -Value "lightweight_source_code_path: legacy-source"
    $remoteOutput = @(& $Resolver -Selector latest -MetadataFile $metadata 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "skip-to-remote fallback should succeed"
    }
    Assert-Contains (($remoteOutput | ForEach-Object { [string]$_ }) -join "`n") "MODDING_API_SELECTOR_KIND=release"
    $skipText = Get-Content -LiteralPath $skipPreferences -Raw
    if ($skipText -match '(?m)^modding_api_reference_(path|selector):') {
        Fail-Test "skip-to-remote should not add local reference fields"
    }

    $setupDoc = Join-Path $ScriptDir "..\references\config\first-time-setup.md"
    $skillDoc = Join-Path $ScriptDir "..\SKILL.md"
    $referenceDoc = Join-Path $ScriptDir "..\references\sub-skills\referencing-modding-api.md"
    Assert-Contains (Get-Content -LiteralPath $setupDoc -Raw) "Skip"
    Assert-Contains (Get-Content -LiteralPath $setupDoc -Raw) "leave local reference fields absent"
    Assert-Contains (Get-Content -LiteralPath $skillDoc -Raw) "Referencing ModdingAPI"
    Assert-Contains (Get-Content -LiteralPath $referenceDoc -Raw) "Release-aware remote fallback"

    Write-Output "[OK] clone_modding_api.ps1 public behavior"
}
finally {
    if ($null -eq $previousRepository) {
        Remove-Item Env:MODDING_API_TEST_REPOSITORY -ErrorAction SilentlyContinue
    }
    else {
        $env:MODDING_API_TEST_REPOSITORY = $previousRepository
    }
    if ($null -eq $previousHome) {
        Remove-Item Env:MODDING_API_TEST_HOME -ErrorAction SilentlyContinue
    }
    else {
        $env:MODDING_API_TEST_HOME = $previousHome
    }
    if ($null -eq $previousTestMode) {
        Remove-Item Env:MODDING_API_TEST_MODE -ErrorAction SilentlyContinue
    }
    else {
        $env:MODDING_API_TEST_MODE = $previousTestMode
    }
    if (Test-Path -LiteralPath $TestRoot) {
        Remove-Item -LiteralPath $TestRoot -Recurse -Force
    }
}
