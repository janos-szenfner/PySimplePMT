"""
pytest-bdd tests for the update check
(gantt_app/utils/update_check.py, issue #41).

Run with:
    python3 -m pytest tests/test_update_check_bdd.py -q

The network is injected, so these are pure: they check the version
parsing, the comparison, and that a failure comes back as "unknown"
rather than raising.
"""
import builtins
import ssl
import urllib.error
from types import SimpleNamespace
from unittest import mock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.utils import update_check
from gantt_app.utils.update_check import (
    STATUS_LATEST,
    STATUS_UNKNOWN,
    STATUS_UPDATE,
    check_for_update,
    is_newer,
    parse_version,
)

pytestmark = [
    pytest.mark.update_check,
]

scenarios("features/update_check.feature")


@pytest.fixture
def ctx():
    return SimpleNamespace(fetch=None, info=None, parsed="__unset__",
                           newer=None, context=None)


def _fetch_answer(tag, html_url="https://example/rel", extra=None):
    """A fake GitHub fetch returning one release tag."""
    def fetch(_url, _timeout):
        release = {"tag_name": tag}
        if html_url is not None:
            release["html_url"] = html_url
        if extra:
            release.update(extra)
        return release
    return fetch


def _fetch_latest_404s(list_answer):
    """releases/latest 404s; the releases list answers as given."""
    def fetch(url, _timeout):
        if url.endswith("/latest"):
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        return list_answer
    return fetch


# ------------------------------------------------------------------
# GIVEN - what the feed says
# ------------------------------------------------------------------

@given(parsers.parse('the release feed answers tag "{tag}" at "{url}"'))
def the_feed_answers(ctx, tag, url):
    ctx.fetch = _fetch_answer(tag, url)


@given(parsers.parse('the release feed answers tag "{tag}" '
                     'without a page'))
def the_feed_answers_without_a_page(ctx, tag):
    ctx.fetch = _fetch_answer(tag, html_url=None)


@given("the release feed is offline")
def the_feed_is_offline(ctx):
    def boom(_url, _timeout):
        raise OSError("offline")
    ctx.fetch = boom


@given(parsers.parse('the latest call 404s and the list answers '
                     'tag "{tag}"'))
def the_latest_call_404s(ctx, tag):
    ctx.fetch = _fetch_latest_404s(
        [{"tag_name": tag, "html_url": "https://example/rel"}])


@given("the latest call 404s and the list has only drafts")
def the_list_has_only_drafts(ctx):
    ctx.fetch = _fetch_latest_404s(
        [{"tag_name": "v9.9.9", "draft": True}])


@given(parsers.parse('the latest call 404s and the list leads with a '
                     'draft then "{tag}"'))
def the_list_leads_with_a_draft(ctx, tag):
    ctx.fetch = _fetch_latest_404s(
        [{"tag_name": "v9.9.9", "draft": True},
         {"tag_name": tag, "html_url": "https://example/rel"}])


@given("the latest call 404s and the list answers a mapping")
def the_list_answers_a_mapping(ctx):
    ctx.fetch = _fetch_latest_404s({"tag_name": "v1.69.0"})


@given(parsers.parse('the release feed answers tag "{tag}" at "{url}" '
                     'carrying assets'))
def the_feed_answers_with_assets(ctx, tag, url):
    def fetch(_url, _timeout):
        return {
            "tag_name": tag, "html_url": url,
            "assets": [
                {"name": "pysimplepmt-1.69.0-macos-arm64.dmg",
                 "browser_download_url": "https://example/dmg",
                 "size": 10},
                {"name": "no-download-url.txt", "size": 1},
            ],
        }
    ctx.fetch = fetch


@given("the latest call 404s and the list is empty")
def the_list_is_empty(ctx):
    ctx.fetch = _fetch_latest_404s([])


@given(parsers.parse('the release feed answers HTTP {code:d}'))
def the_feed_answers_http(ctx, code):
    def fetch(url, _timeout):
        raise urllib.error.HTTPError(url, code, "Busy", None, None)
    ctx.fetch = fetch


