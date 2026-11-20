<#
.SYNOPSIS
  Blasphemous Modding Helper — PowerShell installer wrapper

.DESCRIPTION
  Run this script from a cloned repository. It forwards every argument
  to the adjacent bin/install.js.

.EXAMPLE
  .\install.ps1 --path <AGENT_SKILLS_DIR>\blasphemous-modding-helper

.EXAMPLE
  .\install.ps1 --path <AGENT_SKILLS_DIR>\blasphemous-modding-helper --dry-run

.EXAMPLE
  .\install.ps1 --path <AGENT_SKILLS_DIR>\blasphemous-modding-helper --uninstall
#>

function Install-Skill {
  param(
    [string[]]$InstallerArgs = @()
  )

  $ErrorActionPreference = "Stop"

  if (-not $PSCommandPath -or [IO.Path]::GetFileName($PSCommandPath) -ine "install.ps1") {
    Write-Host "[✗] install.ps1 must be run from a cloned checkout." -ForegroundColor Red
    Write-Host "    Clone the repository, then run the local install.ps1." -ForegroundColor Cyan
    exit 1
  }

  $here = Split-Path -Parent $PSCommandPath
  $local = Join-Path $here "bin\install.js"
  if (-not (Test-Path -LiteralPath $local -PathType Leaf)) {
    Write-Host "[✗] The local installer was not found at $local" -ForegroundColor Red
    Write-Host "    Clone the repository and run the local install.ps1." -ForegroundColor Cyan
    exit 1
  }

  $node = Get-Command node -ErrorAction SilentlyContinue
  if (-not $node) {
    Write-Host "[✗] Node.js (≥18) required." -ForegroundColor Red
    Write-Host "    Install from https://nodejs.org" -ForegroundColor Cyan
    exit 1
  }

  $nodeVersion = & node -p "process.versions.node.split('.')[0]"
  if ($nodeVersion -notmatch '^\d+$' -or [int]$nodeVersion -lt 18) {
    Write-Host "[✗] Node $nodeVersion too old. Need Node ≥18." -ForegroundColor Red
    Write-Host "    Upgrade: https://nodejs.org" -ForegroundColor Cyan
    exit 1
  }

  # Windows PowerShell 5.1 can fold options into a quoted --path ending in a slash.
  $foldedPath = $null
  $foldedOptions = @()
  $rawPath = [regex]::Match([Environment]::CommandLine, '--path\s+"(?<path>[^"]*\\)"(?<rest>.*)$')
  if ($rawPath.Success) {
    $foldedPath = $rawPath.Groups["path"].Value
    $foldedOptions = @($rawPath.Groups["rest"].Value.Trim() -split '\s+' | Where-Object { $_ })
    $unsupported = @($foldedOptions | Where-Object { $_ -notmatch '^--(?:dry-run|uninstall|help)$' })
    if ($unsupported.Count -gt 0) {
      Write-Host "[✗] The wrapped --path ends in a backslash and its remaining arguments could not be parsed." -ForegroundColor Red
      Write-Host "    Remove the trailing backslash and run the wrapper again." -ForegroundColor Cyan
      exit 2
    }
  }

  function ConvertTo-InstallerPath([string]$pathValue) {
    if ($env:OS -ne "Windows_NT" -or -not $pathValue.EndsWith('\')) {
      return $pathValue
    }
    if ($pathValue -match '^[A-Za-z]:\\+$' -or $pathValue -match '^\\+$') {
      return $pathValue.Substring(0, $pathValue.Length - 1) + '/'
    }
    return $pathValue.TrimEnd('\')
  }

  $normalizedArgs = @()
  for ($index = 0; $index -lt $InstallerArgs.Count; $index++) {
    $current = $InstallerArgs[$index]
    $normalizedArgs += $current
    if ($current -eq "--path" -and $index + 1 -lt $InstallerArgs.Count) {
      $index++
      $pathValue = $InstallerArgs[$index]
      if ($foldedPath -and $pathValue -cne $foldedPath) {
        $normalizedArgs += ConvertTo-InstallerPath $foldedPath
        $normalizedArgs += $foldedOptions
        break
      }
      $normalizedArgs += ConvertTo-InstallerPath $pathValue
    }
  }

  & node $local @normalizedArgs
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    Write-Host "[✗] Installer exited with code $exitCode" -ForegroundColor Red
  }
  exit $exitCode
}

# $args is populated when run as a file and empty under Invoke-Expression.
Install-Skill -InstallerArgs $args
