"""
Assisted update: download the new installer, verify it, then open it (#41).

WHY THIS MODULE EXISTS:
======================
The About window's update check (gantt_app.utils.update_check) only reports that a
newer release exists. This module is the next step a planner can take from
there without leaving the app: it downloads the platform's installer from the
release, checks it against the release's published SHA256SUMS, and only then
hands it to the operating system to open. The download is never opened - and a
failed check is never opened - so a corrupted or tampered file cannot be run.

WHAT IT DELIBERATELY DOES NOT DO:
---------------------------------
It does not install anything itself, and it does not replace the running
application. It opens the verified installer (mounts the DMG on macOS, hands
the .deb to the software installer on Linux) and the person completes the
install the ordinary way. Silent self-replacement needs code signing and
notarization to be anything but a downgrade in trust, so it is left out.

The integrity check is the whole point: nothing downloaded here is opened
until its SHA-256 matches the digest the release published for that exact
file. Without a SHA256SUMS to check against, the download is refused rather
than opened unverified.
"""

import hashlib
import os
import subprocess
import sys
import tempfile
import urllib.request
from typing import Callable, Optional

from gantt_app.utils.update_check import default_ssl_context
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)

#: The release asset that lists each file's SHA-256, produced by the release
#: workflow (`sha256sum * > SHA256SUMS`).
CHECKSUMS_NAME = "SHA256SUMS"

#: How many bytes to read per chunk while downloading and hashing.
_CHUNK = 64 * 1024


class UpdateError(Exception):
    """A download that could not be completed or trusted."""


class IntegrityError(UpdateError):
    """A downloaded file whose checksum did not match the release's."""


def installer_suffixes(platform: str = sys.platform) -> tuple:
    """
    The installer file extensions for a platform, in order of preference.

    macOS takes the DMG, Linux the DEB, and Windows an MSI or, failing that,
    an EXE. Windows has no build yet, but the assisted update is ready for one
    the day a release carries it. An unknown platform gets an empty tuple, and
    the assisted download is simply not offered there.
    """
    if platform == "darwin":
        return (".dmg",)
    if platform.startswith("linux"):
        return (".deb",)
    if platform.startswith("win"):
        return (".msi", ".exe")
    return ()


def pick_installer(assets, platform: str = sys.platform) -> Optional[dict]:
    """The release asset that installs the app on this platform, or None."""
    for suffix in installer_suffixes(platform):
        for asset in assets:
            if asset.get("name", "").lower().endswith(suffix):
                return asset
    return None


def find_checksums(assets) -> Optional[dict]:
    """The SHA256SUMS asset, or None when the release published none."""
    for asset in assets:
        if asset.get("name") == CHECKSUMS_NAME:
            return asset
    return None


def parse_sha256sums(text: str, filename: str) -> Optional[str]:
    """
    The digest for one file from a SHA256SUMS listing, lower-cased.

    Each line is ``<hex>  <name>`` (the format `sha256sum` writes). The name
    is matched on its basename, so a listing that stored a path still
    resolves. None when the file is not listed.
    """
    target = os.path.basename(filename)
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        digest, name = parts[0], parts[-1]
        # sha256sum marks a binary read with a '*' before the name.
        if os.path.basename(name.lstrip("*")) == target:
            return digest.lower()
    return None


def sha256_of_file(path: str) -> str:
    """The SHA-256 of a file on disk, as lower-case hex."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_fetch_text(url: str, timeout: float) -> str:
    """Fetch a small text asset (the checksums)."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "PySimplePMT"})
    # The bundled certificate store - see update_check.default_ssl_context;
    # the download verifies TLS exactly as the check that found it did.
    with urllib.request.urlopen(request, timeout=timeout,
                                context=default_ssl_context()) as response:
        return response.read().decode("utf-8")


