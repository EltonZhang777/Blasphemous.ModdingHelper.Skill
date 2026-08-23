#!/usr/bin/env bash
#
# Decompile Blasphemous game source code from Steam installation (macOS/Linux).
#
# This script:
#   1. Verifies game file integrity via Steam validation
#   2. Decompiles Assembly-CSharp.dll and Assembly-CSharp-firstpass.dll
#   3. Creates a Visual Studio solution with both decompiled projects
#
# Designed to be run once as a one-time setup step.
#
# Usage:
#   SKILL_ROOT=/path/to/blasphemous-modding-helper
#   bash "$SKILL_ROOT/scripts/decompile_source.sh"
#   bash "$SKILL_ROOT/scripts/decompile_source.sh" -g /path/to/Blasphemous -o /path/to/output
#
# Arguments:
#   -g <path>  Game installation directory (auto-detected by OS)
#   -o <path>  Output directory (default: ../source_code relative to script)
#

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANAGED_RELATIVE_PATH="Blasphemous_Data/Managed"
DLL_NAMES=("Assembly-CSharp.dll" "Assembly-CSharp-firstpass.dll")
STEAM_APP_ID="774361"
POLL_INTERVAL_SEC=5
POLL_TIMEOUT_SEC=60
SOLUTION_NAME="BlasphemousSourceCode"

# Detect OS and set default game path
OS="$(uname -s)"
case "$OS" in
    Darwin)
        DEFAULT_GAME_PATH="$HOME/Library/Application Support/Steam/steamapps/common/Blasphemous"
        STEAM_OPEN_CMD="open"
        ;;
    Linux)
        if [ -d "$HOME/.steam/steam/steamapps/common" ]; then
            DEFAULT_GAME_PATH="$HOME/.steam/steam/steamapps/common/Blasphemous"
        else
            DEFAULT_GAME_PATH="$HOME/.local/share/Steam/steamapps/common/Blasphemous"
        fi
        STEAM_OPEN_CMD="xdg-open"
        ;;
    *)
        echo "[FAIL] Unsupported OS: $OS (this script supports macOS and Linux only)"
        exit 1
        ;;
esac

# ─── Parse Arguments ──────────────────────────────────────────────
GAME_PATH="$DEFAULT_GAME_PATH"
OUTPUT_PATH=""

while getopts "g:o:h" opt; do
    case "$opt" in
        g) GAME_PATH="$OPTARG" ;;
        o) OUTPUT_PATH="$OPTARG" ;;
        h)
            echo "Usage: $0 [-g game_path] [-o output_path]"
            echo "  -g  Game installation directory (default: auto-detected)"
            echo "  -o  Output directory (default: ../source_code)"
            exit 0
            ;;
        *) exit 1 ;;
    esac
done

# ─── Helper Functions ─────────────────────────────────────────────
step()  { echo ""; echo "[STEP] $*"; }
info()  { echo "  [INFO] $*"; }
ok()    { echo "  [OK]   $*"; }
warn()  { echo "  [WARN] $*"; }
fail()  { echo ""; echo "[FAIL] $*"; exit 1; }

# Resolve output path
if [ -z "$OUTPUT_PATH" ]; then
    OUTPUT_PATH="$(cd "$SCRIPT_DIR/.." && pwd)/source_code"
    info "Output path not specified. Defaulting to: $OUTPUT_PATH"
fi

# ─── 1. Root / Admin Check ───────────────────────────────────────
step "Checking root/sudo privileges..."
if [ "$(id -u)" -ne 0 ]; then
    warn "This script requires root/sudo privileges for file operations."
    warn "Re-run with: sudo $0"
    echo ""
    echo "  === Calling Agent Action Required ==="
    echo "  Re-invoke this script with elevated privileges:"
    echo "    sudo $0"
    echo "  ======================================="
    exit 1
fi
ok "Running with root privileges."

# ─── 2. Validate Game Path ───────────────────────────────────────
step "Validating game path..."
MANAGED_PATH="$GAME_PATH/$MANAGED_RELATIVE_PATH"

