<#
.SYNOPSIS
  Blasphemous Modding Helper — Unified Installer (Windows / PowerShell shim)

.DESCRIPTION
  Thin wrapper around bin/install.js (the unified Node installer).
  Detects AI coding agents on your machine and installs the skill
  for each one using its native install path.

  Why a Node installer? install.sh + install.ps1 used to duplicate logic
  and constantly drifted. One Node script works everywhere without
  bash/PowerShell quoting bugs.

  Why a param() block wrapped in a function? `irm | iex` executes this
  file as a string: script-path variables ($PSCommandPath) are $null and
  a top-level param() block cannot receive arguments through a pipe.
  Wrapping in a function and forwarding $args keeps one script working
  for both the pipe path and the local-clone path.

.PARAMETER InstallerArgs
  Pass flags to the Node installer as a string array.
  Examples:
    -InstallerArgs "--dry-run"
    -InstallerArgs "--only trae-cn"
    -InstallerArgs "--all"

.EXAMPLE
  irm https://raw.githubusercontent.com/EltonZhang777/Blasphemous.ModdingHelper.Skill/main/install.ps1 | iex

.EXAMPLE
  .\install.ps1 -InstallerArgs "--dry-run"

.EXAMPLE
  .\install.ps1 -InstallerArgs "--only trae-cn"

.EXAMPLE
  .\install.ps1 -InstallerArgs "--uninstall"
#>

function Install-Skill {
  param(
    [string[]]$InstallerArgs = @()
  )

  $ErrorActionPreference = "Stop"
  $Repo = "EltonZhang777/Blasphemous.ModdingHelper.Skill"

  # ── Helper to wait for key press (handles non-interactive terminals) ──────
  function Wait-ForKeyPress {
    try {
      $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    } catch {
      # Non-interactive terminal (e.g. CI, AI agent) — just exit
    }
  }

  # ── Check Node ≥18 ────────────────────────────────────────────────────────
  $node = Get-Command node -ErrorAction SilentlyContinue
  if (-not $node) {
    Write-Host "[✗] Node.js (≥18) required." -ForegroundColor Red
    Write-Host "    Install from https://nodejs.org" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "    Or via winget:" -ForegroundColor Gray
    Write-Host "      winget install OpenJS.NodeJS.LTS" -ForegroundColor Gray
    Wait-ForKeyPress
    exit 1
  }

  $nodeMajor = [int](& node -p "process.versions.node.split('.')[0]")
  if ($nodeMajor -lt 18) {
    Write-Host "[✗] Node $nodeMajor too old. Need Node ≥18." -ForegroundColor Red
    Write-Host "    Upgrade: https://nodejs.org" -ForegroundColor Cyan
    Wait-ForKeyPress
    exit 1
  }

  # ── Local clone path ──────────────────────────────────────────────────────
  # When the script runs from a repo clone, use the local bin/install.js
  # directly. This avoids the npx round-trip and keeps offline installs
  # working. $PSCommandPath is $null when piped via `irm | iex`, so the
  # guard below correctly skips this block for the web-pipe path.
  if ($PSCommandPath) {
    $here = Split-Path -Parent $PSCommandPath
    $local = Join-Path $here "bin\install.js"
    if (Test-Path $local) {
      Write-Host "[*] Using local installer: $local" -ForegroundColor Cyan
      & node $local @InstallerArgs
      $exitCode = $LASTEXITCODE
      if ($exitCode -ne 0) {
        Write-Host "[✗] Installer exited with code $exitCode" -ForegroundColor Red
      }
      Write-Host ""
      Wait-ForKeyPress
      exit $exitCode
    }
  }

  # ── Curl-pipe path: delegate to npx ───────────────────────────────────────
  # When the script is piped from the web, $PSCommandPath is null so we
  # fall through to npx. This downloads the package from GitHub and runs
  # bin/install.js remotely.
  $npx = Get-Command npx -ErrorAction SilentlyContinue
  if (-not $npx) {
    Write-Host "[✗] npx required (ships with Node ≥18)." -ForegroundColor Red
    Write-Host "    Reinstall Node.js from https://nodejs.org" -ForegroundColor Cyan
    Wait-ForKeyPress
    exit 1
  }

  Write-Host "[*] Downloading installer via npx..." -ForegroundColor Cyan
  & npx -y "github:$Repo" @InstallerArgs
  $exitCode = $LASTEXITCODE

  if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "[✗] npx installer failed with code $exitCode" -ForegroundColor Red
    Write-Host "    Possible causes:" -ForegroundColor Yellow
    Write-Host "    - Network issue (try again or use a VPN)" -ForegroundColor Yellow
    Write-Host "    - npm registry mirror doesn't support github: protocol" -ForegroundColor Yellow
    Write-Host "    - Git is not installed or not in PATH" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    Alternative: clone the repo and run locally:" -ForegroundColor Cyan
    Write-Host "      git clone https://github.com/$Repo" -ForegroundColor Gray
    Write-Host "      cd Blasphemous.ModdingHelper.Skill" -ForegroundColor Gray
    Write-Host "      .\install.ps1" -ForegroundColor Gray
  }

  Write-Host ""
  Wait-ForKeyPress
  exit $exitCode
}

# $args is the automatic variable: populated when run as a file
# (`pwsh install.ps1 --all`), empty under `irm | iex`.
Install-Skill -InstallerArgs $args
