<#
.SYNOPSIS
    Decompile Blasphemous game source code from Steam installation.

.DESCRIPTION
    This script:
    1. Verifies game file integrity via Steam validation
    2. Decompiles Assembly-CSharp.dll and Assembly-CSharp-firstpass.dll
    3. Creates a Visual Studio solution with both decompiled projects

    Designed to be run once as a one-time setup step.

.PARAMETER GamePath
    Path to the Blasphemous game installation directory.
    Default: "C:\Program Files (x86)\Steam\steamapps\common\Blasphemous"

.PARAMETER OutputPath
    Output directory for decompiled source code.
    Default: ../source_code (relative to this script location)

.EXAMPLE
    $SkillRoot = 'C:\path\to\blasphemous-modding-helper'
    & (Join-Path $SkillRoot 'scripts\decompile_source.ps1')

.EXAMPLE
    $SkillRoot = 'C:\path\to\blasphemous-modding-helper'
    & (Join-Path $SkillRoot 'scripts\decompile_source.ps1') -GamePath "D:\Games\Blasphemous" -OutputPath "D:\Projects\blasphemous-source"
#>
param(
    [Parameter(Mandatory = $false)]
    [string]$GamePath = "C:\Program Files (x86)\Steam\steamapps\common\Blasphemous",

    [Parameter(Mandatory = $false)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
$InformationPreference = "Continue"

# ─── Configuration ────────────────────────────────────────────────
$ManagedRelativePath = "Blasphemous_Data\Managed"
$DllNames = @("Assembly-CSharp.dll", "Assembly-CSharp-firstpass.dll")
$SteamAppId = "774361"
$PollIntervalSec = 5
$PollTimeoutSec = 60
$SolutionName = "BlasphemousSourceCode"

# ─── Helper Functions ─────────────────────────────────────────────
function Write-Step   { Write-Host "`n[STEP] $($args[0])" -ForegroundColor Cyan }
function Write-Info   { Write-Host "  [INFO] $($args[0])" }
function Write-OK     { Write-Host "  [OK]   $($args[0])" -ForegroundColor Green }
function Write-Warn   { Write-Host "  [WARN] $($args[0])" -ForegroundColor Yellow }
function Write-Fail   { Write-Host "`n[FAIL] $($args[0])" -ForegroundColor Red; exit 1 }

# ─── 1. Admin Check ──────────────────────────────────────────────
Write-Step "Checking administrator privileges..."
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warn "This script requires Administrator privileges."
    Write-Warn "Please re-run as Administrator."
    Write-Host ""
    Write-Host "  === Calling Agent Action Required ==="
    Write-Host "  Re-invoke this script with elevated privileges:"
    Write-Host "    Right-click PowerShell -> 'Run as Administrator'"
    Write-Host "  Or use Start-Process with -Verb RunAs"
    Write-Host "  ======================================="
    exit 1
}
Write-OK "Running with administrator privileges."

# ─── 2. Validate Game Path ───────────────────────────────────────
Write-Step "Validating game path..."
try {
    $ManagedPath = Join-Path -Path $GamePath -ChildPath $ManagedRelativePath

    # Validate game root exists
    if (-not (Test-Path -Path $GamePath)) {
        throw "Game installation directory not found: `"$GamePath`""
    }

    # Validate Managed subdirectory exists
    if (-not (Test-Path -Path $ManagedPath)) {
        throw "Managed directory not found at: `"$ManagedPath`""
    }

    Write-OK "Game installation directory: $GamePath"
    Write-OK "Managed directory: $ManagedPath"
}
catch {
    Write-Fail @"
Failed to validate game path: $($_.Exception.Message)

If your game is installed in a custom location, provide the correct path:
    & (Join-Path $SkillRoot 'scripts\decompile_source.ps1') -GamePath "D:\Your\Custom\Path\Blasphemous"

Default path was: "$GamePath"
"@
}

# ─── 3. Resolve Output Path ─────────────────────────────────────
Write-Step "Resolving output path..."
if (-not $OutputPath) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $OutputPath = Join-Path -Path $ScriptDir -ChildPath "..\source_code"
    $OutputPath = Resolve-Path -Path $OutputPath -ErrorAction SilentlyContinue
    if (-not $OutputPath) {
        $OutputPath = (Join-Path -Path $ScriptDir -ChildPath "..\source_code")
    }
    Write-Info "Output path not specified. Defaulting to: $OutputPath"
}
# Create output directory (Force = no error if exists)
New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null
Write-OK "Output path ready: $OutputPath"