if [ ! -d "$GAME_PATH" ]; then
    fail "Game installation directory not found: $GAME_PATH"
fi
if [ ! -d "$MANAGED_PATH" ]; then
    fail "Managed directory not found at: $MANAGED_PATH"
fi
ok "Game installation directory: $GAME_PATH"
ok "Managed directory: $MANAGED_PATH"

# ─── 3. Resolve Output Path ─────────────────────────────────────
step "Resolving output path..."
mkdir -p "$OUTPUT_PATH"
ok "Output path ready: $OUTPUT_PATH"

# ─── 4. Delete Existing DLLs ─────────────────────────────────────
step "Removing existing DLLs to trigger Steam validation..."
for dll in "${DLL_NAMES[@]}"; do
    dll_path="$MANAGED_PATH/$dll"
    if [ -f "$dll_path" ]; then
        rm -f "$dll_path"
        info "Deleted: $dll"
    else
        info "Already absent: $dll"
    fi
done

# ─── 5. Launch Steam File Integrity Validation ───────────────────
step "Launching Steam file integrity validation (AppID: $STEAM_APP_ID)..."
STEAM_URI="steam://validate/$STEAM_APP_ID"

if command -v "$STEAM_OPEN_CMD" &>/dev/null; then
    $STEAM_OPEN_CMD "$STEAM_URI" &
    info "Steam validation launched via $STEAM_OPEN_CMD"
else
    fail "Could not find $STEAM_OPEN_CMD. Open Steam manually and verify game files."
fi

info "Steam validation launched. Polling for DLL restoration..."

# ─── 6. Poll for DLL Restoration ─────────────────────────────────
elapsed=0
all_restored=false

while [ "$elapsed" -lt "$POLL_TIMEOUT_SEC" ]; do
    sleep "$POLL_INTERVAL_SEC"
    elapsed=$((elapsed + POLL_INTERVAL_SEC))

    all_exist=true
    for dll in "${DLL_NAMES[@]}"; do
        if [ ! -f "$MANAGED_PATH/$dll" ]; then
            all_exist=false
            break
        fi
    done

    if [ "$all_exist" = true ]; then
        all_restored=true
        ok "All DLLs restored after ~${elapsed}s."
        break
    fi

    info "Waiting for DLLs... (${elapsed}s / ${POLL_TIMEOUT_SEC}s)"
done

if [ "$all_restored" = false ]; then
    fail "Timed out after ${POLL_TIMEOUT_SEC}s. DLLs were not restored by Steam.
Possible causes:
  1. Steam is not running — open Steam manually
  2. Game not owned on this Steam account
  3. Validation takes longer than expected

Manual fix:
  Open Steam → Library → Blasphemous → Properties → Installed Files → Verify integrity of game files

After manual verification, re-run this script."
fi

# Verify DLLs are valid (non-zero size)
for dll in "${DLL_NAMES[@]}"; do
    dll_path="$MANAGED_PATH/$dll"
    size=$(stat -f%z "$dll_path" 2>/dev/null || stat -c%s "$dll_path" 2>/dev/null)
    if [ "$size" -eq 0 ]; then
        fail "DLL is empty after restoration: $dll. Re-run Steam validation."
    fi
    if command -v bc &>/dev/null; then
        size_display=$(echo "scale=2; $size / 1048576" | bc)
        size_unit="MB"
    else
        size_display="$size"
        size_unit="bytes"
    fi
    ok "Verified: $dll ($size_display $size_unit)"
done
ok "All DLLs restored and verified successfully."

# ─── 7. Check .NET SDK ───────────────────────────────────────────
step "Checking .NET SDK installation..."
if command -v dotnet &>/dev/null; then
    dotnet_version=$(dotnet --version)
    ok ".NET SDK detected: version $dotnet_version"
else
    fail ".NET SDK is not installed.
Please install .NET SDK from: https://dotnet.microsoft.com/download
After installation, re-run this script."
fi

