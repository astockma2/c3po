"""C3PO Browser-Tools (Stage 3 Sub-Stufe 3.5, Playwright-basiert).

8 Tools — 5 free, 3 confirm:
- ``browser.open_url`` (free)
- ``browser.new_tab`` (free)
- ``browser.list_tabs`` (free)
- ``browser.read_page`` (free)
- ``browser.screenshot`` (free)
- ``browser.click`` (confirm)
- ``browser.fill`` (confirm)
- ``browser.close_tab`` (confirm)

Persistent-State-Verzeichnis: ``%LOCALAPPDATA%\\C3PO\\browser-data\\``.
Cookies/Logins bleiben dort.

Tests patchen ``_get_page`` — keine echte Playwright-Session in CI.
"""

from __future__ import annotations

import atexit
import os
import threading
from pathlib import Path
from typing import Any, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


_USER_DATA_DIR = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    / "C3PO"
    / "browser-data"
)
_SCREENSHOT_DIR = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    / "C3PO"
    / "screenshots"
)

# Browser-Singleton — lazy gestartet beim ersten Tool-Call.
_lock = threading.Lock()
_pw_instance: Any = None
_context: Any = None
_page: Any = None


def _ensure_browser() -> Any:
    """Startet Chromium mit persistent context. Tests patchen das."""
    global _pw_instance, _context, _page
    with _lock:
        if _context is not None and _page is not None:
            try:
                _ = _page.title()
                return _page
            except Exception:
                _page = None
                _context = None
        from playwright.sync_api import sync_playwright

        if _pw_instance is None:
            _pw_instance = sync_playwright().start()
            atexit.register(_cleanup)
        _USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        _context = _pw_instance.chromium.launch_persistent_context(
            user_data_dir=str(_USER_DATA_DIR),
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--start-maximized"],
        )
        if _context.pages:
            _page = _context.pages[0]
        else:
            _page = _context.new_page()
        return _page


def _get_page() -> Any:
    """Indirektion fuer Tests — patched zu MagicMock."""
    return _ensure_browser()


def _get_context() -> Any:
    """Liefert den persistent_context (fuer Tab-Operationen)."""
    _get_page()  # erzwingt Init
    return _context


def _cleanup() -> None:
    global _context, _pw_instance, _page
    try:
        if _context is not None:
            _context.close()
    except Exception:
        pass
    try:
        if _pw_instance is not None:
            _pw_instance.stop()
    except Exception:
        pass
    _context = None
    _pw_instance = None
    _page = None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@ToolRegistry.register("browser.open_url")
class BrowserOpenUrlTool(BaseTool):
    """Oeffnet eine URL im aktiven Tab."""

    tool_id = "browser.open_url"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="browser.open_url",
            description=(
                "Oeffnet eine URL im aktiven Tab. Permission: free."
            ),
            parameters={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
            category="browser",
        )

    def execute(self, **params: Any) -> ToolResult:
        url = (params.get("url") or "").strip()
        if not url:
            return ToolResult(
                tool_name="browser.open_url", content="Keine URL.", success=False
            )
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            page = _get_page()
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            return ToolResult(
                tool_name="browser.open_url",
                content=f"Geoeffnet: {page.title()} ({url})",
                success=True,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="browser.open_url", content=f"Fehler: {exc}", success=False
            )


@ToolRegistry.register("browser.new_tab")
class BrowserNewTabTool(BaseTool):
    """Oeffnet einen neuen Tab und navigiert optional dahin."""

    tool_id = "browser.new_tab"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="browser.new_tab",
            description=(
                "Oeffnet einen neuen Tab. Optional: URL direkt dort laden. "
                "Permission: free."
            ),
            parameters={
                "type": "object",
                "properties": {"url": {"type": "string"}},
            },
            category="browser",
        )

    def execute(self, **params: Any) -> ToolResult:
        url = (params.get("url") or "").strip()
        try:
            ctx = _get_context()
            page = ctx.new_page()
            global _page
            _page = page  # neuer Tab wird aktiv
            if url:
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
            return ToolResult(
                tool_name="browser.new_tab",
                content=f"Neuer Tab geoeffnet ({page.title() if url else 'leer'}).",
                success=True,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="browser.new_tab", content=f"Fehler: {exc}", success=False
            )


@ToolRegistry.register("browser.list_tabs")
class BrowserListTabsTool(BaseTool):
    """Listet alle offenen Tabs (Titel + URL)."""

    tool_id = "browser.list_tabs"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="browser.list_tabs",
            description="Listet alle offenen Browser-Tabs. Permission: free.",
            parameters={"type": "object", "properties": {}},
            category="browser",
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            ctx = _get_context()
            tabs = []
            for i, p in enumerate(ctx.pages):
                tabs.append(f"[{i}] {p.title()} — {p.url}")
            return ToolResult(
                tool_name="browser.list_tabs",
                content="\n".join(tabs) if tabs else "Keine Tabs offen.",
                success=True,
                metadata={"count": len(tabs)},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="browser.list_tabs", content=f"Fehler: {exc}", success=False
            )


