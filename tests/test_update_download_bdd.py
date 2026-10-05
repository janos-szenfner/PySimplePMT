"""
pytest-bdd tests for the assisted update download and verify
(gantt_app/utils/update_download).

Run with:
    python3 -m pytest tests/test_update_download_bdd.py -q

The network is injected, so these are pure: they check platform
installer selection, SHA256SUMS parsing, and that a mismatched or
unverifiable download is refused (and its file removed) rather than
opened.
"""
import hashlib
import os
import sys
from types import SimpleNamespace
from unittest import mock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.utils.update_check import UpdateInfo, STATUS_UPDATE
from gantt_app.utils import update_download as ud

pytestmark = [
    pytest.mark.update_download,
]

scenarios("features/update_download.feature")


ASSETS = {
    "dmg": {"name": "pysimplepmt-1.69.0-macos-arm64.dmg",
            "url": "https://example/dmg", "size": 10},
    "deb": {"name": "pysimplepmt_1.69.0_amd64.deb",
            "url": "https://example/deb", "size": 10},
    "msi": {"name": "PySimplePMT-1.69.0-setup.msi",
            "url": "https://example/msi", "size": 10},
    "exe": {"name": "PySimplePMT-setup.exe", "url": "u", "size": 1},
    "sums": {"name": "SHA256SUMS", "url": "https://example/sums",
             "size": 1},
    "dmg_upper": {"name": "PYSIMPLEPMT-1.69.0-MACOS-ARM64.DMG",
                  "url": "https://example/dmg", "size": 10},
}

STANDARD_SUMS = (
    "aaa111  pysimplepmt_1.69.0_amd64.deb\n"
    "bbb222  pysimplepmt-1.69.0-macos-arm64.dmg\n"
    "ccc333  README-macOS.md\n"
)


def _assets(kinds):
    """'dmg,sums' -> the asset dicts those kinds stand for."""
    return [ASSETS[k.strip()] for k in kinds.split(",")]


def _serving(ctx):
    """A download that writes the scenario's payload to the temp path."""
    def download(url, dest_path, timeout, progress):
        with open(dest_path, "wb") as handle:
            handle.write(ctx.payload)
        if progress:
            progress(len(ctx.payload), len(ctx.payload))
    return download


def _update_info(assets):
    return UpdateInfo(STATUS_UPDATE, "1.68.2", "1.69.0",
                      "https://example/rel", assets=assets)


# ------------------------------------------------------------------
# GIVEN - the release, the listing, the wire
# ------------------------------------------------------------------

@pytest.fixture
def ctx():
    return SimpleNamespace(payload=b"the installer bytes",
                           sums_text=None, picked=None, digest=None,
                           path=None, error=None)


@given("a scratch folder")
def a_scratch_folder(ctx, tmp_path):
    ctx.dir = str(tmp_path)


@given(parsers.parse('the release offers "{kinds}"'))
def the_release_offers(ctx, kinds):
    ctx.assets = _assets(kinds)


@given(parsers.parse('an update offering "{kinds}"'))
def an_update_offering(ctx, kinds):
    ctx.info = _update_info(_assets(kinds))


@given(parsers.parse('an update offering "{kinds}" with checksums '
                     'fetched from "{url}"'))
def an_update_with_sums_url(ctx, kinds, url):
    assets = _assets(kinds)
    for asset in assets:
        if asset["name"] == "SHA256SUMS":
            asset["url"] = url
    if all(a["name"] != "SHA256SUMS" for a in assets):
        assets.append({"name": "SHA256SUMS", "url": url, "size": 1})
    ctx.info = _update_info(assets)


@given(parsers.parse('an update offering "{kinds}" with checksums '
                     'that have no URL'))
def an_update_with_urlless_sums(ctx, kinds):
    assets = _assets(kinds)
    assets.append({"name": "SHA256SUMS", "size": 1})
    ctx.info = _update_info(assets)