def _default_download(url: str, dest_path: str, timeout: float,
                      progress: Optional[Callable[[int, int], None]]) -> None:
    """
    Stream a URL to a file, reporting progress as (received, total) bytes.

    Hashing happens later, over the file on disk, so a download interrupted
    part way cannot pass the check: the partial file simply will not match.
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": "PySimplePMT"})
    with urllib.request.urlopen(request, timeout=timeout,
                                context=default_ssl_context()) as response:
        total = int(response.headers.get("Content-Length", 0) or 0)
        received = 0
        with open(dest_path, "wb") as handle:
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                handle.write(chunk)
                received += len(chunk)
                if progress is not None:
                    progress(received, total)


def download_and_verify(
    installer: dict,
    checksums_text: str,
    dest_dir: Optional[str] = None,
    timeout: float = 60.0,
    progress: Optional[Callable[[int, int], None]] = None,
    download: Optional[Callable] = None,
) -> str:
    """
    Download one installer asset and verify it against a SHA256SUMS listing.

    PARAMETERS:
    -----------
    installer : dict
        The asset to fetch: {name, url, size}.
    checksums_text : str
        The contents of the release's SHA256SUMS.
    dest_dir : str, optional
        Where to write the file; a fresh temp directory by default.
    progress : callable, optional
        Called with (received, total) bytes as the download proceeds.
    download : callable, optional
        The downloader, injected for tests.

    RETURNS:
    --------
    str
        The path to the verified file.

    RAISES:
    -------
    IntegrityError
        When the release lists no digest for the file, or the download's
        SHA-256 does not match it. The bad file is deleted first.
    UpdateError
        When the asset has no URL, or the download itself fails.
    """
    url = installer.get("url")
    name = installer.get("name") or "installer"
    if not url:
        raise UpdateError("The release asset has no download URL.")
    if not url.lower().startswith("https://"):
        # urlopen answers file: and ftp: as readily as https:; the asset URL
        # comes from an API response, which is no place to take one on trust.
        raise UpdateError(f"The release asset URL is not https: {url}")

    expected = parse_sha256sums(checksums_text, name)
    if not expected:
        raise IntegrityError(
            f"The release published no checksum for {name}, so it cannot be "
            f"verified.")

    dest_dir = dest_dir or tempfile.mkdtemp(prefix="pysimplepmt-update-")
    dest_path = os.path.join(dest_dir, os.path.basename(name))
    downloader = download or _default_download

    logger.info("Downloading update %s from %s", name, url)
    try:
        downloader(url, dest_path, timeout, progress)
    except Exception as error:
        _remove(dest_path)
        raise UpdateError(f"The download failed: {error}") from error

    actual = sha256_of_file(dest_path)
    if actual.lower() != expected.lower():
        _remove(dest_path)
        logger.warning("Update %s failed its checksum: got %s, expected %s",
                       name, actual, expected)
        raise IntegrityError(
            f"{name} did not match the checksum published for it and was not "
            f"opened.")

    logger.info("Update %s verified (sha256 %s)", name, actual)
    return dest_path


def open_installer(path: str) -> None:
    """
    Hand the verified installer to the operating system to open.

    macOS mounts the DMG; Linux opens the .deb in the software installer;
    Windows opens it with its default handler. The person completes the
    install from there - this never installs anything itself.
    """
    logger.info("Opening the verified installer %s", path)
    if sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    elif sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", path], check=False)
    elif sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        raise UpdateError(f"Do not know how to open an installer on "
                          f"{sys.platform}.")


def fetch_verified_installer(
    info,
    dest_dir: Optional[str] = None,
    timeout: float = 60.0,
    progress: Optional[Callable[[int, int], None]] = None,
    fetch_text: Optional[Callable[[str, float], str]] = None,
    download: Optional[Callable] = None,
    platform: str = sys.platform,
) -> str:
    """
    Find, download and verify the installer for an available update.

    Ties the pieces together for the About window: pick this platform's
    installer from the update's assets, fetch the release's SHA256SUMS,
    download the installer and verify it. Returns the verified file's path;
    raises UpdateError / IntegrityError otherwise (and never returns an
    unverified file).
    """
    installer = pick_installer(info.assets, platform)
    if installer is None:
        raise UpdateError("This release has no installer for your platform; "
                          "use the download page instead.")

    checksums = find_checksums(info.assets)
    if checksums is None or not checksums.get("url"):
        raise IntegrityError("This release published no SHA256SUMS to verify "
                             "the download against.")
    if not checksums["url"].lower().startswith("https://"):
        raise UpdateError("The checksums URL is not https: "
                          f"{checksums['url']}")

    fetch_text = fetch_text or _default_fetch_text
    try:
        checksums_text = fetch_text(checksums["url"], timeout)
    except Exception as error:
        raise UpdateError(f"Could not fetch the checksums: {error}") from error

    return download_and_verify(installer, checksums_text, dest_dir=dest_dir,
                               timeout=timeout, progress=progress,
                               download=download)


def can_assist(info, platform: str = sys.platform) -> bool:
    """Whether an assisted, verified download is possible for this update."""
    return (pick_installer(info.assets, platform) is not None
            and find_checksums(info.assets) is not None)


def _remove(path: str) -> None:
    """Delete a file, ignoring its absence."""
    try:
        os.remove(path)
    except OSError:
        pass
