"""The Pool Control integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import PoolConfigEntry, PoolCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration-wide services."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PoolConfigEntry) -> bool:
    """Set up Pool Control from a config entry."""
    coordinator = PoolCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PoolConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded


async def async_migrate_entry(hass: HomeAssistant, entry: PoolConfigEntry) -> bool:
    """Reject entries created by the pre-1.0 implementation."""
    if entry.version < 3:
        _LOGGER.error(
            "The configuration of '%s' was created by an incompatible version of "
            "Pool Control. Please remove the entry and set it up again",
            entry.title,
        )
        return False
    return True


async def _async_update_listener(hass: HomeAssistant, entry: PoolConfigEntry) -> None:
    """Reload the entry when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)
