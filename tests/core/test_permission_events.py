"""Tests fuer die neuen Permission-Event-Typen."""
from __future__ import annotations

from openjarvis.core.events import EventBus, EventType


def test_permission_event_types_exist():
    assert EventType.PERMISSION_CONFIRM_REQUESTED.value == "permission_confirm_requested"
    assert EventType.PERMISSION_PIN_REQUESTED.value == "permission_pin_requested"
    assert EventType.PERMISSION_RESOLVED.value == "permission_resolved"


def test_event_bus_round_trip_for_permission_events():
    bus = EventBus()
    received = []

    def handler(event):
        received.append(event)

    bus.subscribe(EventType.PERMISSION_CONFIRM_REQUESTED, handler)
    bus.publish(
        EventType.PERMISSION_CONFIRM_REQUESTED,
        {"prompt_id": "abc", "tool": "mail.send", "channel": "voice_local"},
    )
    assert len(received) == 1
    assert received[0].event_type == EventType.PERMISSION_CONFIRM_REQUESTED
    assert received[0].data["prompt_id"] == "abc"


def test_pin_and_resolved_events_independent():
    bus = EventBus()
    pin_seen = []
    resolved_seen = []

    bus.subscribe(EventType.PERMISSION_PIN_REQUESTED, lambda e: pin_seen.append(e))
    bus.subscribe(EventType.PERMISSION_RESOLVED, lambda e: resolved_seen.append(e))

    bus.publish(EventType.PERMISSION_PIN_REQUESTED, {"prompt_id": "p1"})
    bus.publish(EventType.PERMISSION_RESOLVED, {"prompt_id": "p1", "granted": True})

    assert len(pin_seen) == 1
    assert len(resolved_seen) == 1
    assert resolved_seen[0].data["granted"] is True
