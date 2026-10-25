"""Integration tests running the coordinator inside Home Assistant."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.pool_control.const import DOMAIN, EVENT_POOL_CONTROL

from .conftest import OPTIONS, setup_inputs

START = "2026-07-01 10:00:00-07:00"


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


async def _set(hass: HomeAssistant, entity_id: str, on: bool) -> None:
    await hass.services.async_call(
        "input_boolean", "turn_on" if on else "turn_off", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()


def _report(hass: HomeAssistant, ph: str = "7.2", orp: str = "760") -> None:
    """Report fresh sensor values, as the probes do every few seconds."""
    hass.states.async_set("sensor.ph", ph)
    hass.states.async_set("sensor.orp", orp)
    hass.states.async_set("sensor.water_temperature", "26", {"unit_of_measurement": "°C"})


def _state(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None, entity_id
    return state.state


@pytest.fixture(autouse=True)
def _start_time(freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(START)


async def test_setup_and_unload(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    assert loaded_entry.state is ConfigEntryState.LOADED
    for entity_id in (
        "sensor.pool_status",
        "sensor.pool_ph",
        "sensor.pool_orp",
        "sensor.pool_orp_set_point",
        "sensor.pool_ph_minus_tank_level",
        "binary_sensor.pool_swimming_allowed",
        "binary_sensor.pool_problem",
        "select.pool_operating_mode",
        "switch.pool_dry_run",
        "number.pool_ph_set_point",
        "button.pool_manual_ph_dosing_pulse",
    ):
        assert hass.states.get(entity_id) is not None, entity_id
    assert _state(hass, "select.pool_operating_mode") == "auto"

    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


async def test_entities_without_optional_actuators(hass: HomeAssistant) -> None:
    await setup_inputs(hass)
    options = {k: v for k, v in OPTIONS.items() if k not in ("chlorinator", "ph_pump")}
    entry = MockConfigEntry(domain=DOMAIN, title="Pool", version=3, options=options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.pool_orp_set_point") is None
    assert hass.states.get("button.pool_manual_ph_dosing_pulse") is None
    assert hass.states.get("sensor.pool_status") is not None


async def test_old_entry_version_rejected(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, version=2, data={"pool_pump": "switch.pump"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_schedule_starts_pump(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    assert _state(hass, "input_boolean.pump") == "on"
    assert _state(hass, "sensor.pool_status") == "stabilizing"


async def test_chlorinator_runs_after_stabilization(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    _report(hass, orp="700")
    await _tick(hass, freezer, 5)
    assert _state(hass, "input_boolean.chlorinator") == "off"

    await _tick(hass, freezer, 30)
    _report(hass, orp="701")
    await _tick(hass, freezer, 1)
    assert _state(hass, "input_boolean.chlorinator") == "on"
    assert _state(hass, "sensor.pool_status") == "chlorinating"


async def test_interlock_on_pump_off(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    # In dry-run mode the controller does not switch, only the interlock acts.
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.pool_dry_run"}, blocking=True
    )
    await _set(hass, "input_boolean.chlorinator", True)
    assert _state(hass, "input_boolean.chlorinator") == "on"
    events = async_capture_events(hass, EVENT_POOL_CONTROL)
    await _set(hass, "input_boolean.pump", False)
    assert _state(hass, "input_boolean.chlorinator") == "off"
    assert [e.data["type"] for e in events if e.data.get("reason") == "pump_off"] == ["interlock"]


async def test_interlock_on_actuator_without_pump(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.pool_operating_mode", "option": "maintenance"},
        blocking=True,
    )
    await _set(hass, "input_boolean.pump", False)
    await _set(hass, "input_boolean.ph_pump", True)
    assert _state(hass, "input_boolean.ph_pump") == "off"


async def test_ph_pulse_and_tank_tracking(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    await _tick(hass, freezer, 31)
    _report(hass, ph="7.5")
    await _tick(hass, freezer, 0.1)
    assert _state(hass, "input_boolean.ph_pump") == "on"

    freezer.tick(timedelta(seconds=51))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _state(hass, "input_boolean.ph_pump") == "off"

    dosed = float(_state(hass, "sensor.pool_ph_minus_dosed_today"))
    assert dosed == pytest.approx(21 * 57 / 60, abs=3)
    assert float(_state(hass, "sensor.pool_ph_minus_tank_level")) == pytest.approx(
        5000 - dosed, abs=1
    )
    # Lockout: no new pulse right away.
    await _tick(hass, freezer, 1)
    assert _state(hass, "input_boolean.ph_pump") == "off"


async def test_dry_run_does_not_switch(
    hass: HomeAssistant, config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    await setup_inputs(hass)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.pool_dry_run"}, blocking=True
    )
    events = async_capture_events(hass, EVENT_POOL_CONTROL)
    await _set(hass, "input_boolean.pump", False)
    await _tick(hass, freezer, 2)
    assert _state(hass, "input_boolean.pump") == "off"
    assert any(e.data["type"] == "simulated_action" for e in events)


async def test_mode_number_and_switch_entities(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.pool_ph_set_point", "value": 7.3},
        blocking=True,
    )
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.pool_ph_control"}, blocking=True
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.pool_operating_mode", "option": "winter"},
        blocking=True,
    )
    coordinator = loaded_entry.runtime_data
    assert coordinator.state.ph_target == 7.3
    assert coordinator.state.ph_control_enabled is False
    assert coordinator.state.mode == "winter"
    assert _state(hass, "input_boolean.pump") == "off"
    assert _state(hass, "number.pool_ph_set_point") == "7.3"
    assert _state(hass, "switch.pool_ph_control") == "off"


async def test_buttons(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    coordinator = loaded_entry.runtime_data
    coordinator.state.tank_level_ml = 100
    coordinator.state.ph_dosing_locked = True
    for button in ("pool_ph_minus_tank_refilled", "pool_release_ph_dosing_lock"):
        await hass.services.async_call(
            "button", "press", {"entity_id": f"button.{button}"}, blocking=True
        )
    assert coordinator.state.tank_level_ml == 5000
    assert coordinator.state.ph_dosing_locked is False

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.pool_start_extra_circulation"}, blocking=True
    )
    assert coordinator.state.boost_until is not None
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.pool_stop_extra_circulation"}, blocking=True
    )
    assert coordinator.state.boost_until is None


async def test_manual_pulse(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.pool_manual_ph_dosing_pulse"}, blocking=True
    )
    assert _state(hass, "input_boolean.ph_pump") == "on"


async def test_manual_pulse_blocked(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.pool_operating_mode", "option": "maintenance"},
        blocking=True,
    )
    await _set(hass, "input_boolean.pump", False)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.pool_manual_ph_dosing_pulse"}, blocking=True
        )
    assert _state(hass, "input_boolean.ph_pump") == "off"


async def test_boost_not_possible_in_winter(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    await loaded_entry.runtime_data.async_set_runtime(mode="winter")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "start_boost", {"config_entry_id": loaded_entry.entry_id}, blocking=True
        )


async def _call(hass: HomeAssistant, service: str, data: dict[str, Any]) -> Any:
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True
    )


async def test_services(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    entry_id = loaded_entry.entry_id
    coordinator = loaded_entry.runtime_data

    response = await _call(
        hass, "calculate_ph_correction", {"config_entry_id": entry_id, "current_ph": 7.4}
    )
    assert response == {
        "current_ph": 7.4,
        "target_ph": 7.2,
        "dose_ml": 1032,
        "product_dose": 300.0,
    }
    response = await _call(
        hass,
        "calculate_salt_correction",
        {"config_entry_id": entry_id, "current_ppm": 3000, "target_ppm": 3500},
    )
    assert response == {
        "current_ppm": 3000,
        "target_ppm": 3500,
        "salt_kg": 8.6,
        "water_exchange_m3": 0,
    }

    await hass.services.async_call(
        DOMAIN, "start_boost", {"config_entry_id": entry_id, "hours": 1}, blocking=True
    )
    assert coordinator.state.boost_until is not None
    await hass.services.async_call(
        DOMAIN, "stop_boost", {"config_entry_id": entry_id}, blocking=True
    )
    assert coordinator.state.boost_until is None

    coordinator.state.ph_pump_seconds_since_refill = 1200
    await hass.services.async_call(
        DOMAIN,
        "ph_tank_refilled",
        {"config_entry_id": entry_id, "refilled_ml": 500, "level_ml": 4000},
        blocking=True,
    )
    assert coordinator.state.ph_pump_rate_calibrated == 25
    assert coordinator.state.tank_level_ml == 4000
    assert _state(hass, "sensor.pool_dosing_pump_rate") == "25.0"

    coordinator.state.ph_dosed_season_ml = 100
    coordinator.state.ph_dosing_locked = True
    await hass.services.async_call(
        DOMAIN, "reset_season", {"config_entry_id": entry_id}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "reset_ph_lock", {"config_entry_id": entry_id}, blocking=True
    )
    assert coordinator.state.ph_dosed_season_ml == 0
    assert coordinator.state.ph_dosing_locked is False


async def test_service_invalid_entry(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "stop_boost", {"config_entry_id": "missing"}, blocking=True
        )
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "stop_boost", {"config_entry_id": loaded_entry.entry_id}, blocking=True
        )


async def test_state_persisted(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, hass_storage: dict[str, Any]
) -> None:
    await loaded_entry.runtime_data.async_set_runtime(ph_target=7.35)
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    stored = hass_storage[f"{DOMAIN}.{loaded_entry.entry_id}"]["data"]
    assert stored["ph_target"] == 7.35

    assert await hass.config_entries.async_setup(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.runtime_data.state.ph_target == 7.35


async def test_missing_entity_issue(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    hass.states.async_remove("sensor.orp")
    await _tick(hass, freezer, 2)
    registry = ir.async_get(hass)
    issue_id = f"missing_entity_{loaded_entry.entry_id}_orp_sensor"
    assert registry.async_get_issue(DOMAIN, issue_id) is not None

    hass.states.async_set("sensor.orp", "750")
    await _tick(hass, freezer, 2)
    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_frost_protection_from_weather(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    await loaded_entry.runtime_data.async_set_runtime(mode="winter")
    assert _state(hass, "input_boolean.pump") == "off"
    hass.states.async_set("weather.home", "sunny", {"temperature": 30, "temperature_unit": "°F"})
    freezer.move_to("2026-07-02 03:05:00-07:00")
    await _tick(hass, freezer, 0)
    assert _state(hass, "binary_sensor.pool_frost_protection") == "on"
    assert _state(hass, "input_boolean.pump") == "on"


async def test_flow_sensor_interlock(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    await setup_inputs(hass)
    hass.states.async_set("binary_sensor.flow", "on")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        version=3,
        options={**OPTIONS, "flow_sensor": "binary_sensor.flow"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _set(hass, "input_boolean.chlorinator", True)
    hass.states.async_set("binary_sensor.flow", "off")
    await hass.async_block_till_done()
    assert _state(hass, "input_boolean.chlorinator") == "off"
    await _tick(hass, freezer, 1)
    assert _state(hass, "binary_sensor.pool_problem") == "on"


async def test_diagnostics(hass: HomeAssistant, loaded_entry: MockConfigEntry, hass_client) -> None:
    result = await get_diagnostics_for_config_entry(hass, hass_client, loaded_entry)
    assert result["options"]["pump"] == "input_boolean.pump"
    assert result["state"]["mode"] == "auto"
    assert result["decision"]["status"] == "stabilizing"
