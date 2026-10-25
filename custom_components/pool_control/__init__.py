"""The Pool Control integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.const import EVENT_COMPONENT_LOADED, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration
from homeassistant.setup import ATTR_COMPONENT, EventComponentLoaded

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


CARD_FILE = Path(__file__).parent / "frontend" / "pool-control-card.js"
CARD_URL = f"/{DOMAIN}/pool-control-card.js"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration-wide services and the dashboard card."""
    async_setup_services(hass)
    await _async_register_card(hass)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the dashboard card and load it in the frontend.

    If the frontend is not loaded yet, registration is deferred until it is.
    """
    if hass.http is None:
        _LOGGER.debug("HTTP not available, dashboard card not registered")
        return
    if "frontend" not in hass.config.components:

        @callback
        def _frontend_loaded(event: Event[EventComponentLoaded]) -> None:
            if event.data[ATTR_COMPONENT] == "frontend":
                remove_listener()
                hass.async_create_task(_async_register_card(hass))

        remove_listener = hass.bus.async_listen(EVENT_COMPONENT_LOADED, _frontend_loaded)
        return
    from homeassistant.components.frontend import add_extra_js_url  # noqa: PLC0415
    from homeassistant.components.http import StaticPathConfig  # noqa: PLC0415

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=False)]
    )
    integration = await async_get_integration(hass, DOMAIN)
    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
    _LOGGER.info("Pool Control dashboard card registered at %s", CARD_URL)


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