# ─── 8. Check / Install ilspycmd ─────────────────────────────────
step "Ensuring ilspycmd is installed..."
if dotnet tool list --global 2>/dev/null | grep -q "ilspycmd"; then
    ok "ilspycmd is already installed."
else
    info "Installing ilspycmd globally..."
    install_log=$(dotnet tool install --global ilspycmd 2>&1) || {
        fail "Failed to install ilspycmd. Log: $install_log"
    }
    ok "ilspycmd installed successfully."
    # Add ~/.dotnet/tools to PATH for current session
    export PATH="$PATH:$HOME/.dotnet/tools"
fi

# ─── 9. Decompile Assembly-CSharp.dll ────────────────────────────
step "Decompiling Assembly-CSharp.dll..."
dll1="$MANAGED_PATH/Assembly-CSharp.dll"
out_dir1="$OUTPUT_PATH/Assembly-CSharp"
ilspycmd --nested-directories -p -o "$out_dir1" "$dll1" || {
    fail "ilspycmd failed for Assembly-CSharp.dll (exit code: $?)"
}
ok "Assembly-CSharp.dll → $out_dir1"

# ─── 10. Decompile Assembly-CSharp-firstpass.dll ─────────────────
step "Decompiling Assembly-CSharp-firstpass.dll..."
dll2="$MANAGED_PATH/Assembly-CSharp-firstpass.dll"
out_dir2="$OUTPUT_PATH/Assembly-CSharp-firstpass"
ilspycmd --nested-directories -p -o "$out_dir2" "$dll2" || {
    fail "ilspycmd failed for Assembly-CSharp-firstpass.dll (exit code: $?)"
}
ok "Assembly-CSharp-firstpass.dll → $out_dir2"

# ─── 11. Find .csproj Files ──────────────────────────────────────
step "Locating .csproj files from decompiled output..."
csproj_files=()

proj1=$(find "$out_dir1" -name "*.csproj" -type f 2>/dev/null | head -1)
proj2=$(find "$out_dir2" -name "*.csproj" -type f 2>/dev/null | head -1)

[ -n "$proj1" ] && csproj_files+=("$proj1") && info "Found: $(basename "$proj1")"
[ -n "$proj2" ] && csproj_files+=("$proj2") && info "Found: $(basename "$proj2")"

if [ "${#csproj_files[@]}" -eq 0 ]; then
    warn "No .csproj files found. Skipping solution creation."
else
    ok "Found ${#csproj_files[@]} project file(s)."

    # ─── 12. Create Solution and Add Projects ────────────────────
    step "Creating Visual Studio solution..."
    sln_path="$OUTPUT_PATH/$SOLUTION_NAME.sln"

    # Remove existing .sln if present (clean start)
    if [ -f "$sln_path" ]; then
        rm -f "$sln_path"
        info "Removed existing solution: $sln_path"
    fi

    # Create new solution
    dotnet new sln -n "$SOLUTION_NAME" -o "$OUTPUT_PATH" 2>&1 | head -5 || {
        fail "Failed to create .sln file."
    }

    # Add each project
    for csproj in "${csproj_files[@]}"; do
        add_log=$(dotnet sln "$sln_path" add "$csproj" 2>&1) && {
            rel_path="${csproj#$OUTPUT_PATH/}"
            ok "Added to solution: $rel_path"
        } || {
            warn "Failed to add project: $csproj. Log: $add_log"
        }
    done
    ok "Solution ready: $sln_path"
fi

# ─── Done ─────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  Decompilation Complete!"
echo "============================================"
echo "  Game:     $GAME_PATH"
echo "  Output:   $OUTPUT_PATH"
[ -f "$sln_path" ] && echo "  Solution: $sln_path"
echo "  Projects: ${#csproj_files[@]} decompiled"
echo ""
echo "Next step:"
echo "  Update preferences.md 'lightweight_source_code_path' to:"
echo "    $OUTPUT_PATH"
