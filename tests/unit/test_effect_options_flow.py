"""Unit tests for setting a signal's effect and brightness in the options flow.

Run with: python -m pytest tests/unit/test_effect_options_flow.py -v
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from custom_components.signal_lights.config_flow import SignalLightsOptionsFlow

STEP_ONE = {
    "name": "Water empty",
    "color": [0, 0, 255],
    "trigger_type": "condition",
    "trigger_mode": "entity_on",
}


def _flow() -> tuple[SignalLightsOptionsFlow, MagicMock]:
    flow = SignalLightsOptionsFlow()
    store = MagicMock()
    store.add_signal = AsyncMock()
    flow._get_store = lambda: store
    flow._reload_coordinator = AsyncMock()
    flow.async_step_trigger_entity_on = AsyncMock(return_value="next-step")
    return flow, store


def _add_signal(user_input: dict) -> tuple[SignalLightsOptionsFlow, MagicMock]:
    """Run step one, then save the signal the way the last step does."""
    flow, store = _flow()
    asyncio.run(flow.async_step_add_signal(user_input))
    flow._signal_data["trigger_config"] = {"entity_id": "binary_sensor.rocky_water"}
    flow._signal_data["template"] = "{{ is_state('binary_sensor.rocky_water', 'on') }}"
    asyncio.run(flow._finalize_signal({"duration": 0}))
    return flow, store


def _saved(store: MagicMock) -> dict:
    return store.add_signal.call_args.args[0]


def test_first_step_offers_optional_effect_and_brightness():
    flow, _ = _flow()
    result = asyncio.run(flow.async_step_add_signal())
    keys = {str(key): key for key in result["data_schema"].schema}
    assert "effect" in keys and "brightness" in keys
    # Optional: the form validates without either
    result["data_schema"](STEP_ONE)


def test_effect_and_brightness_are_saved_with_the_signal():
    _, store = _add_signal({**STEP_ONE, "effect": "pulse", "brightness": 80.0})
    saved = _saved(store)
    assert saved["effect"] == "pulse"
    assert saved["brightness"] == 80
    assert isinstance(saved["brightness"], int)


def test_neither_key_is_saved_when_neither_is_given():
    _, store = _add_signal(STEP_ONE)
    saved = _saved(store)
    assert "effect" not in saved
    assert "brightness" not in saved


def test_a_blank_effect_is_not_saved():
    _, store = _add_signal({**STEP_ONE, "effect": "   "})
    assert "effect" not in _saved(store)


def test_the_effect_is_trimmed():
    _, store = _add_signal({**STEP_ONE, "effect": "  blink "})
    assert _saved(store)["effect"] == "blink"


def test_flow_state_is_cleared_after_saving():
    flow, _ = _add_signal({**STEP_ONE, "effect": "pulse", "brightness": 80})
    assert flow._signal_data == {}
