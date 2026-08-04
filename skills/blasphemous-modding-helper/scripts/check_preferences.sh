#!/usr/bin/env bash
#
# Check where preferences.md exists for blasphemous-modding-helper.
#
# Outputs one of: "project", "user", or nothing (not found).
#   - "project" = .skills/blasphemous-modding-helper/preferences.md exists
#   - "user"    = $HOME/.skills/blasphemous-modding-helper/preferences.md exists
#   - (empty)   = neither found
#
# Usage: capture stdout to determine scope.
#

project_path=".skills/blasphemous-modding-helper/preferences.md"
user_path="$HOME/.skills/blasphemous-modding-helper/preferences.md"

if [ -f "$project_path" ]; then
    echo "project"
elif [ -f "$user_path" ]; then
    echo "user"
fi
