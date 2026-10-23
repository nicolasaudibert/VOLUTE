#!/bin/bash
# Installs or updates VOLUTE on Linux (Ubuntu 22.04 and 24.04), in a folder of
# its own (~/VOLUTE by default) holding everything it needs: Miniforge, its
# Python environment, SAM2-Plus, the models and VOLUTE itself. Nothing outside
# that folder is changed, apart from the VOLUTE entry of the applications menu
# (~/.local/share/applications/volute.desktop). No administrator rights needed.
#
# Paste into a terminal:
#
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_linux.sh)"
#
# or, where curl is missing:
#
#   bash -c "$(wget -qO- https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_linux.sh)"
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
echo "VOLUTE installer (Linux)"
echo "======================================================================"
echo ""

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Error: this installer is for Linux."
    exit 1
fi

case "$(uname -m)" in
    x86_64)        ARCH="x86_64" ;;
    aarch64|arm64) ARCH="aarch64" ;;
    *)
        echo "Error: unsupported processor architecture: $(uname -m)"
        exit 1 ;;
esac

# A fresh Ubuntu may lack curl; wget is there by default
if command -v curl >/dev/null 2>&1; then
    fetch() { curl -fL --progress-bar -o "$1" "$2"; }
    fetch_quiet() { curl -fsSL -o "$1" "$2"; }
elif command -v wget >/dev/null 2>&1; then
    fetch() { wget -q --show-progress -O "$1" "$2"; }
    fetch_quiet() { wget -q -O "$1" "$2"; }
else
    echo "Error: neither curl nor wget is available to download files."
    echo "Install one of them, for example: sudo apt install curl"
    exit 1
fi

case "$PREFIX" in
    *" "*)
        echo "Error: the installation folder must not contain spaces: $PREFIX"
        echo "Choose another one with VOLUTE_PREFIX, for example:"
        echo "  VOLUTE_PREFIX=/opt/VOLUTE bash -c \"\$(curl -fsSL $RAW_BASE/install_volute_linux.sh)\""
        exit 1 ;;
esac
mkdir -p "$PREFIX"

if [[ ! -x "$MINIFORGE/bin/python" ]]; then
    echo "Installing Miniforge, the Python distribution VOLUTE runs on, into"
    echo "  $MINIFORGE"
    INSTALLER="$(mktemp -d)/Miniforge3.sh"
    fetch "$INSTALLER" \
        "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$ARCH.sh"
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
    fetch_quiet "$CORE" "$RAW_BASE/volute_installer.py"
fi

exec "$MINIFORGE/bin/python" "$CORE" --prefix "$PREFIX" --miniforge "$MINIFORGE" "$@"
