#!/bin/bash
# Creates a macOS .app wrapper around the VOLUTE launcher (macOS only, optional).
#
# What the bundle buys, beyond a Dock icon and a name:
#   - access to the folder holding the installation when it sits under ~/Documents,
#     ~/Desktop or ~/Downloads (see the compiled launcher below);
#   - the application's own model chooser at every launch, unless the bundle was
#     built with --args, which passes the model on the command line and skips it;
#   - a chance for the system-drawn file dialog to be localized — the interpreter
#     is started through a symlink inside the bundle so the process belongs to an
#     application, and that application's AppleLanguages preference is aligned with
#     the configured UI language. Should the panel stay in English regardless, set
#     ui.native_file_dialogs to false in volute_config.yaml to use Qt's own.
#
# The wrapper only starts tools/VOLUTE.py from this installation with the Python
# interpreter found at generation time — no code is copied, so the .app keeps
# working as the sources change. Re-run this script after moving the installation
# or switching Python environment.

set -e

NAME="VOLUTE"
ARGS=""
OUTPUT_DIR="."
PYTHON_BIN="$(command -v python || command -v python3)"

usage() {
    cat << 'USAGE'
Usage: tools/install_app_bundle_macos.sh [options]

  --name NAME     Application name (default: "VOLUTE")
  --args "ARGS"   Arguments passed to VOLUTE.py, e.g. "--model sam2plus --task point"
  --output DIR    Where to create the bundle (default: current directory)
  --python PATH   Python interpreter to use (default: the one on PATH)
  --help          Show this message

Run from the root of your SAM2 installation. Examples:

  tools/install_app_bundle_macos.sh
  tools/install_app_bundle_macos.sh --name "SAM2++ Point Tracking" --args "--model sam2plus --task point"
USAGE
}

while [ $# -gt 0 ]; do
    case "$1" in
        --name)   NAME="$2"; shift 2 ;;
        --args)   ARGS="$2"; shift 2 ;;
        --output) OUTPUT_DIR="$2"; shift 2 ;;
        --python) PYTHON_BIN="$2"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "Error: this script builds a macOS application bundle and only runs on macOS."
    exit 1
fi

if [ ! -d "tools" ] || [ ! -d "sam2" ]; then
    echo "Error: This script must be run from the root of your SAM2 installation"
    exit 1
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "Error: no Python interpreter found. Activate your environment, or pass --python PATH."
    exit 1
fi

# The bundle runs this exact interpreter, with no environment activated: an
# interpreter that cannot import SAM2 and PyQt5 here will not manage it from
# the Dock either, and the failure would only surface at launch. Catch it now,
# while the person is at the keyboard and knows which environment they meant.
MISSING=""
for module in sam2 torch PyQt5; do
    "$PYTHON_BIN" -c "import $module" >/dev/null 2>&1 || MISSING="$MISSING $module"
done
if [ -n "$MISSING" ]; then
    echo "Error: $PYTHON_BIN cannot import:$MISSING"
    echo ""
    echo "The bundle would start and fail. Activate the environment VOLUTE runs"
    echo "in and run this script again, or name its interpreter directly:"
    echo ""
    echo "  conda activate <your-env> && bash tools/install_app_bundle_macos.sh"
    echo "  bash tools/install_app_bundle_macos.sh --python /path/to/env/bin/python"
    exit 1
fi

SAM2_ROOT="$(pwd)"
BUNDLE="${OUTPUT_DIR%/}/${NAME}.app"
APP_VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' tools/volute/__init__.py 2>/dev/null | head -1)"
APP_VERSION="${APP_VERSION:-0.0}"

echo "======================================================================"
echo "VOLUTE macOS application bundle"
echo "======================================================================"
echo "Installation : $SAM2_ROOT"
echo "Interpreter  : $PYTHON_BIN"
echo "Bundle       : $BUNDLE"
[ -n "$ARGS" ] && echo "Arguments    : $ARGS"
echo ""

rm -rf "$BUNDLE"
mkdir -p "$BUNDLE/Contents/MacOS"

