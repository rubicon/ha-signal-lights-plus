"""Unit tests for the effect and brightness settings in services and storage.

Run with: python -m pytest tests/unit/test_effect_services.py -v
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.signal_lights import services
from custom_components.signal_lights.store import SignalLightsStore

ADD_BASE = {
    "name": "Water empty",
    "color": [0, 0, 255],
    "trigger_type": "condition",
    "trigger_mode": "entity_on",
    "trigger_config": {"entity_id": "binary_sensor.rocky_water"},
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


def test_add_signal_schema_accepts_effect_and_brightness():
    data = services.ADD_SIGNAL_SCHEMA({**ADD_BASE, "effect": "pulse", "brightness": 80})
    assert data["effect"] == "pulse"
    assert data["brightness"] == 80


def test_add_signal_schema_keeps_both_settings_optional():
    data = services.ADD_SIGNAL_SCHEMA(ADD_BASE)
    assert "effect" not in data
    assert "brightness" not in data


@pytest.mark.parametrize("brightness", [0, -1, 256, 1000])
def test_brightness_outside_1_to_255_is_rejected(brightness):
    for schema, base in (
        (services.ADD_SIGNAL_SCHEMA, ADD_BASE),
        (services.UPDATE_SIGNAL_SCHEMA, {"name": "Water empty"}),
        (services.TRIGGER_SIGNAL_SCHEMA, {"name": "Water empty"}),
    ):
        with pytest.raises(services.vol.Invalid):
            schema({**base, "brightness": brightness})


def test_effect_longer_than_64_characters_is_rejected():
    with pytest.raises(services.vol.Invalid):
        services.ADD_SIGNAL_SCHEMA({**ADD_BASE, "effect": "x" * 65})


def test_effect_is_trimmed():
    data = services.TRIGGER_SIGNAL_SCHEMA({"name": "Water empty", "effect": "  blink  "})
    assert data["effect"] == "blink"


def test_update_signal_schema_allows_clearing_both_settings():
    data = services.UPDATE_SIGNAL_SCHEMA(
        {"name": "Water empty", "effect": "", "brightness": None}
    )
    assert data["effect"] == ""
    assert data["brightness"] is None


def test_trigger_signal_schema_accepts_overrides():
    data = services.TRIGGER_SIGNAL_SCHEMA(
        {"name": "Water empty", "effect": "pulse", "brightness": 30}
    )
    assert (data["effect"], data["brightness"]) == ("pulse", 30)


# ---------------------------------------------------------------------------
# Storage normalisation
# ---------------------------------------------------------------------------


def _normalize(sig: dict) -> dict:
    store = object.__new__(SignalLightsStore)
    store._normalize_signal(sig, 0)
    return sig


def test_store_keeps_effect_and_brightness_when_set():
    sig = _normalize({"name": "a", "effect": "blink", "brightness": 80})
    assert sig["effect"] == "blink"
    assert sig["brightness"] == 80


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_store_drops_a_blank_effect(blank):
    assert "effect" not in _normalize({"name": "a", "effect": blank})


def test_store_drops_a_null_brightness():
    assert "brightness" not in _normalize({"name": "a", "brightness": None})


def test_store_adds_neither_key_to_a_legacy_signal():
    sig = _normalize({"name": "a", "color": [1, 2, 3]})
    assert "effect" not in sig
    assert "brightness" not in sig


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _register_handlers() -> dict:
    hass = MagicMock()
    hass.data = {}
    hass.services.has_service.return_value = False
    handlers: dict = {}
    hass.services.async_register.side_effect = (
        lambda domain, name, handler, schema=None: handlers.__setitem__(name, handler)
    )
    asyncio.run(services.async_register_services(hass))
    handlers["_hass"] = hass
    return handlers


def _coordinator(existing: dict | None = None) -> MagicMock:
    coord = MagicMock()
    coord.store.get_signals.return_value = []
    coord.store.get_signal_by_name.return_value = existing
    coord.store.add_signal = AsyncMock()
    coord.store.update_signal = AsyncMock(return_value=True)
    coord.async_reload_config = AsyncMock()
    coord.async_trigger_signal = AsyncMock(return_value=True)
    return coord


def _call(schema, data: dict) -> SimpleNamespace:
    return SimpleNamespace(data=schema(data), context=SimpleNamespace(user_id=None))


def _run(handler_name: str, schema, data: dict, coord: MagicMock) -> None:
    handlers = _register_handlers()
    with (
        patch.object(services, "_resolve_coordinator", return_value=coord),
        patch.object(
            services,
            "_validate_and_generate_template",
            AsyncMock(return_value="{{ true }}"),
        ),
    ):
        asyncio.run(handlers[handler_name](_call(schema, data)))


def test_add_signal_stores_effect_and_brightness():
    coord = _coordinator()
    _run("add_signal", services.ADD_SIGNAL_SCHEMA, {**ADD_BASE, "effect": "pulse", "brightness": 80}, coord)
    stored = coord.store.add_signal.call_args.args[0]
    assert stored["effect"] == "pulse"
    assert stored["brightness"] == 80


def test_add_signal_without_them_stores_neither_key():
    coord = _coordinator()
    _run("add_signal", services.ADD_SIGNAL_SCHEMA, ADD_BASE, coord)
    stored = coord.store.add_signal.call_args.args[0]
    assert "effect" not in stored
    assert "brightness" not in stored


def test_update_signal_sets_effect_and_brightness():
    coord = _coordinator(existing={"name": "Water empty", "trigger_mode": "entity_on"})
    _run(
        "update_signal",
        services.UPDATE_SIGNAL_SCHEMA,
        {"name": "Water empty", "effect": "blink", "brightness": 60},
        coord,
    )
    updates = coord.store.update_signal.call_args.args[1]
    assert updates == {"effect": "blink", "brightness": 60}


def test_update_signal_clears_effect_and_brightness():
    coord = _coordinator(existing={"name": "Water empty", "trigger_mode": "entity_on"})
    _run(
        "update_signal",
        services.UPDATE_SIGNAL_SCHEMA,
        {"name": "Water empty", "effect": "", "brightness": None},
        coord,
    )
    updates = coord.store.update_signal.call_args.args[1]
    assert updates == {"effect": None, "brightness": None}


def test_update_signal_leaves_them_alone_when_not_given():
    coord = _coordinator(existing={"name": "Water empty", "trigger_mode": "entity_on"})
    _run(
        "update_signal",
        services.UPDATE_SIGNAL_SCHEMA,
        {"name": "Water empty", "color": [1, 2, 3]},
        coord,
    )
    updates = coord.store.update_signal.call_args.args[1]
    assert "effect" not in updates
    assert "brightness" not in updates


def test_trigger_signal_passes_the_overrides_to_the_coordinator():
    coord = _coordinator()
    _run(
        "trigger_signal",
        services.TRIGGER_SIGNAL_SCHEMA,
        {"name": "Water empty", "effect": "pulse", "brightness": 30},
        coord,
    )
    coord.async_trigger_signal.assert_awaited_once_with(
        "Water empty", effect="pulse", brightness=30
    )


def test_trigger_signal_without_overrides_passes_none():
    coord = _coordinator()
    _run("trigger_signal", services.TRIGGER_SIGNAL_SCHEMA, {"name": "Water empty"}, coord)
    coord.async_trigger_signal.assert_awaited_once_with(
        "Water empty", effect=None, brightness=None
    )


# ---------------------------------------------------------------------------
# Review follow-ups: null effect, boolean brightness
# ---------------------------------------------------------------------------


def test_update_signal_schema_accepts_a_null_effect_to_clear_it():
    data = services.UPDATE_SIGNAL_SCHEMA({"name": "Water empty", "effect": None})
    assert data["effect"] is None


def test_update_signal_with_a_null_effect_clears_it():
    coord = _coordinator(existing={"name": "Water empty", "trigger_mode": "entity_on"})
    _run("update_signal", services.UPDATE_SIGNAL_SCHEMA, {"name": "Water empty", "effect": None}, coord)
    assert coord.store.update_signal.call_args.args[1] == {"effect": None}


@pytest.mark.parametrize("brightness", [True, False])
def test_boolean_brightness_is_rejected(brightness):
    for schema, base in (
        (services.ADD_SIGNAL_SCHEMA, ADD_BASE),
        (services.UPDATE_SIGNAL_SCHEMA, {"name": "Water empty"}),
        (services.TRIGGER_SIGNAL_SCHEMA, {"name": "Water empty"}),
    ):
        with pytest.raises(services.vol.Invalid):
            schema({**base, "brightness": brightness})