@ToolRegistry.register("browser.close_tab")
class BrowserCloseTabTool(BaseTool):
    """Schliesst einen Tab per Index. Permission: confirm."""

    tool_id = "browser.close_tab"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="browser.close_tab",
            description=(
                "Schliesst einen Tab per Index (siehe browser.list_tabs). "
                "Permission: confirm."
            ),
            parameters={
                "type": "object",
                "properties": {"index": {"type": "integer"}},
                "required": ["index"],
            },
            category="browser",
        )

    def execute(self, **params: Any) -> ToolResult:
        idx: Optional[int] = params.get("index")
        if not isinstance(idx, int) or idx < 0:
            return ToolResult(
                tool_name="browser.close_tab",
                content="Ungueltiger Index.",
                success=False,
            )
        try:
            ctx = _get_context()
            pages = list(ctx.pages)
            if idx >= len(pages):
                return ToolResult(
                    tool_name="browser.close_tab",
                    content=f"Index {idx} ausserhalb (0..{len(pages)-1}).",
                    success=False,
                )
            target = pages[idx]
            title = target.title()
            target.close()
            return ToolResult(
                tool_name="browser.close_tab",
                content=f"Tab geschlossen: {title}",
                success=True,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="browser.close_tab",
                content=f"Fehler: {exc}",
                success=False,
            )


@ToolRegistry.register("browser.click")
class BrowserClickTool(BaseTool):
    """Klickt auf ein Element. Permission: confirm."""

    tool_id = "browser.click"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="browser.click",
            description=(
                "Klickt auf ein Element via CSS-Selector oder 'text=...'. "
                "Permission: confirm."
            ),
            parameters={
                "type": "object",
                "properties": {"selector": {"type": "string"}},
                "required": ["selector"],
            },
            category="browser",
        )

    def execute(self, **params: Any) -> ToolResult:
        sel = (params.get("selector") or "").strip()
        if not sel:
            return ToolResult(
                tool_name="browser.click", content="Kein Selector.", success=False
            )
        try:
            page = _get_page()
            page.click(sel, timeout=10000)
            return ToolResult(
                tool_name="browser.click",
                content=f"Geklickt: {sel}",
                success=True,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="browser.click", content=f"Fehler: {exc}", success=False
            )


@ToolRegistry.register("browser.fill")
class BrowserFillTool(BaseTool):
    """Fuellt ein Formularfeld. Permission: confirm."""

    tool_id = "browser.fill"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="browser.fill",
            description=(
                "Fuellt ein Formularfeld (CSS-Selector). Permission: confirm."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "selector": {"type": "string"},
                    "value": {"type": "string"},
                    "submit": {
                        "type": "boolean",
                        "description": "Wenn true, drueckt am Ende Enter.",
                    },
                },
                "required": ["selector", "value"],
            },
            category="browser",
        )

    def execute(self, **params: Any) -> ToolResult:
        sel = (params.get("selector") or "").strip()
        value = params.get("value") or ""
        do_submit = bool(params.get("submit"))
        if not sel:
            return ToolResult(
                tool_name="browser.fill", content="Kein Selector.", success=False
            )
        try:
            page = _get_page()
            page.fill(sel, value, timeout=10000)
            if do_submit:
                page.keyboard.press("Enter")
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            return ToolResult(
                tool_name="browser.fill",
                content=f"Eingefuellt: {sel} (submit={do_submit})",
                success=True,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="browser.fill", content=f"Fehler: {exc}", success=False
            )


@ToolRegistry.register("browser.screenshot")
class BrowserScreenshotTool(BaseTool):
    """Screenshot der aktuellen Seite (free)."""

    tool_id = "browser.screenshot"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="browser.screenshot",
            description=(
                "Speichert einen Screenshot des aktuellen Tabs als PNG. "
                "Permission: free."
            ),
            parameters={
                "type": "object",
                "properties": {"filename": {"type": "string"}},
            },
            category="browser",
        )

    def execute(self, **params: Any) -> ToolResult:
        filename = (params.get("filename") or "screenshot.png").strip()
        if not filename.endswith(".png"):
            filename += ".png"
        try:
            _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            path = _SCREENSHOT_DIR / filename
            page = _get_page()
            page.screenshot(path=str(path), full_page=False)
            return ToolResult(
                tool_name="browser.screenshot",
                content=f"Screenshot: {path}",
                success=True,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="browser.screenshot", content=f"Fehler: {exc}", success=False
            )


@ToolRegistry.register("browser.read_page")
class BrowserReadPageTool(BaseTool):
    """Liefert sichtbaren Text der aktuellen Seite (free)."""

    tool_id = "browser.read_page"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="browser.read_page",
            description=(
                "Liefert den sichtbaren Text des aktuellen Tabs. "
                "Permission: free."
            ),
            parameters={
                "type": "object",
                "properties": {"max_chars": {"type": "integer"}},
            },
            category="browser",
        )

    def execute(self, **params: Any) -> ToolResult:
        max_chars = int(params.get("max_chars") or 3000)
        try:
            page = _get_page()
            text = page.evaluate("() => document.body.innerText") or ""
            text = " ".join(text.split())
            if len(text) > max_chars:
                text = text[:max_chars] + "... (gekuerzt)"
            return ToolResult(
                tool_name="browser.read_page",
                content=f"--- {page.title()} ---\n{text}",
                success=True,
                metadata={"chars": len(text)},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="browser.read_page", content=f"Fehler: {exc}", success=False
            )


__all__ = [
    "BrowserOpenUrlTool",
    "BrowserNewTabTool",
    "BrowserListTabsTool",
    "BrowserCloseTabTool",
    "BrowserClickTool",
    "BrowserFillTool",
    "BrowserScreenshotTool",
    "BrowserReadPageTool",
]