# Languages the bundle advertises: English plus every translation shipped with the
# GUI. macOS localizes what it draws for the application — the file dialog above
# all — only among the languages declared here.
LANGUAGES="en"
for tsv in tools/volute/translations/*.tsv; do
    code="$(basename "$tsv" .tsv)"
    case "$code" in
        template|en) continue ;;
    esac
    LANGUAGES="$LANGUAGES $code"
done

LOCALIZATIONS_XML=""
for code in $LANGUAGES; do
    mkdir -p "$BUNDLE/Contents/Resources/${code}.lproj"
    LOCALIZATIONS_XML="${LOCALIZATIONS_XML}        <string>${code}</string>
"
done

# Bundle identifier: lowercase name, spaces and other characters folded to dashes
BUNDLE_ID="org.volute.$(echo "$NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]\{1,\}/-/g; s/^-//; s/-$//')"

cat > "$BUNDLE/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>${NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>${NAME}</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIdentifier</key>
    <string>${BUNDLE_ID}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleVersion</key>
    <string>${APP_VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${APP_VERSION}</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleIconFile</key>
    <string>icon.icns</string>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <!-- The point of the bundle: declaring these makes macOS localize the
         system-drawn UI, the native file dialog in particular. -->
    <key>CFBundleLocalizations</key>
    <array>
${LOCALIZATIONS_XML}    </array>
    <!-- An application launched from the Finder needs the person's consent to read
         protected folders. Without these, an installation under ~/Documents,
         ~/Desktop or ~/Downloads fails at startup with "Operation not permitted"
         and no visible prompt. -->
    <key>NSDocumentsFolderUsageDescription</key>
    <string>${NAME} needs access to read the application files and your image folders.</string>
    <key>NSDesktopFolderUsageDescription</key>
    <string>${NAME} needs access to read the application files and your image folders.</string>
    <key>NSDownloadsFolderUsageDescription</key>
    <string>${NAME} needs access to read the application files and your image folders.</string>
    <key>NSRemovableVolumesUsageDescription</key>
    <string>${NAME} needs access to read image folders stored on external volumes.</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# Localized bundle names — the .lproj directories are what macOS actually looks
# for when deciding which languages an application supports
for code in $LANGUAGES; do
    printf 'CFBundleName = "%s";\nCFBundleDisplayName = "%s";\n' "$NAME" "$NAME" \
        > "$BUNDLE/Contents/Resources/${code}.lproj/InfoPlist.strings"
done

# The interpreter is reached through a symlink inside the bundle, and that is what
# localizes the native file dialog: macOS derives an application's identity — and
# the language of the panels it draws — from the *executable's* location. Started
# through its own path, the interpreter belongs to no bundle and everything the
# system draws stays in English, whatever this bundle declares.
#
# The symlink carries the application's name because the interpreter, not the
# compiled launcher, is the process that owns the Dock tile: named "python", the
# Dock would label the application after the interpreter version.
ln -sf "$PYTHON_BIN" "$BUNDLE/Contents/MacOS/$NAME"

# Dock icon: the bundle's own .icns wins over the icon Qt sets, so it is copied in
if [ -f "tools/volute/resources/icon.icns" ]; then
    cp "tools/volute/resources/icon.icns" "$BUNDLE/Contents/Resources/icon.icns"
fi

LOG_FILE="\$HOME/Library/Logs/${NAME}.log"
cat > "$BUNDLE/Contents/Resources/run.sh" << LAUNCHER
#!/bin/bash
# Generated by tools/install_app_bundle_macos.sh — re-run it after moving this
# installation or changing Python environment.
# \$1 is the bundle's Contents directory, passed by the compiled launcher.
CONTENTS="\$1"
PYTHON="\$CONTENTS/MacOS/${NAME}"
MODEL_ARGS="${ARGS}"

mkdir -p "\$HOME/Library/Logs"
cd "${SAM2_ROOT}" 2>> "${LOG_FILE}"

LANG_CODE="\$(sed -n 's/^[[:space:]]*default_language:[[:space:]]*"\{0,1\}\([a-z][a-z]\).*/\1/p' \\
              tools/volute_config.yaml 2>/dev/null | head -1)"

# The native file dialog is drawn by a separate system process, which reads the
# language from this application's own preferences — not from anything the GUI
# process sets for itself. Aligning that preference with the configured language
# is what puts the panel in French; it stays on the language configured here,
# whatever the Language menu does afterwards. Remove it with:
#   defaults delete ${BUNDLE_ID} AppleLanguages
if [ -n "\$LANG_CODE" ]; then
    defaults write "${BUNDLE_ID}" AppleLanguages -array "\$LANG_CODE" 2>> "${LOG_FILE}"
fi

