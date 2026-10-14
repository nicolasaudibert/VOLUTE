#!/bin/bash
# Installs or updates VOLUTE on macOS, in a folder of its own (~/VOLUTE by
# default) holding everything it needs: Miniforge, its Python environment,
# SAM2-Plus, the models and VOLUTE itself. Nothing outside that folder is
# changed, apart from VOLUTE.app in ~/Applications.
#
# Paste into the Terminal:
#
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_macos.sh)"
#
# This script installs Miniforge into the folder, then hands over to
# volute_installer.py, run with Miniforge's own Python. Options given to this
# script are passed on to it (see python volute_installer.py --help).
#
# Environment variables:
#   VOLUTE_PREFIX            installation folder (default: ~/VOLUTE)
#   VOLUTE_INSTALLER_SOURCE  local volute_installer.py to run instead of the
#                            published one, for testing

set -e

PREFIX="${VOLUTE_PREFIX:-$HOME/VOLUTE}"
MINIFORGE="$PREFIX/miniforge3"
RAW_BASE="https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install"

echo "======================================================================"
echo "VOLUTE installer (macOS)"
echo "======================================================================"
echo ""

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Error: this installer is for macOS."
    exit 1
fi

# The hardware, not the architecture this shell happens to run under: a
# Terminal started through Rosetta reports x86_64 on Apple Silicon too
if [[ "$(sysctl -n hw.optional.arm64 2>/dev/null)" == "1" ]]; then
    ARCH="arm64"
else
    ARCH="x86_64"
fi

case "$PREFIX" in
    *" "*)
        echo "Error: the installation folder must not contain spaces: $PREFIX"
        echo "Choose another one with VOLUTE_PREFIX, for example:"
        echo "  VOLUTE_PREFIX=/Users/Shared/VOLUTE /bin/bash -c \"\$(curl -fsSL $RAW_BASE/install_volute_macos.sh)\""
        exit 1 ;;
esac
mkdir -p "$PREFIX"

if [[ ! -x "$MINIFORGE/bin/python" ]]; then
    echo "Installing Miniforge, the Python distribution VOLUTE runs on, into"
    echo "  $MINIFORGE"
    INSTALLER="$(mktemp -d)/Miniforge3.sh"
    curl -fL --progress-bar -o "$INSTALLER" \
        "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-$ARCH.sh"
    # -b: no question, and no change to shell startup files
    bash "$INSTALLER" -b -p "$MINIFORGE"
    rm -f "$INSTALLER"
    # The Miniforge installer lists its folder in ~/.conda/environments.txt,
    # whatever CONDA_REGISTER_ENVS says: that line is taken out again, and the
    # file and its folder too when nothing else is left in them
    ENV_LIST="$HOME/.conda/environments.txt"
    if [[ -f "$ENV_LIST" ]]; then
        grep -vxF "$MINIFORGE" "$ENV_LIST" > "$ENV_LIST.tmp" || true
        if [[ -s "$ENV_LIST.tmp" ]]; then
            mv "$ENV_LIST.tmp" "$ENV_LIST"
        else
            rm -f "$ENV_LIST.tmp" "$ENV_LIST"
        fi
        rmdir "$HOME/.conda" 2>/dev/null || true
    fi
    echo ""
else
    echo "Miniforge already installed in $MINIFORGE"
fi

if [[ -n "$VOLUTE_INSTALLER_SOURCE" ]]; then
    CORE="$VOLUTE_INSTALLER_SOURCE"
else
    CORE="$PREFIX/volute_installer.py"
    curl -fsSL -o "$CORE" "$RAW_BASE/volute_installer.py"
fi

exec "$MINIFORGE/bin/python" "$CORE" --prefix "$PREFIX" --miniforge "$MINIFORGE" "$@"
