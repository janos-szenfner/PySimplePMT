#!/usr/bin/env bash
#
# Build a self-contained Ubuntu/Debian package for PySimplePMT.
#
# Runs PyInstaller to produce a bundle that carries its own Python interpreter,
# every pip dependency and the Tcl/Tk runtime, then wraps that bundle in a .deb.
#
# Usage:
#   packaging/build_deb.sh [version]
#
# The version defaults to __version__ in gantt_app/__init__.py.
#
# Requires: python3, pip, dpkg-deb, and the packages in requirements.txt plus
# requirements-build.txt. On a bare Ubuntu runner you also need python3-tk,
# because PyInstaller bundles the Tcl/Tk runtime it finds on the build host.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

PACKAGE_NAME="pysimplepmt"
MAINTAINER="${DEB_MAINTAINER:-Janos Szenfner <janos@szenfner.com>}"

# ---------------------------------------------------------------------------
# Version and architecture
# ---------------------------------------------------------------------------

if [[ $# -ge 1 && -n "$1" ]]; then
    VERSION="$1"
else
    # The Python below deliberately contains no single quotes, so the whole
    # program survives being wrapped in them. Stripping the surrounding
    # quotes via chr(34)/chr(39) avoids nesting a quote inside a quote, which
    # is what previously produced invalid Python and aborted the build.
    VERSION="$(python3 -c 'import re, pathlib, sys
text = pathlib.Path("gantt_app/__init__.py").read_text()
match = re.search(r"__version__\s*=\s*(\S+)", text)
if not match:
    sys.stderr.write("ERROR: no __version__ in gantt_app/__init__.py\n")
    sys.exit(1)
print(match.group(1).strip().strip(chr(34) + chr(39)))')"
fi

if [[ -z "${VERSION}" ]]; then
    echo "ERROR: could not determine a version to build" >&2
    exit 1
fi

# Strip a leading 'v' so a git tag like v1.2.0 yields a valid Debian version
VERSION="${VERSION#v}"

ARCH="$(dpkg --print-architecture)"

echo "==> Building ${PACKAGE_NAME} ${VERSION} (${ARCH})"

BUILD_DIR="${PROJECT_ROOT}/build"
DIST_DIR="${PROJECT_ROOT}/dist"
STAGE_DIR="${BUILD_DIR}/deb/${PACKAGE_NAME}_${VERSION}_${ARCH}"

rm -rf "${STAGE_DIR}"

# ---------------------------------------------------------------------------
# Freeze the application
# ---------------------------------------------------------------------------

echo "==> Running PyInstaller"
python3 -m PyInstaller packaging/pysimplepmt.spec --noconfirm --clean \
    --distpath "${DIST_DIR}" --workpath "${BUILD_DIR}/pyinstaller"

BUNDLE_DIR="${DIST_DIR}/${PACKAGE_NAME}"
if [[ ! -x "${BUNDLE_DIR}/${PACKAGE_NAME}" ]]; then
    echo "ERROR: PyInstaller did not produce ${BUNDLE_DIR}/${PACKAGE_NAME}" >&2
    exit 1
fi

# A bundle can build cleanly and still be missing a pure-Python dependency
# that is only imported on a menu action. Prove every one of them imports
# from inside the frozen build before wrapping it in a package.
echo "==> Verifying bundled dependencies"
if ! "${BUNDLE_DIR}/${PACKAGE_NAME}" --self-check; then
    echo "ERROR: the frozen build is missing a required dependency" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Lay out the package tree
# ---------------------------------------------------------------------------

echo "==> Staging package tree"
install -d "${STAGE_DIR}/DEBIAN"
install -d "${STAGE_DIR}/opt/${PACKAGE_NAME}"
install -d "${STAGE_DIR}/usr/bin"
install -d "${STAGE_DIR}/usr/share/applications"
install -d "${STAGE_DIR}/usr/share/icons/hicolor/256x256/apps"
install -d "${STAGE_DIR}/usr/share/doc/${PACKAGE_NAME}"

cp -a "${BUNDLE_DIR}/." "${STAGE_DIR}/opt/${PACKAGE_NAME}/"

# Launcher on PATH. A wrapper rather than a symlink, so the binary still
# resolves its bundled libraries relative to its real location.
cat > "${STAGE_DIR}/usr/bin/${PACKAGE_NAME}" <<'LAUNCHER'
#!/bin/sh
# Launcher for PySimplePMT
exec /opt/pysimplepmt/pysimplepmt "$@"
LAUNCHER
chmod 0755 "${STAGE_DIR}/usr/bin/${PACKAGE_NAME}"

install -m 0644 packaging/${PACKAGE_NAME}.desktop \
    "${STAGE_DIR}/usr/share/applications/${PACKAGE_NAME}.desktop"

echo "==> Generating icon"
python3 packaging/make_icon.py \
    "${STAGE_DIR}/usr/share/icons/hicolor/256x256/apps/${PACKAGE_NAME}.png" 256

# ---------------------------------------------------------------------------
# Documentation and copyright
# ---------------------------------------------------------------------------

if [[ -f LICENSE ]]; then
    install -m 0644 LICENSE "${STAGE_DIR}/usr/share/doc/${PACKAGE_NAME}/copyright"
else
    cat > "${STAGE_DIR}/usr/share/doc/${PACKAGE_NAME}/copyright" <<COPYRIGHT
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: ${PACKAGE_NAME}

Files: *
Copyright: ${MAINTAINER}
License: See the project repository for licensing terms.
COPYRIGHT
    chmod 0644 "${STAGE_DIR}/usr/share/doc/${PACKAGE_NAME}/copyright"
fi

printf '%s (%s) unstable; urgency=low\n\n  * Released %s.\n\n -- %s  %s\n' \
    "${PACKAGE_NAME}" "${VERSION}" "${VERSION}" "${MAINTAINER}" \
    "$(date -R)" | gzip -9n > "${STAGE_DIR}/usr/share/doc/${PACKAGE_NAME}/changelog.Debian.gz"
chmod 0644 "${STAGE_DIR}/usr/share/doc/${PACKAGE_NAME}/changelog.Debian.gz"

# ---------------------------------------------------------------------------
# Control metadata
# ---------------------------------------------------------------------------

INSTALLED_SIZE="$(du -sk "${STAGE_DIR}" | cut -f1)"

# The bundle carries Python, Tcl/Tk and every pip dependency. What remains are
# base system libraries that Tk links against and that ship with any Ubuntu
# desktop; they are declared so apt reports a clear error on a minimal system
# rather than the app failing to start.
cat > "${STAGE_DIR}/DEBIAN/control" <<CONTROL
Package: ${PACKAGE_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: ${MAINTAINER}
Installed-Size: ${INSTALLED_SIZE}
Depends: libc6, libx11-6, libxext6, libxrender1, libfontconfig1, libfreetype6
Recommends: xdg-utils
Description: Gantt chart project management tool
 PySimplePMT is a desktop project management application with Gantt chart
 visualisation, drag-and-drop task management and sub-task hierarchies.
 .
 It imports plans from GanttProject (.gan), Mermaid (.mmd) and Excel (.xlsx)
 files, and exports to Mermaid, Excel, PNG and PDF.
 .
 This package is self-contained: the Python interpreter, the Tcl/Tk runtime
 and every third-party library are bundled, so no Python installation or pip
 package is required on the target system.
CONTROL

cat > "${STAGE_DIR}/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e

# Refresh the desktop and icon caches so the launcher appears immediately
if [ "$1" = "configure" ]; then
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -f -t /usr/share/icons/hicolor || true
    fi
fi

exit 0
POSTINST
chmod 0755 "${STAGE_DIR}/DEBIAN/postinst"

cat > "${STAGE_DIR}/DEBIAN/postrm" <<'POSTRM'
#!/bin/sh
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -f -t /usr/share/icons/hicolor || true
    fi
fi

exit 0
POSTRM
chmod 0755 "${STAGE_DIR}/DEBIAN/postrm"

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

echo "==> Building .deb"
# Directories 0755, files at least 0644, and root-owned as dpkg expects
find "${STAGE_DIR}" -type d -exec chmod 0755 {} +
find "${STAGE_DIR}/opt/${PACKAGE_NAME}" -type f -name '*.so*' -exec chmod 0755 {} +

OUTPUT="${DIST_DIR}/${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"
if command -v fakeroot >/dev/null 2>&1 && [ "$(id -u)" -ne 0 ]; then
    fakeroot dpkg-deb --build --root-owner-group "${STAGE_DIR}" "${OUTPUT}"
else
    dpkg-deb --build --root-owner-group "${STAGE_DIR}" "${OUTPUT}"
fi

echo "==> Built ${OUTPUT}"
dpkg-deb --info "${OUTPUT}" | sed 's/^/    /'
echo "==> Size: $(du -h "${OUTPUT}" | cut -f1)"
