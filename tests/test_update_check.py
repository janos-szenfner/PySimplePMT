"""
Unit tests for the update check (gantt_app/update_check.py, issue #41).

The network is injected, so these are pure: they check the version parsing,
the comparison, and that a failure comes back as "unknown" rather than
raising.
"""

import unittest

from gantt_app.update_check import (
    STATUS_LATEST,
    STATUS_UNKNOWN,
    STATUS_UPDATE,
    check_for_update,
    is_newer,
    parse_version,
)


def _fetch(tag, html_url="https://example/rel"):
    """A fake GitHub fetch returning one release tag."""
    def fetch(_url, _timeout):
        return {"tag_name": tag, "html_url": html_url}
    return fetch


class TestParseVersion(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_version("1.68.2"), (1, 68, 2))

    def test_leading_v(self):
        self.assertEqual(parse_version("v1.69.0"), (1, 69, 0))

    def test_prerelease_suffix_ignored(self):
        self.assertEqual(parse_version("v1.69.0-beta2"), (1, 69, 0))

    def test_nonsense_is_none(self):
        self.assertIsNone(parse_version("latest"))
        self.assertIsNone(parse_version(""))


class TestIsNewer(unittest.TestCase):
    def test_true_when_higher(self):
        self.assertTrue(is_newer("1.69.0", "1.68.2"))

    def test_false_when_equal(self):
        self.assertFalse(is_newer("1.68.2", "1.68.2"))

    def test_false_when_lower(self):
        self.assertFalse(is_newer("1.68.1", "1.68.2"))

    def test_false_when_unparseable(self):
        self.assertFalse(is_newer("latest", "1.68.2"))


class TestCheckForUpdate(unittest.TestCase):
    def test_a_newer_release_is_an_update(self):
        info = check_for_update("1.68.2", fetch=_fetch("v1.69.0"))
        self.assertEqual(info.status, STATUS_UPDATE)
        self.assertEqual(info.latest, "1.69.0")
        self.assertEqual(info.download_url, "https://example/rel")

    def test_the_same_release_is_the_latest(self):
        info = check_for_update("1.68.2", fetch=_fetch("v1.68.2"))
        self.assertEqual(info.status, STATUS_LATEST)

    def test_an_older_running_reads_as_latest(self):
        # Running ahead of the published release (a dev build) is not an
        # update prompt.
        info = check_for_update("1.70.0", fetch=_fetch("v1.68.2"))
        self.assertEqual(info.status, STATUS_LATEST)

    def test_a_network_error_is_unknown_not_a_crash(self):
        def boom(_url, _timeout):
            raise OSError("offline")
        info = check_for_update("1.68.2", fetch=boom)
        self.assertEqual(info.status, STATUS_UNKNOWN)
        self.assertIsNotNone(info.error)

    def test_a_release_with_no_version_is_unknown(self):
        info = check_for_update("1.68.2", fetch=_fetch("nightly"))
        self.assertEqual(info.status, STATUS_UNKNOWN)

    def test_it_falls_back_to_the_releases_page_without_a_url(self):
        def fetch(_url, _timeout):
            return {"tag_name": "v1.69.0"}
        info = check_for_update("1.68.2", fetch=fetch)
        self.assertIn("releases", info.download_url)


if __name__ == "__main__":
    unittest.main()
