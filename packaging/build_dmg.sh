#!/usr/bin/env bash
#
# Build a macOS .app bundle and a .dmg for PySimplePMT.
#
# Runs PyInstaller to produce a bundle carrying its own Python interpreter,
# every pip dependency and the Tcl/Tk runtime, wraps that in a .app, and puts
# the .app in a disk image beside a shortcut to /Applications.
#
# Usage:
#   packaging/build_dmg.sh [version]
#
# The version defaults to __version__ in gantt_app/__init__.py.
#
# Requires: macOS (for iconutil and hdiutil), python3, pip, and the packages
# in requirements.txt plus requirements-build.txt.
#
# The result is UNSIGNED. Building a signed, notarised app needs an Apple
# Developer certificate, which this project does not have; what the user has
# to do about that is in packaging/README-macOS.md, which is copied into the
# image so the instructions travel with it.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

PACKAGE_NAME="pysimplepmt"
APP_NAME="PySimplePMT"

# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "ERROR: this builds a macOS bundle and only runs on macOS" >&2
    exit 1
fi

for tool in iconutil hdiutil; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
        echo "ERROR: ${tool} is required and was not found" >&2
        exit 1
    fi
done

# ---------------------------------------------------------------------------
# Version and architecture
# ---------------------------------------------------------------------------

if [[ $# -ge 1 && -n "$1" ]]; then
    VERSION="$1"
else
    VERSION="$(python3 -c "import gantt_app; print(gantt_app.__version__)")"
fi
VERSION="${VERSION#v}"

# The build is not cross-compiled: PyInstaller bundles the interpreter and the
# libraries of the machine it runs on, so the architecture of the result is
# the architecture of the builder. Recorded in the name rather than assumed,
# so an Intel build cannot be mistaken for an Apple Silicon one.
ARCH="$(uname -m)"

echo "==> Building ${APP_NAME} ${VERSION} for ${ARCH}"

DIST_DIR="${PROJECT_ROOT}/dist"
BUILD_DIR="${PROJECT_ROOT}/build"
APP_BUNDLE="${DIST_DIR}/${APP_NAME}.app"
DMG_NAME="${PACKAGE_NAME}-${VERSION}-macos-${ARCH}"
DMG_PATH="${DIST_DIR}/${DMG_NAME}.dmg"

rm -rf "${DIST_DIR}/${PACKAGE_NAME}" "${APP_BUNDLE}" "${DMG_PATH}"

# ---------------------------------------------------------------------------
# The icon, then the bundle
# ---------------------------------------------------------------------------
#
# The .icns is written before PyInstaller runs, because the spec picks it up
# from build/ while assembling the bundle.

echo "==> Generating the icon"
mkdir -p "${BUILD_DIR}"
python3 packaging/make_icns.py "${BUILD_DIR}/${PACKAGE_NAME}.icns"

echo "==> Running PyInstaller"
python3 -m PyInstaller "packaging/${PACKAGE_NAME}.spec" --noconfirm --clean

if [[ ! -d "${APP_BUNDLE}" ]]; then
    echo "ERROR: PyInstaller did not produce ${APP_BUNDLE}" >&2
    exit 1
fi

# An unsigned bundle copied about by CI picks up a quarantine flag and a stale
# signature from the build machine. Stripping the extended attributes and
# applying an ad-hoc signature is what stops macOS reporting the app as
# "damaged" rather than merely unidentified - the first is a dead end for the
# user, the second is a right-click away.
echo "==> Clearing extended attributes and ad-hoc signing"
xattr -cr "${APP_BUNDLE}"
codesign --force --deep --sign - "${APP_BUNDLE}" 2>/dev/null \
    || echo "    ad-hoc signing failed; the app will still open via right-click → Open"

echo "==> Bundle contents"
du -sh "${APP_BUNDLE}"
"${APP_BUNDLE}/Contents/MacOS/${PACKAGE_NAME}" --version

# ---------------------------------------------------------------------------
# The disk image
# ---------------------------------------------------------------------------
#
# A staging folder rather than imaging dist/ directly, so the image holds
# exactly three things: the app, somewhere to drag it to, and the note
# explaining why the first launch needs a right-click.

echo "==> Staging the disk image"
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "${STAGE_DIR}"' EXIT

cp -R "${APP_BUNDLE}" "${STAGE_DIR}/"
ln -s /Applications "${STAGE_DIR}/Applications"
cp packaging/README-macOS.md "${STAGE_DIR}/README-macOS.md"

echo "==> Creating ${DMG_PATH}"
hdiutil create \
    -volname "${APP_NAME} ${VERSION}" \
    -srcfolder "${STAGE_DIR}" \
    -fs HFS+ \
    -format UDZO \
    -ov \
    "${DMG_PATH}"

# ---------------------------------------------------------------------------
# Prove the image is readable before anyone downloads it
# ---------------------------------------------------------------------------

echo "==> Verifying the image"
hdiutil verify "${DMG_PATH}"

MOUNT_POINT="$(mktemp -d)"
hdiutil attach "${DMG_PATH}" -mountpoint "${MOUNT_POINT}" -nobrowse -quiet
if [[ ! -x "${MOUNT_POINT}/${APP_NAME}.app/Contents/MacOS/${PACKAGE_NAME}" ]]; then
    hdiutil detach "${MOUNT_POINT}" -quiet || true
    echo "ERROR: the mounted image has no runnable application in it" >&2
    exit 1
fi
echo "    ${APP_NAME}.app is present and runnable"
hdiutil detach "${MOUNT_POINT}" -quiet
rmdir "${MOUNT_POINT}" 2>/dev/null || true

# ---------------------------------------------------------------------------
# The bundle on its own, for anyone who would rather not mount an image
# ---------------------------------------------------------------------------
#
# Zipped with ditto rather than zip: it is the only one of the two that keeps
# the resource forks, the symlinks inside the framework directories and the
# signature intact, and a bundle zipped with plain zip arrives broken.

ZIP_PATH="${DIST_DIR}/${PACKAGE_NAME}-${VERSION}-macos-${ARCH}-app.zip"
echo "==> Zipping the bundle to ${ZIP_PATH}"
rm -f "${ZIP_PATH}"
ditto -c -k --sequesterRsrc --keepParent "${APP_BUNDLE}" "${ZIP_PATH}"

echo
echo "==> Built:"
ls -lh "${DMG_PATH}" "${ZIP_PATH}"
echo "    and ${APP_BUNDLE}"
