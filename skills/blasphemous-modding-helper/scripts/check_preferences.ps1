<#
.SYNOPSIS
    Check where preferences.md exists for blasphemous-modding-helper.

.DESCRIPTION
    Outputs one of: "project", "user", or nothing (not found).
    - "project" = .skills/blasphemous-modding-helper/preferences.md exists
    - "user"    = $HOME/.skills/blasphemous-modding-helper/preferences.md exists
    - (empty)   = neither found

    Usage: dot-calling agent captures stdout to determine scope.
.EXAMPLE
    $SkillRoot = 'C:\path\to\blasphemous-modding-helper'
    $scope = & (Join-Path $SkillRoot 'scripts\check_preferences.ps1')
#>

$projectPath = ".skills/blasphemous-modding-helper/preferences.md"
$userPath    = "$HOME/.skills/blasphemous-modding-helper/preferences.md"

if (Test-Path $projectPath) {
    "project"
}
elseif (Test-Path $userPath) {
    "user"
}
