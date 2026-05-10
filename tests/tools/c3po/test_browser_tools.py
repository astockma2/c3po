"""Tests fuer c3po/browser_tools.py — Stage 3 Sub-Stufe 3.5.

Playwright wird NIE echt gestartet. Wir patchen ``_get_page`` und
``_get_context`` mit MagicMocks.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from openjarvis.tools.c3po.browser_tools import (
    BrowserClickTool,
    BrowserCloseTabTool,
    BrowserFillTool,
    BrowserListTabsTool,
    BrowserNewTabTool,
    BrowserOpenUrlTool,
    BrowserReadPageTool,
    BrowserScreenshotTool,
)


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.title.return_value = "Example"
    page.url = "https://example.com"
    return page


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    return ctx


# ---------------------------------------------------------------------------
# browser.open_url
# ---------------------------------------------------------------------------


class TestBrowserOpenUrl:
    def test_spec(self):
        assert BrowserOpenUrlTool().spec.name == "browser.open_url"

    def test_no_url_fails(self):
        r = BrowserOpenUrlTool().execute(url="")
        assert r.success is False

    def test_adds_https_prefix(self, mock_page):
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_page", return_value=mock_page
        ):
            r = BrowserOpenUrlTool().execute(url="example.com")
        assert r.success is True
        called_url = mock_page.goto.call_args[0][0]
        assert called_url.startswith("https://")

    def test_keeps_explicit_scheme(self, mock_page):
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_page", return_value=mock_page
        ):
            BrowserOpenUrlTool().execute(url="http://insecure.example")
        assert mock_page.goto.call_args[0][0].startswith("http://")


# ---------------------------------------------------------------------------
# browser.new_tab
# ---------------------------------------------------------------------------


class TestBrowserNewTab:
    def test_creates_new_page(self, mock_context):
        new_page = MagicMock()
        new_page.title.return_value = "New"
        mock_context.new_page.return_value = new_page
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_context",
            return_value=mock_context,
        ):
            r = BrowserNewTabTool().execute()
        assert r.success is True
        mock_context.new_page.assert_called_once()
        new_page.goto.assert_not_called()  # ohne URL nicht navigieren

    def test_with_url_navigates(self, mock_context):
        new_page = MagicMock()
        new_page.title.return_value = "X"
        mock_context.new_page.return_value = new_page
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_context",
            return_value=mock_context,
        ):
            BrowserNewTabTool().execute(url="example.com")
        new_page.goto.assert_called_once()


# ---------------------------------------------------------------------------
# browser.list_tabs
# ---------------------------------------------------------------------------


class TestBrowserListTabs:
    def test_lists_all_pages(self, mock_context):
        p1 = MagicMock()
        p1.title.return_value = "A"
        p1.url = "https://a"
        p2 = MagicMock()
        p2.title.return_value = "B"
        p2.url = "https://b"
        mock_context.pages = [p1, p2]
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_context",
            return_value=mock_context,
        ):
            r = BrowserListTabsTool().execute()
        assert r.success is True
        assert "A" in r.content and "B" in r.content
        assert r.metadata["count"] == 2

    def test_no_tabs(self, mock_context):
        mock_context.pages = []
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_context",
            return_value=mock_context,
        ):
            r = BrowserListTabsTool().execute()
        assert "Keine" in r.content


# ---------------------------------------------------------------------------
# browser.close_tab
# ---------------------------------------------------------------------------


class TestBrowserCloseTab:
    def test_invalid_index(self):
        for bad in (None, -1, "abc"):
            r = BrowserCloseTabTool().execute(index=bad)
            assert r.success is False

    def test_index_out_of_range(self, mock_context):
        mock_context.pages = []
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_context",
            return_value=mock_context,
        ):
            r = BrowserCloseTabTool().execute(index=5)
        assert r.success is False
        assert "ausserhalb" in r.content

    def test_closes_correct_tab(self, mock_context):
        p1, p2 = MagicMock(), MagicMock()
        p1.title.return_value = "First"
        p2.title.return_value = "Second"
        mock_context.pages = [p1, p2]
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_context",
            return_value=mock_context,
        ):
            r = BrowserCloseTabTool().execute(index=1)
        assert r.success is True
        assert "Second" in r.content
        p2.close.assert_called_once()
        p1.close.assert_not_called()


# ---------------------------------------------------------------------------
# browser.click
# ---------------------------------------------------------------------------


class TestBrowserClick:
    def test_no_selector_fails(self):
        r = BrowserClickTool().execute(selector="")
        assert r.success is False

    def test_clicks_selector(self, mock_page):
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_page", return_value=mock_page
        ):
            r = BrowserClickTool().execute(selector="button.submit")
        assert r.success is True
        mock_page.click.assert_called_once()
        assert mock_page.click.call_args[0][0] == "button.submit"


# ---------------------------------------------------------------------------
# browser.fill
# ---------------------------------------------------------------------------


class TestBrowserFill:
    def test_no_selector_fails(self):
        r = BrowserFillTool().execute(selector="", value="x")
        assert r.success is False

    def test_fills_value(self, mock_page):
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_page", return_value=mock_page
        ):
            r = BrowserFillTool().execute(selector="#user", value="andre")
        assert r.success is True
        mock_page.fill.assert_called_once_with("#user", "andre", timeout=10000)
        # Ohne submit kein Enter
        mock_page.keyboard.press.assert_not_called()

    def test_submit_presses_enter(self, mock_page):
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_page", return_value=mock_page
        ):
            BrowserFillTool().execute(selector="#q", value="hi", submit=True)
        mock_page.keyboard.press.assert_called_once_with("Enter")


# ---------------------------------------------------------------------------
# browser.screenshot
# ---------------------------------------------------------------------------


class TestBrowserScreenshot:
    def test_screenshot_default_filename(self, mock_page, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "openjarvis.tools.c3po.browser_tools._SCREENSHOT_DIR", tmp_path
        )
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_page", return_value=mock_page
        ):
            r = BrowserScreenshotTool().execute()
        assert r.success is True
        called_path = mock_page.screenshot.call_args.kwargs["path"]
        assert "screenshot.png" in called_path

    def test_appends_png_extension(self, mock_page, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "openjarvis.tools.c3po.browser_tools._SCREENSHOT_DIR", tmp_path
        )
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_page", return_value=mock_page
        ):
            r = BrowserScreenshotTool().execute(filename="foo")
        called_path = mock_page.screenshot.call_args.kwargs["path"]
        assert called_path.endswith("foo.png")


# ---------------------------------------------------------------------------
# browser.read_page
# ---------------------------------------------------------------------------


class TestBrowserReadPage:
    def test_reads_text(self, mock_page):
        mock_page.evaluate.return_value = "Hello world from this page"
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_page", return_value=mock_page
        ):
            r = BrowserReadPageTool().execute()
        assert r.success is True
        assert "Hello world" in r.content

    def test_truncates_long_text(self, mock_page):
        mock_page.evaluate.return_value = "x " * 5000
        with patch(
            "openjarvis.tools.c3po.browser_tools._get_page", return_value=mock_page
        ):
            r = BrowserReadPageTool().execute(max_chars=100)
        assert "gekuerzt" in r.content
