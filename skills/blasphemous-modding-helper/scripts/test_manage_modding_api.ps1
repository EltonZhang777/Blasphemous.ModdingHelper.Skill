<#
.SYNOPSIS
    Public-behavior tests for manage_modding_api.ps1.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Cloner = Join-Path $ScriptDir "clone_modding_api.ps1"
$Manager = Join-Path $ScriptDir "manage_modding_api.ps1"
$TestRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("modding-api-lifecycle-test-" + [guid]::NewGuid().ToString("N"))

function Fail-Test([string]$Message) {
    Write-Error "[FAIL] $Message"
    exit 1
}

function Assert-Contains([string]$Haystack, [string]$Needle) {
    if (-not $Haystack.Contains($Needle)) {
        Fail-Test "Expected output to contain: $Needle"
    }
}

function Assert-ErrorReport([string]$Text) {
    Assert-Contains $Text "[ERROR REPORT]"
    Assert-Contains $Text "operation:"
    Assert-Contains $Text "target_path:"
    Assert-Contains $Text "selector:"
    Assert-Contains $Text "current_head:"
    Assert-Contains $Text "worktree_state:"
    Assert-Contains $Text "network_state:"
    Assert-Contains $Text "cause:"
    Assert-Contains $Text "next_step:"
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
$previousNetworkFailure = $env:MODDING_API_TEST_NETWORK_FAILURE
$env:MODDING_API_TEST_MODE = "1"
$PowerShell = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if ([string]::IsNullOrWhiteSpace($PowerShell)) {
    $PowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
}

try {
    $remote = Join-Path $TestRoot "modding-api.git"
    $seed = Join-Path $TestRoot "seed"
    $target = Join-Path $TestRoot "reference"
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
    $releaseCommit = (Invoke-Git $seed @("rev-parse", "refs/tags/v1.0.0^{commit}")).Trim()
    Set-Content -LiteralPath $metadata -Value (@{
        tag_name = "v1.0.0"
        draft = $false
        prerelease = $false
        resolved_ref = "v1.0.0"
        resolved_commit = $releaseCommit
    } | ConvertTo-Json -Compress)

    $env:MODDING_API_TEST_REPOSITORY = $remote
    $cloneOutput = @(& $Cloner -TargetPath $target -Selector latest -MetadataFile $metadata 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "fixture clone should succeed: $($cloneOutput -join [Environment]::NewLine)"
    }

    $output = @(& $Manager -Operation check -TargetPath $target -Selector latest -Offline 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "matching offline check should succeed: $($output -join [Environment]::NewLine)"
    }
    $outputText = ($output | ForEach-Object { [string]$_ }) -join "`n"
    Assert-Contains $outputText "MODDING_API_OPERATION=check"
    Assert-Contains $outputText "MODDING_API_NETWORK=offline"
    Assert-Contains $outputText "MODDING_API_LOCK_MATCH=true"

    $lockFile = "$target.lock"
    $oldHead = (Invoke-Git $target @("rev-parse", "HEAD")).Trim()
    $oldLock = Get-Content -LiteralPath $lockFile -Raw
    Set-Content -LiteralPath (Join-Path $seed "README.md") -Value "new stable" -NoNewline
    Invoke-Git $seed @("commit", "-am", "second stable reference") | Out-Null
    Invoke-Git $seed @("tag", "-a", "v1.1.0", "-m", "new stable release") | Out-Null
    Invoke-Git $seed @("push", "origin", "main", "--tags") | Out-Null
    $newCommit = (Invoke-Git $seed @("rev-parse", "refs/tags/v1.1.0^{commit}")).Trim()
    $newMetadata = Join-Path $TestRoot "new-latest.json"
    Set-Content -LiteralPath $newMetadata -Value (@{
        tag_name = "v1.1.0"
        draft = $false
        prerelease = $false
        resolved_ref = "v1.1.0"
        resolved_commit = $newCommit
    } | ConvertTo-Json -Compress)

    $dryOutput = @(& $Manager -Operation update -TargetPath $target -Selector latest -MetadataFile $newMetadata -DryRun 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "dry-run update should succeed: $($dryOutput -join [Environment]::NewLine)"
    }
    $dryText = ($dryOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-Contains $dryText "MODDING_API_DRY_RUN=true"
    Assert-Contains $dryText "MODDING_API_CHECKOUT_CHANGED=true"
    if ((Invoke-Git $target @("rev-parse", "HEAD")).Trim() -ne $oldHead) {
        Fail-Test "dry-run update must not change HEAD"
    }
    if ((Get-Content -LiteralPath $lockFile -Raw) -ne $oldLock) {
        Fail-Test "dry-run update must not change lock state"
    }

    $updateOutput = @(& $Manager -Operation update -TargetPath $target -Selector latest -MetadataFile $newMetadata 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "online update should succeed: $($updateOutput -join [Environment]::NewLine)"
    }
    $updateText = ($updateOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-Contains $updateText "MODDING_API_OPERATION=update"
    Assert-Contains $updateText "MODDING_API_CHECKOUT_CHANGED=true"
    if ((Invoke-Git $target @("rev-parse", "HEAD")).Trim() -ne $newCommit) {
        Fail-Test "update should move the fixed reference to the resolved commit"
    }
    Assert-Contains (Get-Content -LiteralPath $lockFile -Raw) "resolved_tag: v1.1.0"
    Assert-Contains (Get-Content -LiteralPath $lockFile -Raw) "resolved_commit: $newCommit"

    $dryCheckLock = Get-Content -LiteralPath $lockFile -Raw
    $incompleteDryCheckLock = $dryCheckLock -replace '(?m)^checked_at:.*$', 'checked_at: '
    Set-Content -LiteralPath $lockFile -Value $incompleteDryCheckLock -NoNewline
    $dryCheckOutput = @(& $Manager -Operation check -TargetPath $target -Selector latest -MetadataFile $newMetadata -DryRun 2>&1)
    $dryCheckExitCode = $LASTEXITCODE
    if ($dryCheckExitCode -ne 0) {
        Fail-Test "dry-run check should succeed without writing a lock: $($dryCheckOutput -join [Environment]::NewLine)"
    }
    $dryCheckText = ($dryCheckOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-Contains $dryCheckText "MODDING_API_LOCK_MATCH=false"
    Assert-Contains $dryCheckText "MODDING_API_LOCK_UPDATED=false"
    Assert-Contains $dryCheckText "MODDING_API_CHECKED_AT=<not-written>"
    if ((Get-Content -LiteralPath $lockFile -Raw) -ne $incompleteDryCheckLock) {
        Fail-Test "dry-run check must not change lock state"
    }
    Set-Content -LiteralPath $lockFile -Value $dryCheckLock -NoNewline

    $defaultProject = Join-Path $TestRoot "default-project"
    $defaultPreferencesDirectory = Join-Path $defaultProject ".skills\blasphemous-modding-helper"
    New-Item -ItemType Directory -Force -Path $defaultPreferencesDirectory | Out-Null
    Set-Content -LiteralPath (Join-Path $defaultPreferencesDirectory "preferences.md") -Value @(
        "modding_api_reference_path: $target",
        "modding_api_reference_selector: latest"
    )
    Push-Location $defaultProject
    try {
        $defaultOutput = @(& $Manager -Operation check -Offline 2>&1)
        $defaultExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    if ($defaultExitCode -ne 0) {
        Fail-Test "project preferences should be discovered without explicit scope or path: $($defaultOutput -join [Environment]::NewLine)"
    }
    Assert-Contains (($defaultOutput | ForEach-Object { [string]$_ }) -join "`n") "MODDING_API_REFERENCE_PATH=$([System.IO.Path]::GetFullPath($target))"

    $missingSelectorProject = Join-Path $TestRoot "missing-selector-project"
    $missingSelectorPreferencesDirectory = Join-Path $missingSelectorProject ".skills\blasphemous-modding-helper"
    New-Item -ItemType Directory -Force -Path $missingSelectorPreferencesDirectory | Out-Null
    Set-Content -LiteralPath (Join-Path $missingSelectorPreferencesDirectory "preferences.md") -Value "modding_api_reference_path: $target"
    $selectorLockBefore = Get-Content -LiteralPath $lockFile -Raw
    $selectorLockBranch = $selectorLockBefore.Replace("selector: latest", "selector: branch:main")
    Set-Content -LiteralPath $lockFile -Value $selectorLockBranch -NoNewline
    Push-Location $missingSelectorProject
    try {
        $missingSelectorOutput = @(& $Manager -Operation check -Offline 2>&1)
        $missingSelectorExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    if ($missingSelectorExitCode -ne 1) {
        Fail-Test "missing preferences selector should default to latest and reject a branch lock"
    }
    Assert-Contains (($missingSelectorOutput | ForEach-Object { [string]$_ }) -join "`n") "requested selector latest"
    Set-Content -LiteralPath $lockFile -Value $selectorLockBefore -NoNewline

    $userDefaultProject = Join-Path $TestRoot "user-default-project"
    $userDefaultHome = Join-Path $TestRoot "user-default-home"
    $userDefaultPreferencesDirectory = Join-Path $userDefaultHome ".skills\blasphemous-modding-helper"
    New-Item -ItemType Directory -Force -Path $userDefaultProject,$userDefaultPreferencesDirectory | Out-Null
    Set-Content -LiteralPath (Join-Path $userDefaultPreferencesDirectory "preferences.md") -Value @(
        "modding_api_reference_path: $target",
        "modding_api_reference_selector: latest"
    )
    $env:MODDING_API_TEST_HOME = $userDefaultHome
    Push-Location $userDefaultProject
    try {
        $userDefaultOutput = @(& $Manager -Operation check -Offline 2>&1)
        $userDefaultExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    if ($userDefaultExitCode -ne 0) {
        Fail-Test "user preferences should be discovered when project preferences are absent: $($userDefaultOutput -join [Environment]::NewLine)"
    }
    if ($null -eq $previousHome) {
        Remove-Item Env:MODDING_API_TEST_HOME -ErrorAction SilentlyContinue
    }
    else {
        $env:MODDING_API_TEST_HOME = $previousHome
    }

    $shapeHead = (Invoke-Git $target @("rev-parse", "HEAD")).Trim()
    $shapeLock = Get-Content -LiteralPath $lockFile -Raw
    Invoke-Git $target @("checkout", "-b", "wrong-shape") | Out-Null
    $shapeOutput = @(& $Manager -Operation check -TargetPath $target -Selector latest -Offline 2>&1)
    $shapeExitCode = $LASTEXITCODE
    if ($shapeExitCode -ne 1) {
        Fail-Test "wrong fixed-reference checkout shape should return runtime exit code 1"
    }
    $shapeText = ($shapeOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-ErrorReport $shapeText
    Assert-Contains $shapeText "fixed selector requires detached HEAD"
    if ((Invoke-Git $target @("rev-parse", "HEAD")).Trim() -ne $shapeHead) {
        Fail-Test "wrong checkout shape must preserve HEAD"
    }
    if ((Get-Content -LiteralPath $lockFile -Raw) -ne $shapeLock) {
        Fail-Test "wrong checkout shape must preserve lock state"
    }
    Invoke-Git $target @("checkout", "--detach", "HEAD") | Out-Null

    $usageOutput = @(& $Manager -Operation invalid 2>&1)
    $usageExitCode = $LASTEXITCODE
    if ($usageExitCode -ne 2) {
        Fail-Test "invalid operation should return usage/configuration exit code 2"
    }
    Assert-ErrorReport (($usageOutput | ForEach-Object { [string]$_ }) -join "`n")

    Set-Content -LiteralPath (Join-Path $target "README.md") -Value "local edit" -NoNewline
    $dirtyOutput = @(& $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Manager -Operation update -TargetPath $target -Selector latest -MetadataFile $newMetadata 2>&1)
    $dirtyExitCode = $LASTEXITCODE
    if ($dirtyExitCode -ne 1) {
        Fail-Test "dirty worktree should return runtime exit code 1"
    }
    $dirtyText = ($dirtyOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-ErrorReport $dirtyText
    Assert-Contains $dirtyText "worktree_state: dirty"
    git -C $target checkout -- README.md 2>$null | Out-Null

    $wrongOrigin = Join-Path $TestRoot "wrong-origin.git"
    Invoke-Git $TestRoot @("init", "--bare", $wrongOrigin) | Out-Null
    Invoke-Git $target @("remote", "set-url", "origin", $wrongOrigin) | Out-Null
    $wrongOriginOutput = @(& $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Manager -Operation check -TargetPath $target -Selector latest -Offline 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "wrong origin should return runtime exit code 1"
    }
    Assert-ErrorReport (($wrongOriginOutput | ForEach-Object { [string]$_ }) -join "`n")
    Invoke-Git $target @("remote", "set-url", "origin", $remote) | Out-Null

    $validLock = Get-Content -LiteralPath $lockFile -Raw
    $badLock = $validLock.Replace("resolved_commit: $newCommit", "resolved_commit: $oldHead")
    Set-Content -LiteralPath $lockFile -Value $badLock -NoNewline
    $mismatchOutput = @(& $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Manager -Operation check -TargetPath $target -Selector latest -Offline 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "mismatching offline lock should return runtime exit code 1"
    }
    $mismatchText = ($mismatchOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-ErrorReport $mismatchText
    Assert-Contains $mismatchText "does not match locked commit"
    Set-Content -LiteralPath $lockFile -Value $validLock -NoNewline

    $offlineUpdateOutput = @(& $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Manager -Operation update -TargetPath $target -Selector latest -Offline 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "offline update should return runtime exit code 1"
    }
    $offlineUpdateText = ($offlineUpdateOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-ErrorReport $offlineUpdateText
    Assert-Contains $offlineUpdateText "cannot refresh a reference while offline"

    $missingLock = "$lockFile.saved"
    Move-Item -LiteralPath $lockFile -Destination $missingLock
    $missingLockOutput = @(& $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Manager -Operation check -TargetPath $target -Selector latest -Offline 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "offline check without a lock should return runtime exit code 1"
    }
    Assert-ErrorReport (($missingLockOutput | ForEach-Object { [string]$_ }) -join "`n")
    Move-Item -LiteralPath $missingLock -Destination $lockFile

    $missingTagFieldLock = Get-Content -LiteralPath $lockFile -Raw
    $missingTagFieldLock = $missingTagFieldLock -replace '(?m)^resolved_tag:.*\r?\n', ''
    Set-Content -LiteralPath $lockFile -Value $missingTagFieldLock -NoNewline
    $missingTagFieldOutput = @(& $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Manager -Operation check -TargetPath $target -Selector latest -Offline 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "lock without resolved_tag should return runtime exit code 1"
    }
    Assert-Contains (($missingTagFieldOutput | ForEach-Object { [string]$_ }) -join "`n") "lock state is incomplete"
    Set-Content -LiteralPath $lockFile -Value $validLock -NoNewline

    $tagTarget = Join-Path $TestRoot "tag-reference"
    $tagCloneOutput = @(& $Cloner -TargetPath $tagTarget -Selector tag:v1.0.0 -MetadataFile $metadata 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "tag fixture clone should succeed: $($tagCloneOutput -join [Environment]::NewLine)"
    }
    $tagCheckOutput = @(& $Manager -Operation check -TargetPath $tagTarget -Selector tag:v1.0.0 -MetadataFile $metadata 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "tag check should succeed: $($tagCheckOutput -join [Environment]::NewLine)"
    }
    Assert-Contains (($tagCheckOutput | ForEach-Object { [string]$_ }) -join "`n") "MODDING_API_SELECTOR_KIND=tag"

    $commitTarget = Join-Path $TestRoot "commit-reference"
    $commitCloneOutput = @(& $Cloner -TargetPath $commitTarget -Selector ("commit:" + $oldHead) 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "commit fixture clone should succeed: $($commitCloneOutput -join [Environment]::NewLine)"
    }
    $commitCheckOutput = @(& $Manager -Operation check -TargetPath $commitTarget -Selector ("commit:" + $oldHead) 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "commit check should succeed: $($commitCheckOutput -join [Environment]::NewLine)"
    }
    Assert-Contains (($commitCheckOutput | ForEach-Object { [string]$_ }) -join "`n") "MODDING_API_SELECTOR_KIND=commit"

    $commitMismatchLock = Get-Content -LiteralPath "$commitTarget.lock" -Raw
    $commitMismatchLock = $commitMismatchLock.Replace("selector: commit:$oldHead", "selector: commit:$newCommit")
    Set-Content -LiteralPath "$commitTarget.lock" -Value $commitMismatchLock -NoNewline
    $commitMismatchOutput = @(& $Manager -Operation check -TargetPath $commitTarget -Selector ("commit:" + $newCommit) -Offline 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "commit lock with a different resolved SHA should return runtime exit code 1"
    }
    Assert-Contains (($commitMismatchOutput | ForEach-Object { [string]$_ }) -join "`n") "does not match the commit selector"
    $commitLockText = Get-Content -LiteralPath "$commitTarget.lock" -Raw
    $commitLockText = $commitLockText.Replace("selector: commit:$newCommit", "selector: commit:$oldHead")
    Set-Content -LiteralPath "$commitTarget.lock" -Value $commitLockText -NoNewline

    $lockWithoutCheckTime = $validLock -replace '(?m)^checked_at:.*$', 'checked_at: '
    Set-Content -LiteralPath $lockFile -Value $lockWithoutCheckTime -NoNewline
    $relockOutput = @(& $Manager -Operation check -TargetPath $target -Selector latest -MetadataFile $newMetadata 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "check should rebuild an incomplete lock: $($relockOutput -join [Environment]::NewLine)"
    }
    $relockText = ($relockOutput | ForEach-Object { [string]$_ }) -join "`n"
    if (-not $relockText.Contains("MODDING_API_LOCK_UPDATED=true")) {
        Fail-Test "check should rebuild an incomplete lock: $relockText"
    }
    if ([string]::IsNullOrWhiteSpace((Get-Content -LiteralPath $lockFile | Where-Object { $_ -match '^checked_at:' }))) {
        Fail-Test "check should restore checked_at"
    }

    $env:MODDING_API_TEST_NETWORK_FAILURE = "1"
    $fallbackOutput = @(& $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Manager -Operation check -TargetPath $target -Selector latest 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "network-failed check should use a matching lock: $($fallbackOutput -join [Environment]::NewLine)"
    }
    $fallbackText = ($fallbackOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-Contains $fallbackText "MODDING_API_NETWORK=offline"
    Assert-Contains $fallbackText "MODDING_API_LOCK_MATCH=true"

    $networkMissingLock = "$lockFile.network-missing"
    Move-Item -LiteralPath $lockFile -Destination $networkMissingLock
    $networkMissingOutput = @(& $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Manager -Operation check -TargetPath $target -Selector latest 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "network-failed check without a lock should return runtime exit code 1"
    }
    $networkMissingText = ($networkMissingOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-ErrorReport $networkMissingText
    Assert-Contains $networkMissingText "network_state: offline"
    Move-Item -LiteralPath $networkMissingLock -Destination $lockFile

    $networkMismatchLock = Get-Content -LiteralPath $lockFile -Raw
    $networkMismatchLock = $networkMismatchLock.Replace("resolved_commit: $newCommit", "resolved_commit: $oldHead")
    Set-Content -LiteralPath $lockFile -Value $networkMismatchLock -NoNewline
    $networkMismatchOutput = @(& $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Manager -Operation check -TargetPath $target -Selector latest 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "network-failed check with a mismatching lock should return runtime exit code 1"
    }
    $networkMismatchText = ($networkMismatchOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-ErrorReport $networkMismatchText
    Assert-Contains $networkMismatchText "network_state: offline"
    Set-Content -LiteralPath $lockFile -Value $validLock -NoNewline

    if ($null -eq $previousNetworkFailure) {
        Remove-Item Env:MODDING_API_TEST_NETWORK_FAILURE -ErrorAction SilentlyContinue
    }
    else {
        $env:MODDING_API_TEST_NETWORK_FAILURE = $previousNetworkFailure
    }

    $missingTagMetadata = Join-Path $TestRoot "missing-tag.json"
    Set-Content -LiteralPath $missingTagMetadata -Value (@{
        resolved_ref = "missing-tag"
        resolved_commit = ("0" * 40)
    } | ConvertTo-Json -Compress)
    $missingTagOutput = @(& $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Manager -Operation update -TargetPath $tagTarget -Selector tag:missing-tag -MetadataFile $missingTagMetadata 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "missing tag should return runtime exit code 1"
    }
    Assert-ErrorReport (($missingTagOutput | ForEach-Object { [string]$_ }) -join "`n")

    $invalidTarget = Join-Path $TestRoot "invalid-reference"
    New-Item -ItemType Directory -Force -Path $invalidTarget | Out-Null
    Set-Content -LiteralPath (Join-Path $invalidTarget "README.md") -Value "not git" -NoNewline
    $invalidOutput = @(& $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Manager -Operation check -TargetPath $invalidTarget -Selector latest -Offline 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "non-Git target should return runtime exit code 1"
    }
    $invalidText = ($invalidOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-ErrorReport $invalidText
    Assert-Contains $invalidText "not a Git worktree"

    $missingCommit = "0" * 40
    $missingRefOutput = @(& $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Manager -Operation update -TargetPath $target -Selector ("commit:" + $missingCommit) 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "missing commit should return runtime exit code 1"
    }
    $missingRefText = ($missingRefOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-ErrorReport $missingRefText

    Invoke-Git $seed @("checkout", "-b", "dev") | Out-Null
    Set-Content -LiteralPath (Join-Path $seed "README.md") -Value "dev one" -NoNewline
    Invoke-Git $seed @("commit", "-am", "first dev reference") | Out-Null
    Invoke-Git $seed @("push", "--set-upstream", "origin", "dev") | Out-Null
    $devCommit1 = (Invoke-Git $seed @("rev-parse", "HEAD")).Trim()
    $devMetadata = Join-Path $TestRoot "dev.json"
    Set-Content -LiteralPath $devMetadata -Value (@{
        resolved_ref = "dev"
        resolved_commit = $devCommit1
    } | ConvertTo-Json -Compress)
    $branchTarget = Join-Path $TestRoot "branch-reference"
    $branchCloneOutput = @(& $Cloner -TargetPath $branchTarget -Selector branch:dev -MetadataFile $devMetadata 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "branch fixture clone should succeed: $($branchCloneOutput -join [Environment]::NewLine)"
    }

    $branchDryHead = (Invoke-Git $branchTarget @("rev-parse", "HEAD")).Trim()
    $branchDryLock = Get-Content -LiteralPath "$branchTarget.lock" -Raw
    Invoke-Git $branchTarget @("update-ref", "-d", "refs/remotes/origin/dev") | Out-Null
    $branchDryOutput = @(& $Manager -Operation update -TargetPath $branchTarget -Selector branch:dev -MetadataFile $devMetadata -DryRun 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "branch dry-run should plan a fetch when the remote-tracking ref is absent: $($branchDryOutput -join [Environment]::NewLine)"
    }
    $branchDryText = ($branchDryOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-Contains $branchDryText "MODDING_API_PLAN_REQUIRES_FETCH=true"
    if ((Invoke-Git $branchTarget @("rev-parse", "HEAD")).Trim() -ne $branchDryHead) {
        Fail-Test "branch dry-run must preserve HEAD"
    }
    if ((Get-Content -LiteralPath "$branchTarget.lock" -Raw) -ne $branchDryLock) {
        Fail-Test "branch dry-run must preserve lock state"
    }
    Invoke-Git $branchTarget @("update-ref", "refs/remotes/origin/dev", $branchDryHead) | Out-Null

    Set-Content -LiteralPath (Join-Path $seed "README.md") -Value "dev two" -NoNewline
    Invoke-Git $seed @("commit", "-am", "second dev reference") | Out-Null
    Invoke-Git $seed @("push", "origin", "dev") | Out-Null
    $devCommit2 = (Invoke-Git $seed @("rev-parse", "HEAD")).Trim()
    Set-Content -LiteralPath $devMetadata -Value (@{
        resolved_ref = "dev"
        resolved_commit = $devCommit2
    } | ConvertTo-Json -Compress)
    $branchUpdateOutput = @(& $Manager -Operation update -TargetPath $branchTarget -Selector branch:dev -MetadataFile $devMetadata 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "clean branch fast-forward should succeed: $($branchUpdateOutput -join [Environment]::NewLine)"
    }
    if ((Invoke-Git $branchTarget @("rev-parse", "HEAD")).Trim() -ne $devCommit2) {
        Fail-Test "branch update should fast-forward to the resolved commit"
    }

    Set-Content -LiteralPath (Join-Path $branchTarget "README.md") -Value "local branch" -NoNewline
    Invoke-Git $branchTarget @("commit", "-am", "local divergent reference") | Out-Null
    $localBranchCommit = (Invoke-Git $branchTarget @("rev-parse", "HEAD")).Trim()
    Set-Content -LiteralPath (Join-Path $seed "README.md") -Value "dev three" -NoNewline
    Invoke-Git $seed @("commit", "-am", "third dev reference") | Out-Null
    Invoke-Git $seed @("push", "origin", "dev") | Out-Null
    $devCommit3 = (Invoke-Git $seed @("rev-parse", "HEAD")).Trim()
    Set-Content -LiteralPath $devMetadata -Value (@{
        resolved_ref = "dev"
        resolved_commit = $devCommit3
    } | ConvertTo-Json -Compress)
    $branchLock = "$branchTarget.lock"
    $branchLockBefore = Get-Content -LiteralPath $branchLock -Raw
    $divergentOutput = @(& $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Manager -Operation update -TargetPath $branchTarget -Selector branch:dev -MetadataFile $devMetadata 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "divergent branch history should return runtime exit code 1"
    }
    $divergentText = ($divergentOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-ErrorReport $divergentText
    Assert-Contains $divergentText "divergent"
    if ((Invoke-Git $branchTarget @("rev-parse", "HEAD")).Trim() -ne $localBranchCommit) {
        Fail-Test "divergent update must preserve local branch HEAD"
    }
    if ((Get-Content -LiteralPath $branchLock -Raw) -ne $branchLockBefore) {
        Fail-Test "divergent update must preserve lock state"
    }

    $missingBranchMetadata = Join-Path $TestRoot "missing-branch.json"
    Set-Content -LiteralPath $missingBranchMetadata -Value (@{
        resolved_ref = "dev"
        resolved_commit = ("0" * 40)
    } | ConvertTo-Json -Compress)
    $missingBranchOutput = @(& $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Manager -Operation update -TargetPath $branchTarget -Selector branch:dev -MetadataFile $missingBranchMetadata 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "mismatching branch ref should return runtime exit code 1"
    }
    Assert-ErrorReport (($missingBranchOutput | ForEach-Object { [string]$_ }) -join "`n")

    $missingRemoteTarget = Join-Path $TestRoot "missing-remote-branch-reference"
    $missingRemoteCloneOutput = @(& $Cloner -TargetPath $missingRemoteTarget -Selector branch:dev -MetadataFile $devMetadata 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail-Test "missing remote branch fixture clone should succeed: $($missingRemoteCloneOutput -join [Environment]::NewLine)"
    }
    $missingRemoteHead = (Invoke-Git $missingRemoteTarget @("rev-parse", "HEAD")).Trim()
    Invoke-Git $missingRemoteTarget @("branch", "-m", "missing-branch") | Out-Null
    Invoke-Git $missingRemoteTarget @("update-ref", "refs/remotes/origin/missing-branch", $missingRemoteHead) | Out-Null
    Invoke-Git $missingRemoteTarget @("config", "branch.missing-branch.remote", "origin") | Out-Null
    Invoke-Git $missingRemoteTarget @("config", "branch.missing-branch.merge", "refs/heads/missing-branch") | Out-Null
    $missingRemoteMetadata = Join-Path $TestRoot "missing-remote-branch.json"
    Set-Content -LiteralPath $missingRemoteMetadata -Value (@{
        resolved_ref = "missing-branch"
        resolved_commit = $missingRemoteHead
    } | ConvertTo-Json -Compress)
    $missingRemoteLock = "$missingRemoteTarget.lock"
    $missingRemoteLockBefore = Get-Content -LiteralPath $missingRemoteLock -Raw
    $missingRemoteOutput = @(& $Manager -Operation update -TargetPath $missingRemoteTarget -Selector branch:missing-branch -MetadataFile $missingRemoteMetadata 2>&1)
    if ($LASTEXITCODE -ne 1) {
        Fail-Test "missing remote branch should return runtime exit code 1"
    }
    $missingRemoteText = ($missingRemoteOutput | ForEach-Object { [string]$_ }) -join "`n"
    Assert-ErrorReport $missingRemoteText
    Assert-Contains $missingRemoteText "Git operation failed"
    if ((Invoke-Git $missingRemoteTarget @("rev-parse", "HEAD")).Trim() -ne $missingRemoteHead) {
        Fail-Test "missing remote branch must preserve HEAD"
    }
    if ((Get-Content -LiteralPath $missingRemoteLock -Raw) -ne $missingRemoteLockBefore) {
        Fail-Test "missing remote branch must preserve lock state"
    }

    Write-Output "[OK] manage_modding_api.ps1 public behavior"
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
    if ($null -eq $previousNetworkFailure) {
        Remove-Item Env:MODDING_API_TEST_NETWORK_FAILURE -ErrorAction SilentlyContinue
    }
    else {
        $env:MODDING_API_TEST_NETWORK_FAILURE = $previousNetworkFailure
    }
    if (Test-Path -LiteralPath $TestRoot) {
        Remove-Item -LiteralPath $TestRoot -Recurse -Force
    }
}