# ─── 4. Delete Existing DLLs (force Steam to restore clean copies) ─
Write-Step "Removing existing DLLs to trigger Steam validation..."
foreach ($dll in $DllNames) {
    $dllPath = Join-Path -Path $ManagedPath -ChildPath $dll
    if (Test-Path -Path $dllPath) {
        Remove-Item -Path $dllPath -Force
        Write-Info "Deleted: $dll"
    }
    else {
        Write-Info "Already absent: $dll"
    }
}

# ─── 5. Launch Steam File Integrity Validation (non-blocking) ────
Write-Step "Launching Steam file integrity validation (AppID: $SteamAppId)..."
$steamUri = "steam://validate/$SteamAppId"
try {
    Start-Process $steamUri
}
catch {
    Write-Warn "Start-Process for Steam URI failed: $_"
    Write-Warn "Attempting to launch Steam manually..."
    try {
        $steamExe = "${env:ProgramFiles(x86)}\Steam\steam.exe"
        if (Test-Path $steamExe) {
            Start-Process -FilePath $steamExe -ArgumentList "steam://validate/$SteamAppId"
        }
        else {
            Write-Fail "Could not launch Steam. Please open Steam manually and verify game files."
        }
    }
    catch {
        Write-Fail "Could not launch Steam. Please open Steam manually and verify game files (Library > Blasphemous > Properties > Installed Files > Verify integrity)."
    }
}
Write-Info "Steam validation launched. Polling for DLL restoration..."

# ─── 6. Poll for DLL Restoration (60s timeout) ───────────────────
$elapsed = 0
$allRestored = $false
while ($elapsed -lt $PollTimeoutSec) {
    Start-Sleep -Seconds $PollIntervalSec
    $elapsed += $PollIntervalSec

    $allExist = $true
    foreach ($dll in $DllNames) {
        $dllPath = Join-Path -Path $ManagedPath -ChildPath $dll
        if (-not (Test-Path -Path $dllPath)) {
            $allExist = $false
            break
        }
    }

    if ($allExist) {
        $allRestored = $true
        Write-OK "All DLLs restored after ~${elapsed}s."
        break
    }

    Write-Info "Waiting for DLLs... (${elapsed}s / ${PollTimeoutSec}s)"
}

if (-not $allRestored) {
    Write-Fail @"
Timed out after ${PollTimeoutSec}s. DLLs were not restored by Steam.
Possible causes:
  1. Steam is not running — open Steam manually
  2. Game not owned on this Steam account
  3. Validation takes longer than expected

Manual fix:
  Open Steam → Library → Blasphemous → Properties → Installed Files → Verify integrity of game files

After manual verification, re-run this script.
"@
}

# Verify DLLs are valid (non-zero size)
foreach ($dll in $DllNames) {
    $dllPath = Join-Path -Path $ManagedPath -ChildPath $dll
    $fileInfo = Get-Item -Path $dllPath
    if ($fileInfo.Length -eq 0) {
        Write-Fail "DLL is empty after restoration: $dll. Re-run Steam validation."
    }
    $sizeMB = [math]::Round($fileInfo.Length / 1MB, 2)
    Write-OK "Verified: $dll ($sizeMB MB)"
}
Write-OK "All DLLs restored and verified successfully."

# ─── 7. Check .NET SDK ───────────────────────────────────────────
Write-Step "Checking .NET SDK installation..."
try {
    $dotnetVersion = dotnet --version
    Write-OK ".NET SDK detected: version $dotnetVersion"
}
catch {
    Write-Fail @"
.NET SDK is not installed.
Please install .NET SDK from: https://dotnet.microsoft.com/download
After installation, re-run this script.
"@
}

