"""Tests fuer desktop/keyring_helper.py."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def test_is_admin_pin_set_returns_true_when_set(monkeypatch):
    import desktop.keyring_helper as kh

    fake_kr = MagicMock()
    fake_kr.get_password.return_value = "1234"
    monkeypatch.setattr(kh, "_keyring", lambda: fake_kr)
    assert kh.is_admin_pin_set() is True


def test_is_admin_pin_set_returns_false_when_unset(monkeypatch):
    import desktop.keyring_helper as kh

    fake_kr = MagicMock()
    fake_kr.get_password.return_value = None
    monkeypatch.setattr(kh, "_keyring", lambda: fake_kr)
    assert kh.is_admin_pin_set() is False


def test_is_admin_pin_set_returns_false_when_keyring_missing(monkeypatch):
    import desktop.keyring_helper as kh

    def boom():
        raise ImportError("keyring not installed")

    monkeypatch.setattr(kh, "_keyring", boom)
    assert kh.is_admin_pin_set() is False


def test_set_admin_pin_calls_keyring(monkeypatch):
    import desktop.keyring_helper as kh

    fake_kr = MagicMock()
    monkeypatch.setattr(kh, "_keyring", lambda: fake_kr)
    kh.set_admin_pin(" 1234 ")
    fake_kr.set_password.assert_called_once_with("c3po-admin", "admin-pin", "1234")


def test_verify_pin_correct(monkeypatch):
    import desktop.keyring_helper as kh

    fake_kr = MagicMock()
    fake_kr.get_password.return_value = "1234"
    monkeypatch.setattr(kh, "_keyring", lambda: fake_kr)
    assert kh.verify_pin("1234") is True


def test_verify_pin_wrong(monkeypatch):
    import desktop.keyring_helper as kh

    fake_kr = MagicMock()
    fake_kr.get_password.return_value = "1234"
    monkeypatch.setattr(kh, "_keyring", lambda: fake_kr)
    assert kh.verify_pin("9999") is False


def test_verify_pin_no_pin_set(monkeypatch):
    import desktop.keyring_helper as kh

    fake_kr = MagicMock()
    fake_kr.get_password.return_value = None
    monkeypatch.setattr(kh, "_keyring", lambda: fake_kr)
    assert kh.verify_pin("1234") is False


def test_verify_pin_handles_keyring_exception(monkeypatch):
    import desktop.keyring_helper as kh

    fake_kr = MagicMock()
    fake_kr.get_password.side_effect = Exception("keyring backend kaputt")
    monkeypatch.setattr(kh, "_keyring", lambda: fake_kr)
    assert kh.verify_pin("1234") is False


def test_verify_pin_strips_whitespace(monkeypatch):
    """PIN-Vergleich ist tolerant gegen leading/trailing whitespace
    (Tray-Eingabe vs. Storage)."""
    import desktop.keyring_helper as kh

    fake_kr = MagicMock()
    fake_kr.get_password.return_value = "1234"
    monkeypatch.setattr(kh, "_keyring", lambda: fake_kr)
    assert kh.verify_pin("  1234  ") is True