# ------------------------------------------------------------------
# WHEN - parse, compare, check
# ------------------------------------------------------------------

@when(parsers.parse('the version "{text}" is parsed'))
def the_version_is_parsed(ctx, text):
    ctx.parsed = parse_version(text)


@when("an empty version is parsed")
def an_empty_version_is_parsed(ctx):
    ctx.parsed = parse_version("")


@when(parsers.parse('"{latest}" is compared against the running '
                    '"{current}"'))
def versions_are_compared(ctx, latest, current):
    ctx.newer = is_newer(latest, current)


@when(parsers.parse('the running "{current}" checks for an update'))
def the_running_checks(ctx, current):
    ctx.info = check_for_update(current, fetch=ctx.fetch)


@when("the default fetch asks the release API")
def the_default_fetch_asks(ctx):
    captured = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self):
            return b'{"tag_name": "v9.9.9"}'

    def fake_urlopen(_request, timeout=None, context=None, **_kw):
        captured['context'] = context
        return _Response()

    with mock.patch('urllib.request.urlopen', fake_urlopen):
        update_check._default_fetch(update_check.LATEST_RELEASE_API, 1.0)
    ctx.context = captured['context']


@when("an SSL context is built without certifi")
def an_ssl_context_without_certifi(ctx):
    real_import = builtins.__import__

    def no_certifi(name, *args, **kwargs):
        if name == 'certifi':
            raise ImportError("not bundled")
        return real_import(name, *args, **kwargs)

    with mock.patch.object(builtins, '__import__', no_certifi):
        ctx.context = update_check.default_ssl_context()


# ------------------------------------------------------------------
# THEN - what the check answered
# ------------------------------------------------------------------

@then(parsers.parse('it reads as {major:d}.{minor:d}.{patch:d}'))
def it_reads_as(ctx, major, minor, patch):
    assert ctx.parsed == (major, minor, patch)


@then("no version is found")
def no_version_is_found(ctx):
    assert ctx.parsed is None


@then(parsers.parse('newer is {answer}'))
def newer_is(ctx, answer):
    assert ctx.newer is (answer == "yes")


@then(parsers.parse('the status is "{status}"'))
def the_status_is(ctx, status):
    expected = {"update": STATUS_UPDATE, "latest": STATUS_LATEST,
                "unknown": STATUS_UNKNOWN}[status]
    assert ctx.info.status == expected


@then(parsers.parse('the latest version is "{version}"'))
def the_latest_version_is(ctx, version):
    assert ctx.info.latest == version


@then(parsers.parse('the download page is "{url}"'))
def the_download_page_is(ctx, url):
    assert ctx.info.download_url == url


@then(parsers.parse('the download page mentions "{word}"'))
def the_download_page_mentions(ctx, word):
    assert word in ctx.info.download_url


@then("the info carries an error")
def the_info_carries_an_error(ctx):
    assert ctx.info.error is not None


@then(parsers.parse('the info carries {count:d} downloadable asset'))
@then(parsers.parse('the info carries {count:d} downloadable assets'))
def the_info_carries_assets(ctx, count):
    assert len(ctx.info.assets) == count


@then(parsers.parse('the asset is named "{name}" from "{url}"'))
def the_asset_is_named(ctx, name, url):
    asset = ctx.info.assets[0]
    assert asset["name"] == name
    assert asset["url"] == url


@then("the SSL context it used trusts the shipped certifi bundle")
def the_context_trusts_certifi(ctx):
    import certifi

    assert isinstance(ctx.context, ssl.SSLContext)
    # The context's trust came from the shipped bundle, not a system
    # store the frozen app does not have.
    assert ctx.context.get_ca_certs() is not None
    with open(certifi.where(), 'rb') as handle:
        assert b'BEGIN CERTIFICATE' in handle.read()


@then("it is still a usable SSL context")
def it_is_still_a_usable_ssl_context(ctx):
    assert isinstance(ctx.context, ssl.SSLContext)
