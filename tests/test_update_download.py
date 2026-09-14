"""
Tests for the assisted update download and verify (gantt_app/utils/update_download).

The network is injected, so these are pure: they check platform installer
selection, SHA256SUMS parsing, and that a mismatched or unverifiable download
is refused (and its file removed) rather than opened.
"""

import hashlib
import os
import tempfile
import unittest

from gantt_app.utils.update_check import UpdateInfo, STATUS_UPDATE
from gantt_app.utils import update_download as ud


DMG = {"name": "pysimplepmt-1.69.0-macos-arm64.dmg",
       "url": "https://example/dmg", "size": 10}
DEB = {"name": "pysimplepmt_1.69.0_amd64.deb",
       "url": "https://example/deb", "size": 10}
MSI = {"name": "PySimplePMT-1.69.0-setup.msi",
       "url": "https://example/msi", "size": 10}
SUMS = {"name": "SHA256SUMS", "url": "https://example/sums", "size": 1}


class TestInstallerSelection(unittest.TestCase):
    def test_macos_takes_the_dmg(self):
        self.assertEqual(ud.pick_installer([DEB, DMG, SUMS], "darwin"), DMG)

    def test_linux_takes_the_deb(self):
        self.assertEqual(ud.pick_installer([DEB, DMG, SUMS], "linux"), DEB)

    def test_windows_takes_the_msi(self):
        self.assertEqual(ud.pick_installer([DMG, MSI], "win32"), MSI)

    def test_windows_falls_back_to_exe(self):
        exe = {"name": "PySimplePMT-setup.exe", "url": "u", "size": 1}
        self.assertEqual(ud.pick_installer([DMG, exe], "win32"), exe)

    def test_unknown_platform_gets_nothing(self):
        self.assertIsNone(ud.pick_installer([DMG, DEB], "sunos"))

    def test_no_matching_asset_is_none(self):
        self.assertIsNone(ud.pick_installer([DEB, SUMS], "darwin"))


class TestChecksumParsing(unittest.TestCase):
    SUMS_TEXT = (
        "aaa111  pysimplepmt_1.69.0_amd64.deb\n"
        "bbb222  pysimplepmt-1.69.0-macos-arm64.dmg\n"
        "ccc333  README-macOS.md\n"
    )

    def test_it_finds_the_named_file(self):
        self.assertEqual(
            ud.parse_sha256sums(self.SUMS_TEXT,
                                "pysimplepmt-1.69.0-macos-arm64.dmg"),
            "bbb222")

    def test_it_matches_on_basename(self):
        self.assertEqual(
            ud.parse_sha256sums(self.SUMS_TEXT,
                                "/tmp/pysimplepmt_1.69.0_amd64.deb"),
            "aaa111")

    def test_a_binary_star_marker_is_ignored(self):
        text = "deadbeef *pysimplepmt-1.69.0-macos-arm64.dmg\n"
        self.assertEqual(
            ud.parse_sha256sums(text, "pysimplepmt-1.69.0-macos-arm64.dmg"),
            "deadbeef")

    def test_an_unlisted_file_is_none(self):
        self.assertIsNone(ud.parse_sha256sums(self.SUMS_TEXT, "other.dmg"))


class TestDownloadAndVerify(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pspmt-test-")
        self.payload = b"the installer bytes"
        self.digest = hashlib.sha256(self.payload).hexdigest()

    def _download(self, url, dest_path, timeout, progress):
        with open(dest_path, "wb") as handle:
            handle.write(self.payload)
        if progress:
            progress(len(self.payload), len(self.payload))

    def test_a_matching_checksum_returns_the_path(self):
        sums = f"{self.digest}  {DMG['name']}\n"
        path = ud.download_and_verify(DMG, sums, dest_dir=self.dir,
                                      download=self._download)
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(ud.sha256_of_file(path), self.digest)

    def test_a_mismatch_is_refused_and_the_file_removed(self):
        sums = f"{'0' * 64}  {DMG['name']}\n"
        with self.assertRaises(ud.IntegrityError):
            ud.download_and_verify(DMG, sums, dest_dir=self.dir,
                                   download=self._download)
        # The bad file must not be left behind to be opened by hand.
        self.assertEqual(os.listdir(self.dir), [])

    def test_no_checksum_for_the_file_is_refused(self):
        with self.assertRaises(ud.IntegrityError):
            ud.download_and_verify(DMG, "aaa  something-else.dmg\n",
                                   dest_dir=self.dir, download=self._download)

    def test_a_download_error_becomes_an_update_error(self):
        def boom(url, dest_path, timeout, progress):
            raise OSError("connection reset")
        sums = f"{self.digest}  {DMG['name']}\n"
        with self.assertRaises(ud.UpdateError):
            ud.download_and_verify(DMG, sums, dest_dir=self.dir, download=boom)

    def test_a_non_https_asset_url_is_refused(self):
        # The URL comes from an API response; urlopen would answer file:
        # or ftp: just as readily, so anything but https: is refused.
        bad = {"name": DMG["name"], "url": "file:///etc/passwd", "size": 1}
        with self.assertRaises(ud.UpdateError):
            ud.download_and_verify(bad, f"{self.digest}  {DMG['name']}\n",
                                   dest_dir=self.dir,
                                   download=self._download)
        self.assertEqual(os.listdir(self.dir), [])


class TestFetchVerifiedInstaller(unittest.TestCase):
    def _info(self, assets):
        return UpdateInfo(STATUS_UPDATE, "1.68.2", "1.69.0",
                          "https://example/rel", assets=assets)

    def test_it_downloads_and_verifies_end_to_end(self):
        payload = b"dmg-bytes"
        digest = hashlib.sha256(payload).hexdigest()
        dir_ = tempfile.mkdtemp(prefix="pspmt-test-")

        def fetch_text(url, timeout):
            return f"{digest}  {DMG['name']}\n"

        def download(url, dest_path, timeout, progress):
            with open(dest_path, "wb") as handle:
                handle.write(payload)

        path = ud.fetch_verified_installer(
            self._info([DMG, SUMS]), dest_dir=dir_, platform="darwin",
            fetch_text=fetch_text, download=download)
        self.assertTrue(os.path.isfile(path))

    def test_no_installer_for_the_platform_is_refused(self):
        with self.assertRaises(ud.UpdateError):
            ud.fetch_verified_installer(self._info([SUMS]), platform="darwin")

    def test_no_checksums_asset_is_refused(self):
        with self.assertRaises(ud.IntegrityError):
            ud.fetch_verified_installer(self._info([DMG]), platform="darwin")

    def test_a_non_https_checksums_url_is_refused(self):
        bad_sums = {"name": "SHA256SUMS", "url": "ftp://example/sums",
                    "size": 1}
        with self.assertRaises(ud.UpdateError):
            ud.fetch_verified_installer(
                self._info([DMG, bad_sums]), platform="darwin")

    def test_can_assist_reports_readiness(self):
        self.assertTrue(ud.can_assist(self._info([DMG, SUMS]), "darwin"))
        self.assertFalse(ud.can_assist(self._info([DMG]), "darwin"))
        self.assertTrue(ud.can_assist(self._info([MSI, SUMS]), "win32"))


if __name__ == "__main__":
    unittest.main()
