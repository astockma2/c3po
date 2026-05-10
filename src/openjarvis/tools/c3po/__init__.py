"""C3PO-spezifische Tools (Stage 3).

Auto-Import-Loop registriert alle Tool-Module beim Import dieses Pakets.
Wird in Task 11 vervollstaendigt — hier nur die finale Liste.
"""

from __future__ import annotations

import importlib
import logging

logger = logging.getLogger(__name__)

_MODULES = (
    "time_tools",
    "windows_tools",
    "mail_tools",
    "calendar_tools",
    "browser_tools",
    "messaging_tools",
    "admin_tools",
)

for _m in _MODULES:
    try:
        importlib.import_module(f".{_m}", __name__)
    except ImportError as exc:
        logger.debug("c3po-tool-modul %s nicht ladbar: %s", _m, exc)
