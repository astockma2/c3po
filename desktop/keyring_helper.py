"""Wrapper um keyring fuer Windows Credential Manager.

PIN-Hash + Admin-Session-Logik.
"""
from __future__ import annotations

import hmac
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_SERVICE = "c3po-admin"
_USERNAME = "admin-pin"


def _keyring():
    """Lazy-Import - keyring ist optionale dep."""
    import keyring as _kr
    return _kr


def is_admin_pin_set() -> bool:
    """True wenn ein PIN im Credential Manager liegt."""
    try:
        kr = _keyring()
    except ImportError:
        logger.warning("keyring nicht installiert - PIN-Setup nicht moeglich")
        return False
    try:
        return bool(kr.get_password(_SERVICE, _USERNAME))
    except Exception as exc:
        logger.warning("keyring.get_password fehlgeschlagen: %s", exc)
        return False


def set_admin_pin(pin: str) -> None:
    """Speichert PIN im Credential Manager."""
    kr = _keyring()
    kr.set_password(_SERVICE, _USERNAME, pin.strip())


def verify_pin(pin: str) -> bool:
    """Vergleicht eingegebene PIN gegen gespeicherte PIN.

    Konstantzeitig via hmac.compare_digest. Returns False wenn keiner gesetzt.
    """
    try:
        kr = _keyring()
    except ImportError:
        return False
    try:
        expected = kr.get_password(_SERVICE, _USERNAME)
    except Exception as exc:
        logger.warning("keyring.get_password fehlgeschlagen: %s", exc)
        return False
    if not expected:
        return False
    return hmac.compare_digest(pin.strip(), expected.strip())


def reset_admin_pin() -> None:
    """Loescht den gespeicherten PIN."""
    try:
        kr = _keyring()
        kr.delete_password(_SERVICE, _USERNAME)
    except Exception as exc:
        logger.debug("reset_admin_pin no-op: %s", exc)


__all__ = ["is_admin_pin_set", "set_admin_pin", "verify_pin", "reset_admin_pin"]