"\$PYTHON" tools/VOLUTE.py \$MODEL_ARGS >> "${LOG_FILE}" 2>&1
status=\$?

# A double-clicked application has nowhere to print: report a startup failure
# rather than dying silently. "Operation not permitted" means macOS denied
# access to the folder holding the installation.
if [ \$status -ne 0 ]; then
    detail="\$(tail -n 3 "${LOG_FILE}" 2>/dev/null | tr '"' "'" | tr '\n' ' ')"
    osascript -e "display alert \"${NAME}\" message \"The application could not start (exit code \$status).

\$detail

Full log: ~/Library/Logs/${NAME}.log\" as critical" >/dev/null 2>&1
fi
exit \$status
LAUNCHER

chmod +x "$BUNDLE/Contents/Resources/run.sh"

# The bundle executable has to be a compiled binary, not the shell script above:
# macOS attributes file access to the running executable, so a script bundle is
# judged as /bin/bash — a system binary with no claim on the person's folders,
# which is denied without ever showing a prompt. A binary signed as part of the
# bundle carries the bundle's own identity, and the processes it starts inherit it.
LAUNCHER_SRC="$(mktemp -t volute_launcher).c"
cat > "$LAUNCHER_SRC" << 'LAUNCHER_C'
/* Bundle executable: locates Contents/Resources/run.sh next to itself and runs
   it. Resolving its own path keeps the bundle movable (Dock, /Applications). */
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(void) {
    char exec_path[PATH_MAX], resolved[PATH_MAX], script[PATH_MAX];
    uint32_t size = sizeof(exec_path);

    if (_NSGetExecutablePath(exec_path, &size) != 0) return 127;
    if (realpath(exec_path, resolved) == NULL) return 127;

    /* <bundle>/Contents/MacOS/launcher -> <bundle>/Contents */
    char macos_dir[PATH_MAX];
    snprintf(macos_dir, sizeof(macos_dir), "%s", dirname(resolved));
    char contents_dir[PATH_MAX];
    snprintf(contents_dir, sizeof(contents_dir), "%s", dirname(macos_dir));
    snprintf(script, sizeof(script), "%s/Resources/run.sh", contents_dir);

    execl("/bin/bash", "bash", script, contents_dir, (char *)NULL);
    return 127;
}
LAUNCHER_C

if command -v cc >/dev/null 2>&1 && cc -O2 -o "$BUNDLE/Contents/MacOS/launcher" "$LAUNCHER_SRC" 2>/dev/null; then
    echo "  ✓ Compiled launcher"
else
    echo "  ! No C compiler (install the Xcode Command Line Tools: xcode-select --install)."
    echo "    Falling back to a script launcher: the application will start only if the"
    echo "    installation sits outside ~/Documents, ~/Desktop and ~/Downloads."
    cp "$BUNDLE/Contents/Resources/run.sh" "$BUNDLE/Contents/MacOS/launcher"
    chmod +x "$BUNDLE/Contents/MacOS/launcher"
fi
rm -f "$LAUNCHER_SRC"

# Ad-hoc signature: macOS ties folder-access permissions to an application's code
# signature. Unsigned, the bundle gets a new identity at every launch and any
# permission granted to it is forgotten.
if command -v codesign >/dev/null 2>&1; then
    codesign --force --deep --sign - "$BUNDLE" >/dev/null 2>&1 \
        && echo "  ✓ Signed (ad-hoc)" \
        || echo "  ! Could not sign the bundle — macOS may refuse it access to protected folders"
fi

# Refresh Launch Services so the Finder picks the bundle up immediately
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[ -x "$LSREGISTER" ] && "$LSREGISTER" -f "$BUNDLE" 2>/dev/null || true

echo "  ✓ Created: $BUNDLE"
echo ""
echo "Double-click it, or drag it to the Dock or /Applications."
echo "Console output goes to ~/Library/Logs/${NAME}.log"
echo ""
echo "First launch: macOS asks for access to the folder holding this installation"
echo "(\"${SAM2_ROOT}\"). Accept, otherwise the application cannot read its own files."
echo "If no prompt appears and nothing starts, add the bundle to System Settings ›"
echo "Privacy & Security › Full Disk Access, or install outside ~/Documents,"
echo "~/Desktop and ~/Downloads — folders outside those are not protected."
echo ""
echo "The native file dialog follows the *system* language, not the language"
echo "selected in the GUI. Check System Settings › General › Language & Region."