@given(parsers.parse('the checksums fetch fails with "{message}"'))
def the_checksums_fetch_fails(ctx, message):
    ctx.sums_error = OSError(message)


@given("the standard checksums listing")
def the_standard_checksums_listing(ctx):
    ctx.sums_text = STANDARD_SUMS


@given(parsers.parse('a checksums line "{digest}" for "{name}" '
                     'marked binary'))
def a_checksums_line_marked_binary(ctx, digest, name):
    ctx.sums_text = f"{digest} *{name}\n"


@given(parsers.parse('a checksums listing naming "{name}" with '
                     'digest "{digest}"'))
def a_checksums_listing(ctx, name, digest):
    ctx.sums_text = f"{digest}  {name}\n"


@given(parsers.parse('a checksums listing digesting the payload for '
                     'the "{kind}" asset'))
def a_checksums_digesting_the_payload(ctx, kind):
    digest = hashlib.sha256(ctx.payload).hexdigest()
    ctx.sums_text = f"{digest}  {ASSETS[kind]['name']}\n"


@given(parsers.parse('a checksums listing digesting the payload for '
                     'the "{kind}" asset in capitals'))
def a_checksums_digesting_the_payload_in_capitals(ctx, kind):
    digest = hashlib.sha256(ctx.payload).hexdigest().upper()
    ctx.sums_text = f"{digest}  {ASSETS[kind]['name']}\n"


@given(parsers.parse('a checksums listing naming the "{kind}" asset '
                     'with a wrong digest'))
def a_checksums_with_a_wrong_digest(ctx, kind):
    ctx.sums_text = f"{'0' * 64}  {ASSETS[kind]['name']}\n"


@given(parsers.parse('the checksums fetch digests the payload '
                     '"{payload}" for the "{kind}" asset'))
def the_checksums_fetch(ctx, payload, kind):
    digest = hashlib.sha256(payload.encode()).hexdigest()
    ctx.sums_text = f"{digest}  {ASSETS[kind]['name']}\n"


@given(parsers.parse('the download serves "{payload}"'))
def the_download_serves(ctx, payload):
    ctx.payload = payload.encode()
    ctx.download = _serving(ctx)


@given(parsers.parse('the download fails with "{message}"'))
def the_download_fails(ctx, message):
    def boom(url, dest_path, timeout, progress):
        raise OSError(message)
    ctx.download = boom


# ------------------------------------------------------------------
# WHEN - pick, look up, download
# ------------------------------------------------------------------

@when(parsers.parse('an installer is picked for "{platform}"'))
def an_installer_is_picked(ctx, platform):
    ctx.picked = ud.pick_installer(ctx.assets, platform)


@when(parsers.parse('the digest for "{filename}" is looked up'))
def the_digest_is_looked_up(ctx, filename):
    ctx.digest = ud.parse_sha256sums(ctx.sums_text, filename)


def _download_and_verify(ctx, asset, progress=None):
    if not hasattr(ctx, "download"):
        ctx.download = _serving(ctx)
    try:
        ctx.path = ud.download_and_verify(asset, ctx.sums_text,
                                          dest_dir=ctx.dir,
                                          progress=progress,
                                          download=ctx.download)
    except ud.UpdateError as error:
        ctx.error = error


@when(parsers.parse('the "{kind}" asset is downloaded and verified'))
def the_asset_is_downloaded(ctx, kind):
    _download_and_verify(ctx, ASSETS[kind])


@when(parsers.parse('the "{kind}" asset is downloaded and verified '
                    'with progress'))
def the_asset_is_downloaded_with_progress(ctx, kind):
    ctx.progress_calls = []
    _download_and_verify(ctx, ASSETS[kind],
                         progress=lambda r, t: ctx.progress_calls
                         .append((r, t)))


@when(parsers.parse('the "{kind}" asset at "{url}" is downloaded '
                    'and verified'))
def the_asset_at_url_is_downloaded(ctx, kind, url):
    _download_and_verify(ctx, {**ASSETS[kind], "url": url})


