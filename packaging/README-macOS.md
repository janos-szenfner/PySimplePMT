# PySimplePMT on macOS

## Installing

1. Drag **PySimplePMT** onto the **Applications** shortcut in this window.
2. Eject the disk image.

## The first launch needs a right-click

**Do not double-click it the first time.** macOS will refuse, and the message
it shows offers no way past it.

Instead:

1. Open **Applications** in the Finder.
2. **Right-click** (or Control-click) **PySimplePMT**.
3. Choose **Open**.
4. A dialog says the developer cannot be verified. Click **Open**.

You only do this once. Every launch after it is an ordinary double-click, and
the app works from the Dock and from Spotlight like any other.

### On macOS Sequoia (15) and later

Right-click → Open may not appear on the first attempt. If so:

1. Double-click the app and dismiss the warning.
2. Open **System Settings → Privacy & Security**.
3. Scroll to the bottom, where it says PySimplePMT was blocked, and click
   **Open Anyway**.

## Why

The app is **unsigned**: it carries no Apple Developer certificate, because
this is a free, open-source project and a certificate is a paid annual
subscription. macOS treats any unsigned application this way regardless of
what is in it.

Nothing about the warning says the application is unsafe - only that Apple has
not been paid to vouch for it. The whole source is public, and this build is
produced by a GitHub Actions workflow you can read in the repository, from the
tag it is named after.

If you would rather not run unsigned software, run it from source instead:

```bash
git clone https://github.com/janos-szenfner/PySimplePMT.git
cd PySimplePMT
pip install -r requirements.txt
python3 run.py
```

## What is in the bundle

Everything. The Python interpreter, the Tcl/Tk runtime and every third-party
library are inside the .app, so **no Python installation and no pip packages
are required** and nothing is downloaded when you run it.

## Which Macs this build runs on

**Apple Silicon (arm64) only** - M1, M2, M3, M4 and later.

It is **not** built for Intel Macs. The bundle carries the interpreter and the
libraries of the machine that built it, and the release is built on an Apple
Silicon runner. On an Intel Mac, run from source as above.

To check which you have: **Apple menu → About This Mac**. "Chip" means Apple
Silicon; "Processor" means Intel.

## Uninstalling

Drag **PySimplePMT** from Applications to the Bin. It writes its settings and
its log under `~/.pysimplepmt`, which you can delete too.

## If it will not start

Open Terminal and run it directly - it will say what went wrong:

```bash
/Applications/PySimplePMT.app/Contents/MacOS/pysimplepmt --self-check
```

That checks every bundled dependency imports, and prints the version.
