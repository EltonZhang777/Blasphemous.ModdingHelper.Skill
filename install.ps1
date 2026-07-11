<#
.SYNOPSIS
  Blasphemous Modding Helper - Unified Installer (Windows npx shim)
.DESCRIPTION
  Thin wrapper around bin/install.js (the unified Node installer).
  Detects AI coding agents on your machine and installs the skill
  for each one using its native install path.

  For flags, pass them as a single string to -InstallerArgs:
    .\install.ps1 -InstallerArgs "--dry-run --only claude-code"
  Or pipe from the web:
    irm https://raw.githubusercontent.com/.../install.ps1 | iex
.EXAMPLE
  irm https://raw.githubusercontent.com/EltonZhang777/Blasphemous.ModdingHelper.Skill/main/install.ps1 | iex
.EXAMPLE
  .\install.ps1 -InstallerArgs "--dry-run"
.EXAMPLE
  .\install.ps1 -InstallerArgs "--uninstall"
#>

function Install-Skill {
  param(
    [string[]]$InstallerArgs = @()
  )

  $ErrorActionPreference = "Stop"
  $Repo = "EltonZhang777/Blasphemous.ModdingHelper.Skill"

  # --- Require Node >= 18 ---
  $node = Get-Command node -ErrorAction SilentlyContinue
  if (-not $node) {
    Write-Error "Node.js (>=18) required. Install from https://nodejs.org"
    exit 1
  }
  $nodeMajor = [int](& node -p "process.versions.node.split('.')[0]")
  if ($nodeMajor -lt 18) {
    Write-Error "Node $nodeMajor too old. Need Node >=18. Upgrade: https://nodejs.org"
    exit 1
  }

  # --- If running from repo clone, use local installer ---
  if ($PSCommandPath) {
    $here = Split-Path -Parent $PSCommandPath
    $local = Join-Path $here "bin\install.js"
    if (Test-Path $local) {
      & node $local @InstallerArgs
      exit $LASTEXITCODE
    }
  }

  # --- Curl-pipe path: delegate to npx ---
  $npx = Get-Command npx -ErrorAction SilentlyContinue
  if (-not $npx) {
    Write-Error "npx required (ships with Node >=18). Reinstall Node.js."
    exit 1
  }

  & npx -y "github:$Repo" @InstallerArgs
  exit $LASTEXITCODE
}

Install-Skill -InstallerArgs $args

