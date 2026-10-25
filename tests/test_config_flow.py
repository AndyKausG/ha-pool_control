"""Tests for the config and options flow."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pool_control.const import DOMAIN

from .conftest import OPTIONS


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Garden pool",
            "volume": 17.2,
            "pump": "switch.pump",
            "chlorinator": "switch.chlorinator",
            "ph_pump": "switch.ph_pump",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensors"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "ph_sensor": "sensor.ph",
            "orp_sensor": "sensor.orp",
            "temperature_sensor": "sensor.temp",
            "weather": "weather.home",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garden pool"
    assert result["data"] == {}
    assert result["options"] == {
        "volume": 17.2,
        "pump": "switch.pump",
        "chlorinator": "switch.chlorinator",
        "ph_pump": "switch.ph_pump",
        "ph_sensor": "sensor.ph",
        "orp_sensor": "sensor.orp",
        "temperature_sensor": "sensor.temp",
        "weather": "weather.home",
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_duplicate_actuator(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Pool", "volume": 10, "pump": "switch.pump", "chlorinator": "switch.pump"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "duplicate_actuator"}


async def _open_step(hass: HomeAssistant, entry: MockConfigEntry, step: str) -> dict:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": step}
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_ph_dosing(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, version=3, options=OPTIONS)
    entry.add_to_hass(hass)
    result = await _open_step(hass, entry, "ph_dosing")
    assert result["step_id"] == "ph_dosing"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"ph_pulse_seconds": 58, "ph_pump_auto_off_seconds": 60}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"ph_pulse_seconds": "pulse_exceeds_auto_off"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"ph_pulse_seconds": 40, "ph_pump_auto_off_seconds": 60}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["ph_pulse_seconds"] == 40
    assert entry.options["pump"] == "input_boolean.pump"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_filtration_window_validation(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, version=3, options=OPTIONS)
    entry.add_to_hass(hass)
    result = await _open_step(hass, entry, "filtration")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"filtration_window_start": "20:00:00", "filtration_window_end": "08:00:00"},
    )
    assert result["errors"] == {"filtration_window_end": "window_invalid"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "filtration_window_start": "08:00:00",
            "filtration_window_end": "22:00:00",
            "runtime_min_hours": 10,
            "runtime_max_hours": 4,
        },
    )
    assert result["errors"] == {"runtime_max_hours": "runtime_invalid"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_remove_optional_entity(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, version=3, options=OPTIONS)
    entry.add_to_hass(hass)
    result = await _open_step(hass, entry, "entities")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "pump": "input_boolean.pump",
            "ph_sensor": "sensor.ph",
            "orp_sensor": "sensor.orp",
            "temperature_sensor": "sensor.water_temperature",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "chlorinator" not in entry.options
    assert "weather" not in entry.options
    assert entry.options["volume"] == 17.2


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("step", "user_input", "errors"),
    [
        ("chlorine", {"salt_min": 4000, "salt_max": 3000}, {"salt_max": "salt_invalid"}),
        (
            "frost_swimming",
            {"swim_ph_min": 7.6, "swim_ph_max": 7.4},
            {"swim_ph_max": "swim_ph_invalid"},
        ),
        ("measurement", {"stabilization_minutes": 20}, None),
    ],
)
async def test_options_steps(
    hass: HomeAssistant, step: str, user_input: dict, errors: dict | None
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, version=3, options=OPTIONS)
    entry.add_to_hass(hass)
    result = await _open_step(hass, entry, step)
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)
    if errors:
        assert result["errors"] == errors
    else:
        assert result["type"] is FlowResultType.CREATE_ENTRY