@when(parsers.parse('the "{kind}" asset with no URL is downloaded '
                    'and verified'))
def the_urlless_asset_is_downloaded(ctx, kind):
    _download_and_verify(ctx, {"name": ASSETS[kind]["name"], "size": 1})


@when(parsers.parse('the installer "{name}" is opened on "{platform}"'))
def the_installer_is_opened(ctx, name, platform):
    ctx.calls = {"run": [], "startfile": []}
    ctx.path = name

    def fake_run(argv, **kwargs):
        ctx.calls["run"].append(argv)

    def fake_startfile(path):
        ctx.calls["startfile"].append(path)

    with mock.patch.object(sys, "platform", platform), \
            mock.patch("subprocess.run", fake_run), \
            mock.patch.object(os, "startfile", fake_startfile,
                              create=True):
        try:
            ud.open_installer(name)
        except ud.UpdateError as error:
            ctx.error = error


@when(parsers.parse('a verified installer is fetched for "{platform}"'))
def a_verified_installer_is_fetched(ctx, platform):
    if not hasattr(ctx, "download"):
        ctx.download = _serving(ctx)

    def fetch_text(url, timeout):
        if getattr(ctx, "sums_error", None) is not None:
            raise ctx.sums_error
        return ctx.sums_text

    try:
        ctx.path = ud.fetch_verified_installer(
            ctx.info, dest_dir=ctx.dir, platform=platform,
            fetch_text=fetch_text, download=ctx.download)
    except ud.UpdateError as error:
        ctx.error = error


# ------------------------------------------------------------------
# THEN - what the release answered with
# ------------------------------------------------------------------

@then(parsers.parse('the picked asset is the "{kind}"'))
def the_picked_asset_is(ctx, kind):
    assert ctx.picked is ASSETS[kind]


@then("nothing is picked")
def nothing_is_picked(ctx):
    assert ctx.picked is None


@then(parsers.parse('the digest is "{digest}"'))
def the_digest_is(ctx, digest):
    assert ctx.digest == digest


@then("no digest is found")
def no_digest_is_found(ctx):
    assert ctx.digest is None


@then("the verified file is in the folder")
def the_verified_file_is_in_the_folder(ctx):
    assert os.path.isfile(ctx.path)


@then("the installer file is in the folder")
def the_installer_file_is_in_the_folder(ctx):
    assert os.path.isfile(ctx.path)


@then("the file's digest matches the payload's")
def the_files_digest_matches(ctx):
    assert ud.sha256_of_file(ctx.path) == \
        hashlib.sha256(ctx.payload).hexdigest()


@then("the folder is empty")
def the_folder_is_empty(ctx):
    assert os.listdir(ctx.dir) == []


@then("an integrity error is raised")
def an_integrity_error_is_raised(ctx):
    assert isinstance(ctx.error, ud.IntegrityError)


@then("an update error is raised")
def an_update_error_is_raised(ctx):
    assert isinstance(ctx.error, ud.UpdateError)


@then(parsers.parse('a release of "{kinds}" can assist "{platform}"'))
def a_release_can_assist(kinds, platform):
    assert ud.can_assist(_update_info(_assets(kinds)), platform)


@then(parsers.parse('a release of "{kinds}" cannot assist "{platform}"'))
def a_release_cannot_assist(kinds, platform):
    assert not ud.can_assist(_update_info(_assets(kinds)), platform)


@then("progress was reported with the payload's length as both counts")
def progress_was_reported(ctx):
    assert ctx.progress_calls
    assert ctx.progress_calls[-1] == (len(ctx.payload), len(ctx.payload))


@then(parsers.parse('the OS was asked to open it with "{command}"'))
def the_os_was_asked(ctx, command):
    assert ctx.calls["run"] == [[command, ctx.path]]


@then("Windows was asked to start it")
def windows_was_asked(ctx):
    assert ctx.calls["startfile"] == [ctx.path]
