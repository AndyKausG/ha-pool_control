"""Fixtures for Pool Control tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pool_control.const import DOMAIN

OPTIONS: dict[str, Any] = {
    "volume": 17.2,
    "pump": "input_boolean.pump",
    "chlorinator": "input_boolean.chlorinator",
    "ph_pump": "input_boolean.ph_pump",
    "ph_sensor": "sensor.ph",
    "orp_sensor": "sensor.orp",
    "temperature_sensor": "sensor.water_temperature",
    "weather": "weather.home",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations in all tests."""


@pytest.fixture(autouse=True)
def expected_lingering_timers() -> bool:
    """Allow the debouncer timers of the coordinator."""
    return True


@pytest.fixture(autouse=True)
def live_by_default() -> Generator[None]:
    """Start new installations without dry run, unless a test checks the default."""
    from unittest.mock import patch

    with patch("custom_components.pool_control.coordinator.INITIAL_DRY_RUN", False):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Prevent the entry from being set up in config flow tests."""
    from unittest.mock import patch

    with patch("custom_components.pool_control.async_setup_entry", return_value=True):
        yield


async def setup_inputs(hass: HomeAssistant) -> None:
    """Create actuators and sensor states."""
    assert await async_setup_component(
        hass,
        "input_boolean",
        {"input_boolean": {"pump": {}, "chlorinator": {}, "ph_pump": {}}},
    )
    hass.states.async_set("sensor.ph", "7.2")
    hass.states.async_set("sensor.orp", "760")
    hass.states.async_set("sensor.water_temperature", "26", {"unit_of_measurement": "°C"})
    hass.states.async_set("weather.home", "sunny", {"temperature": 20, "temperature_unit": "°C"})


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a config entry."""
    return MockConfigEntry(domain=DOMAIN, title="Pool", version=3, data={}, options=OPTIONS)


@pytest.fixture
async def loaded_entry(hass: HomeAssistant, config_entry: MockConfigEntry) -> MockConfigEntry:
    """Set up the integration."""
    await setup_inputs(hass)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