# ─── 8. Check / Install ilspycmd ─────────────────────────────────
Write-Step "Ensuring ilspycmd is installed..."
try {
    $globalTools = dotnet tool list --global
    if ($globalTools -match "ilspycmd") {
        Write-OK "ilspycmd is already installed."
    }
    else {
        Write-Info "Installing ilspycmd globally..."
        $installLog = dotnet tool install --global ilspycmd 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "Failed to install ilspycmd. Log: $installLog"
        }
        Write-OK "ilspycmd installed successfully."
        # Refresh PATH for current session
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
        $env:Path = "$userPath;$machinePath"
    }
}
catch {
    Write-Fail "Failed to check/install ilspycmd: $_"
}

# ─── 9. Decompile Assembly-CSharp.dll ────────────────────────────
Write-Step "Decompiling Assembly-CSharp.dll..."
$dll1 = Join-Path -Path $ManagedPath -ChildPath "Assembly-CSharp.dll"
$outDir1 = Join-Path -Path $OutputPath -ChildPath "Assembly-CSharp"
& ilspycmd --nested-directories -p -o $outDir1 $dll1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "ilspycmd failed for Assembly-CSharp.dll (exit code: $LASTEXITCODE)"
}
Write-OK "Assembly-CSharp.dll → $outDir1"

# ─── 10. Decompile Assembly-CSharp-firstpass.dll ─────────────────
Write-Step "Decompiling Assembly-CSharp-firstpass.dll..."
$dll2 = Join-Path -Path $ManagedPath -ChildPath "Assembly-CSharp-firstpass.dll"
$outDir2 = Join-Path -Path $OutputPath -ChildPath "Assembly-CSharp-firstpass"
& ilspycmd --nested-directories -p -o $outDir2 $dll2
if ($LASTEXITCODE -ne 0) {
    Write-Fail "ilspycmd failed for Assembly-CSharp-firstpass.dll (exit code: $LASTEXITCODE)"
}
Write-OK "Assembly-CSharp-firstpass.dll → $outDir2"

# ─── 11. Find .csproj Files ──────────────────────────────────────
Write-Step "Locating .csproj files from decompiled output..."
$csprojFiles = @()

$proj1 = Get-ChildItem -Path $outDir1 -Filter "*.csproj" -Recurse | Select-Object -First 1
$proj2 = Get-ChildItem -Path $outDir2 -Filter "*.csproj" -Recurse | Select-Object -First 1

if ($proj1) { $csprojFiles += $proj1.FullName; Write-Info "Found: $($proj1.Name)" }
if ($proj2) { $csprojFiles += $proj2.FullName; Write-Info "Found: $($proj2.Name)" }

if ($csprojFiles.Count -eq 0) {
    Write-Warn "No .csproj files found. Skipping solution creation."
}
else {
    Write-OK "Found $($csprojFiles.Count) project file(s)."

    # ─── 12. Create Solution and Add Projects ────────────────────
    Write-Step "Creating Visual Studio solution..."
    $slnPath = Join-Path -Path $OutputPath -ChildPath "$SolutionName.sln"

    # Remove existing .sln if present (clean start)
    if (Test-Path -Path $slnPath) {
        Remove-Item -Path $slnPath -Force
        Write-Info "Removed existing solution: $slnPath"
    }

    # Create new solution
    dotnet new sln -n $SolutionName -o $OutputPath 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to create .sln file."
    }

    # Add each project
    foreach ($csproj in $csprojFiles) {
        $addLog = dotnet sln $slnPath add $csproj 2>&1
        if ($LASTEXITCODE -eq 0) {
            $relPath = $csproj -replace [regex]::Escape($OutputPath), "."
            Write-OK "Added to solution: $relPath"
        }
        else {
            Write-Warn "Failed to add project: $csproj. Log: $addLog"
        }
    }
    Write-OK "Solution ready: $slnPath"
}

# ─── Done ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Decompilation Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Game:     $GamePath"
Write-Host "  Output:   $OutputPath"
if (Test-Path $slnPath) {
    Write-Host "  Solution: $slnPath"
}
Write-Host "  Projects: $($csprojFiles.Count) decompiled"
Write-Host ""
Write-Host "Next step:" -ForegroundColor Yellow
Write-Host "  Update preferences.md 'full_source_code_path' to:" -ForegroundColor Yellow
Write-Host "    $OutputPath" -ForegroundColor White
