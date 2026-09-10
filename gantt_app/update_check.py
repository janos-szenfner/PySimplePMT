"""
Check whether a newer PySimplePMT release is available (issue #41).

WHY THIS MODULE EXISTS:
======================
The About window asks GitHub whether the release it is running is the latest,
and says so - "you have the latest", or the newer version and a link to it.
The check is a small, self-contained, network-touching thing, kept out of the
window so the comparison can be tested without one and the window can run it
on a background thread without the logic living there.

WHAT IT DOES NOT DO:
--------------------
It never downloads or installs anything. It reads the latest release's
version and page URL and reports them; putting the new build in place is left
to the person, who follows the link. Auto-update is a separate, larger
concern (code signing, a trusted download, replacing a running app) and is
deliberately not attempted here.
"""

import json
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)

#: The repository releases are published to.
REPO = "janos-szenfner/PySimplePMT"

#: GitHub's "latest release" API, and the human page the link points at.
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"

#: What a check can conclude.
STATUS_LATEST = "latest"      # running the newest release
STATUS_UPDATE = "update"      # a newer release exists
STATUS_UNKNOWN = "unknown"    # could not tell (offline, no release, error)


@dataclass
class UpdateInfo:
    """The outcome of a check: which status, and the versions involved."""
    status: str
    current: str
    latest: Optional[str] = None
    download_url: Optional[str] = None
    error: Optional[str] = None


def parse_version(text: str) -> Optional[Tuple[int, ...]]:
    """
    A dotted version string as a tuple of integers, or None.

    Leading ``v`` is dropped and a trailing pre-release or build suffix is
    ignored, so ``v1.69.0-beta`` reads as (1, 69, 0). Anything without a
    numeric lead comes back None, which the caller treats as "cannot tell".
    """
    if not text:
        return None
    cleaned = text.strip().lstrip("vV")
    parts = []
    for chunk in cleaned.split("."):
        number = ""
        for char in chunk:
            if char.isdigit():
                number += char
            else:
                break
        if number == "":
            break
        parts.append(int(number))
    return tuple(parts) or None


def is_newer(latest: str, current: str) -> bool:
    """Whether ``latest`` is a strictly higher version than ``current``."""
    latest_tuple = parse_version(latest)
    current_tuple = parse_version(current)
    if not latest_tuple or not current_tuple:
        return False
    return latest_tuple > current_tuple


def _default_fetch(url: str, timeout: float) -> dict:
    """Fetch and decode the latest-release JSON from GitHub."""
    request = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json",
                      "User-Agent": f"PySimplePMT"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_for_update(current: str,
                     fetch: Callable[[str, float], dict] = _default_fetch,
                     timeout: float = 4.0) -> UpdateInfo:
    """
    Ask GitHub for the latest release and compare it to the running version.

    PARAMETERS:
    -----------
    current : str
        The running version, e.g. gantt_app.__version__.
    fetch : callable
        Fetches the release JSON; injected so the comparison can be tested
        without the network.
    timeout : float
        Seconds to wait for GitHub before giving up.

    RETURNS:
    --------
    UpdateInfo
        STATUS_UPDATE with the newer version and its page, STATUS_LATEST when
        nothing newer exists, or STATUS_UNKNOWN when the check could not be
        made - offline, rate-limited, or no release published. Never raises.
    """
    try:
        data = fetch(LATEST_RELEASE_API, timeout) or {}
    except Exception as error:  # network, JSON, HTTP - all non-fatal
        logger.info("Update check could not reach GitHub: %s", error)
        return UpdateInfo(STATUS_UNKNOWN, current, error=str(error))

    tag = data.get("tag_name") or ""
    latest = tag.lstrip("vV")
    download_url = data.get("html_url") or RELEASES_PAGE

    if parse_version(latest) is None:
        logger.info("Update check got no usable version from %r", tag)
        return UpdateInfo(STATUS_UNKNOWN, current,
                          error="no version in the latest release")

    if is_newer(latest, current):
        logger.info("Update available: %s (running %s)", latest, current)
        return UpdateInfo(STATUS_UPDATE, current, latest, download_url)

    logger.info("Running the latest version (%s)", current)
    return UpdateInfo(STATUS_LATEST, current, latest, download_url)
