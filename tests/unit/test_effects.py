"""Unit tests for per-signal effect and brightness at the coordinator level.

Run with: python -m pytest tests/unit/test_effects.py -v
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.signal_lights.coordinator import SignalLightsCoordinator
from custom_components.signal_lights.engine import LightConfig, Signal, SignalEngine


def _signal(name: str, sort_order: int, **kwargs) -> Signal:
    return Signal(
        name=name,
        color=kwargs.pop("color", (255, 0, 0)),
        trigger_type="condition",
        template="{{ true }}",
        sort_order=sort_order,
        **kwargs,
    )


def _coordinator(
    signals: list[Signal],
    lights: list[LightConfig],
    light_states: dict[str, dict],
    *,
    cycle_interval: int = 0,
) -> SignalLightsCoordinator:
    """Build a coordinator without running its constructor.

    hass.services.async_call records the light calls. hass.states.get returns
    a state with the given attributes, or None for a light not in light_states.
    """
    coord = object.__new__(SignalLightsCoordinator)
    coord.engine = SignalEngine()
    coord.engine.set_signals(signals)
    coord.engine.set_lights(lights)
    coord.hass = MagicMock()
    coord.hass.services.async_call = AsyncMock()

    def _get_state(entity_id: str):
        if entity_id not in light_states:
            return None
        return SimpleNamespace(attributes=light_states[entity_id])

    coord.hass.states.get = _get_state
    coord._cycle_index = 0
    coord._cycle_cancel = None
    coord._effect_lights = set()
    coord._get_cycle_interval = lambda: cycle_interval
    coord._cancel_cycle_timer = lambda: None
    return coord


def _calls(coord: SignalLightsCoordinator) -> dict[str, dict]:
    """Return {entity_id: service data} for each light.turn_on call."""
    result: dict[str, dict] = {}
    for call in coord.hass.services.async_call.call_args_list:
        domain, service, data = call.args
        assert domain == "light"
        if service == "turn_on":
            result[data["entity_id"]] = data
    return result


BLINK_LIGHT = {"effect_list": ["blink", "pulse"]}


def test_effect_is_sent_when_the_light_lists_it():
    coord = _coordinator(
        [_signal("alert", 0, effect="blink")],
        [LightConfig("light.zbt2", 255)],
        {"light.zbt2": BLINK_LIGHT},
    )
    coord.engine.activate_signal("alert")
    asyncio.run(coord._apply_light_states())
    assert _calls(coord)["light.zbt2"]["effect"] == "blink"


def test_effect_is_left_out_when_the_light_does_not_list_it():
    coord = _coordinator(
        [_signal("alert", 0, effect="rainbow")],
        [LightConfig("light.zbt2", 255)],
        {"light.zbt2": BLINK_LIGHT},
    )
    coord.engine.activate_signal("alert")
    asyncio.run(coord._apply_light_states())
    assert "effect" not in _calls(coord)["light.zbt2"]


@pytest.mark.parametrize(
    "attributes",
    [{}, {"effect_list": None}, {"effect_list": "blink"}],
    ids=["no-effect-list", "none-effect-list", "string-effect-list"],
)
def test_effect_is_left_out_when_the_light_has_no_usable_effect_list(attributes):
    coord = _coordinator(
        [_signal("alert", 0, effect="blink")],
        [LightConfig("light.zbt2", 255)],
        {"light.zbt2": attributes},
    )
    coord.engine.activate_signal("alert")
    asyncio.run(coord._apply_light_states())
    assert "effect" not in _calls(coord)["light.zbt2"]


def test_effect_is_left_out_when_the_light_state_is_missing():
    coord = _coordinator(
        [_signal("alert", 0, effect="blink")],
        [LightConfig("light.zbt2", 255)],
        {},
    )
    coord.engine.activate_signal("alert")
    asyncio.run(coord._apply_light_states())
    assert "effect" not in _calls(coord)["light.zbt2"]


def test_signal_without_effect_or_brightness_sends_the_legacy_call():
    coord = _coordinator(
        [_signal("alert", 0)],
        [LightConfig("light.zbt2", 200)],
        {"light.zbt2": BLINK_LIGHT},
    )
    coord.engine.activate_signal("alert")
    asyncio.run(coord._apply_light_states())
    assert coord.hass.services.async_call.call_args_list[0].args == (
        "light",
        "turn_on",
        {"entity_id": "light.zbt2", "rgb_color": [255, 0, 0], "brightness": 200},
    )


def test_signal_brightness_replaces_the_light_brightness():
    coord = _coordinator(
        [_signal("alert", 0, brightness=90)],
        [LightConfig("light.zbt2", 255)],
        {"light.zbt2": {}},
    )
    coord.engine.activate_signal("alert")
    asyncio.run(coord._apply_light_states())
    assert _calls(coord)["light.zbt2"]["brightness"] == 90


def test_no_signal_active_turns_the_light_off_as_before():
    coord = _coordinator(
        [_signal("alert", 0, effect="blink")],
        [LightConfig("light.zbt2", 255)],
        {"light.zbt2": BLINK_LIGHT},
    )
    asyncio.run(coord._apply_light_states())
    assert coord.hass.services.async_call.call_args_list[0].args == (
        "light",
        "turn_off",
        {"entity_id": "light.zbt2"},
    )


def test_cycling_gives_each_light_its_own_winner_values():
    alpha = _signal("alpha", 0, effect="blink", brightness=50, light_filter=["light.a"])
    beta = _signal("beta", 1, color=(0, 0, 255), effect="pulse", brightness=70)
    coord = _coordinator(
        [alpha, beta],
        [LightConfig("light.a", 255), LightConfig("light.b", 255)],
        {"light.a": BLINK_LIGHT, "light.b": BLINK_LIGHT},
        cycle_interval=5,
    )
    coord.engine.activate_signal("alpha")
    coord.engine.activate_signal("beta")
    coord._cycle_cancel = object()  # the timer is already running
    asyncio.run(coord._apply_light_states())
    calls = _calls(coord)
    # alpha is on screen: it applies to light.a only
    assert calls["light.a"]["rgb_color"] == [255, 0, 0]
    assert calls["light.a"]["effect"] == "blink"
    assert calls["light.a"]["brightness"] == 50
    # light.b is outside alpha's filter, so beta is its own winner
    assert calls["light.b"]["rgb_color"] == [0, 0, 255]
    assert calls["light.b"]["effect"] == "pulse"
    assert calls["light.b"]["brightness"] == 70


def test_trigger_signal_override_applies_to_that_activation_only():
    coord = _coordinator(
        [_signal("alert", 0, effect="blink", brightness=90)],
        [LightConfig("light.zbt2", 255)],
        {"light.zbt2": BLINK_LIGHT},
    )
    coord._flush = AsyncMock()

    assert asyncio.run(coord.async_trigger_signal("alert", effect="pulse", brightness=30))
    asyncio.run(coord._apply_light_states())
    first = _calls(coord)["light.zbt2"]
    assert (first["effect"], first["brightness"]) == ("pulse", 30)

    coord.engine.dismiss_signal("alert")
    coord.hass.services.async_call.reset_mock()
    assert asyncio.run(coord.async_trigger_signal("alert"))
    asyncio.run(coord._apply_light_states())
    second = _calls(coord)["light.zbt2"]
    assert (second["effect"], second["brightness"]) == ("blink", 90)


def test_load_engine_config_reads_effect_and_brightness_from_the_store():
    coord = object.__new__(SignalLightsCoordinator)
    coord.engine = SignalEngine()
    coord.store = MagicMock()
    coord.store.get_lights.return_value = [{"entity_id": "light.zbt2", "brightness": 255}]
    coord.store.get_signals.return_value = [
        {"name": "with", "color": [1, 2, 3], "effect": "blink", "brightness": 80},
        {"name": "without", "color": [1, 2, 3]},
    ]
    coord._load_engine_config()
    by_name = {s.name: s for s in coord.engine.signals}
    assert (by_name["with"].effect, by_name["with"].brightness) == ("blink", 80)
    assert (by_name["without"].effect, by_name["without"].brightness) == (None, None)


def test_build_data_reports_effect_and_brightness_for_each_signal():
    coord = _coordinator(
        [_signal("with", 0, effect="blink", brightness=80), _signal("without", 1)],
        [LightConfig("light.zbt2", 255)],
        {},
    )
    coord.store = MagicMock()
    coord.store.get_lights.return_value = []
    coord.store.get_notification_config.return_value = {}
    coord._signal_errors = {}
    data = coord._build_data()
    by_name = {s["name"]: s for s in data["signals"]}
    assert (by_name["with"]["effect"], by_name["with"]["brightness"]) == ("blink", 80)
    assert (by_name["without"]["effect"], by_name["without"]["brightness"]) == (None, None)


# ---------------------------------------------------------------------------
# An effect must not outlive the signal that set it
# ---------------------------------------------------------------------------

OFF_LIGHT = {"effect_list": ["blink", "pulse", "off"]}


def _last_turn_on(coord: SignalLightsCoordinator) -> dict:
    return _calls(coord)["light.zbt2"]


def _displacement_coordinator(light_state: dict) -> SignalLightsCoordinator:
    coord = _coordinator(
        [
            _signal("plain", 0, color=(0, 255, 0)),
            _signal("fx", 1, effect="blink"),
        ],
        [LightConfig("light.zbt2", 255)],
        {"light.zbt2": light_state},
    )
    coord._effect_lights = set()
    return coord


def test_a_plain_signal_that_displaces_an_effect_turns_the_effect_off():
    coord = _displacement_coordinator(OFF_LIGHT)
    coord.engine.activate_signal("fx")
    asyncio.run(coord._apply_light_states())
    assert _last_turn_on(coord)["effect"] == "blink"

    coord.hass.services.async_call.reset_mock()
    coord.engine.activate_signal("plain")
    asyncio.run(coord._apply_light_states())
    assert _last_turn_on(coord)["effect"] == "off"


def test_the_off_effect_is_sent_once_only():
    coord = _displacement_coordinator(OFF_LIGHT)
    coord.engine.activate_signal("fx")
    asyncio.run(coord._apply_light_states())
    coord.engine.activate_signal("plain")
    asyncio.run(coord._apply_light_states())

    coord.hass.services.async_call.reset_mock()
    asyncio.run(coord._apply_light_states())
    assert "effect" not in _last_turn_on(coord)


def test_no_off_effect_when_the_light_does_not_list_it():
    coord = _displacement_coordinator(BLINK_LIGHT)
    coord.engine.activate_signal("fx")
    asyncio.run(coord._apply_light_states())

    coord.hass.services.async_call.reset_mock()
    coord.engine.activate_signal("plain")
    asyncio.run(coord._apply_light_states())
    assert "effect" not in _last_turn_on(coord)


def test_turning_the_light_off_forgets_the_effect():
    coord = _displacement_coordinator(OFF_LIGHT)
    coord.engine.activate_signal("fx")
    asyncio.run(coord._apply_light_states())
    coord.engine.dismiss_signal("fx")
    asyncio.run(coord._apply_light_states())  # nothing active: turn_off

    coord.hass.services.async_call.reset_mock()
    coord.engine.activate_signal("plain")
    asyncio.run(coord._apply_light_states())
    assert "effect" not in _last_turn_on(coord)


def test_legacy_signals_never_send_an_effect_even_if_the_light_lists_off():
    coord = _coordinator(
        [_signal("plain", 0)],
        [LightConfig("light.zbt2", 255)],
        {"light.zbt2": OFF_LIGHT},
    )
    coord._effect_lights = set()
    coord.engine.activate_signal("plain")
    asyncio.run(coord._apply_light_states())
    assert "effect" not in _last_turn_on(coord)


def test_cycling_from_an_effect_signal_to_a_plain_one_turns_the_effect_off():
    coord = _displacement_coordinator(OFF_LIGHT)
    coord._cycle_interval = 5
    coord._get_cycle_interval = lambda: 5
    coord.engine.activate_signal("plain")
    coord.engine.activate_signal("fx")
    coord._cycle_cancel = object()
    active = coord.engine.get_active_signals()
    fx_index = [a.signal.name for a in active].index("fx")

    coord._cycle_index = fx_index
    asyncio.run(coord._apply_light_states())
    assert _last_turn_on(coord)["effect"] == "blink"

    coord.hass.services.async_call.reset_mock()
    coord._cycle_index = 1 - fx_index
    asyncio.run(coord._apply_light_states())
    assert _last_turn_on(coord)["effect"] == "off"
