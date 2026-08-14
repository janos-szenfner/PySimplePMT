# Packaging PySimplePMT

Builds a self-contained Ubuntu/Debian package. The goal is that an end user
installs one `.deb` and needs nothing else — no Python, no pip, no virtualenv.

## Contents

| File | Purpose |
|---|---|
| `pysimplepmt.spec` | PyInstaller specification; bundles the interpreter, dependencies and Tcl/Tk |
| `build_deb.sh` | Freezes the app and wraps the result in a `.deb` |
| `pysimplepmt.desktop` | Desktop entry so the app appears in the applications menu |
| `make_icon.py` | Draws the application icon (kept as code, not a committed binary) |

## Building locally

```bash
sudo apt-get install -y python3-tk fakeroot dpkg-dev
pip install -r requirements.txt -r requirements-build.txt
./packaging/build_deb.sh
```

The package lands in `dist/pysimplepmt_<version>_<arch>.deb`. The version
defaults to `__version__` in `gantt_app/__init__.py`; pass one explicitly to
override it:

```bash
./packaging/build_deb.sh 1.2.0
```

`python3-tk` is required **on the build host** because PyInstaller bundles the
Tcl/Tk runtime it finds there. It is not required on the target machine.

## Installing and removing

```bash
sudo apt install ./dist/pysimplepmt_1.0.0_amd64.deb
pysimplepmt
sudo apt remove pysimplepmt
```

## What is bundled, and what is not

**Bundled** (the user needs none of these installed):

- The CPython interpreter and standard library
- The Tcl/Tk runtime behind Tkinter
- customtkinter, plotly, tkinterweb, pillow, openpyxl and their transitive
  dependencies — every package pinned in `requirements.txt`

Plotly draws the interactive chart and tkinterweb embeds it in the window.
PNG, PDF and SVG export is drawn with Pillow in `utils/chart_render.py`.
matplotlib, numpy and Kaleido were all removed.

**Nothing is fetched at runtime.** Kaleido, Plotly's own image renderer,
works by driving a Chrome or Chromium browser and downloads one when none is
installed — hundreds of megabytes over the network, which defeats the point of
a self-contained package. Drawing the static export directly means no browser,
no rendering service and no download.

The one thing taken from the system is a font. `fonts-dejavu-core` is
recommended so accented characters render; without it the export falls back to
Pillow's built-in face, which covers little more than ASCII.

**Not bundled** — base system libraries that ship with any Ubuntu desktop and
that Tk links against. These are declared in the package's `Depends:` field so
`apt` reports a clear error on a minimal system rather than the app failing to
start:

```
libc6, libx11-6, libxext6, libxrender1, libfontconfig1, libfreetype6
```

**Deliberately excluded**: MS Project (`.mpp`) import, which needs the
optional `tasklib` reader. The feature degrades gracefully and reports what to
install.

A JPype + mpxj backend was removed outright: it is a Java bridge rather than a
Python solution, requiring a JVM and a separately downloaded `mpxj.jar` on the
user's machine. Neither can go inside a self-contained package, so it would
have put an external runtime back onto the end user.

## Verifying a build

The build refuses to package a bundle that is missing a dependency. After
PyInstaller runs, `build_deb.sh` executes:

```bash
dist/pysimplepmt/pysimplepmt --self-check
```

which imports every required and optional package from **inside** the frozen
build and exits non-zero if a required one is missing. This matters because
pure-Python packages such as `openpyxl` are compiled into the executable's
PYZ archive rather than appearing as directories under `_internal/` — the
bundle can look wrong to a casual `ls` while being perfectly correct, and can
equally look fine while missing something only imported on a menu action.

Run the same check against an installed package:

```bash
pysimplepmt --self-check
pysimplepmt --version
pysimplepmt --log-file
```

## CI and releases

| Workflow | Trigger | Does |
|---|---|---|
| `.github/workflows/ci.yml` | push, pull request | Runs the test suite on Python 3.9 / 3.11 / 3.12 and builds a throwaway `.deb` to prove packaging still works |
| `.github/workflows/release.yml` | tag matching `v*`, or manual dispatch | Runs tests, builds the `.deb`, installs it, smoke-tests it under Xvfb, and publishes a GitHub release |

To cut a release:

```bash
# Update __version__ in gantt_app/__init__.py first
git tag v1.1.0
git push origin v1.1.0
```

The release job attaches the `.deb`, a `SHA256SUMS` file, and
`dependency-manifest.txt` (the exact `pip freeze` of what went into the
bundle) so a build can be audited or reproduced later.

The smoke test launches the installed application against a virtual display
and requires that it stay running for 25 seconds; exiting early is treated as
a crash and fails the release. A package that installs but will not start is
worse than a failed build.

## Notes

- The launcher at `/usr/bin/pysimplepmt` is a shell wrapper rather than a
  symlink, so the executable still resolves its bundled libraries relative to
  its real location in `/opt/pysimplepmt`. The release workflow asserts that
  this wrapper never invokes a system Python.
- Only `amd64` is built by default; `build_deb.sh` uses
  `dpkg --print-architecture`, so running it on an arm64 host produces an
  arm64 package.
