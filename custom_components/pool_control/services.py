"""Service actions for Pool Control."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from . import chemistry
from .const import DOMAIN
from .coordinator import PoolConfigEntry, PoolCoordinator

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_HOURS = "hours"
ATTR_REFILLED_ML = "refilled_ml"
ATTR_LEVEL_ML = "level_ml"
ATTR_CURRENT_PH = "current_ph"
ATTR_TARGET_PH = "target_ph"
ATTR_CURRENT_PPM = "current_ppm"
ATTR_TARGET_PPM = "target_ppm"

SERVICE_START_BOOST = "start_boost"
SERVICE_STOP_BOOST = "stop_boost"
SERVICE_TANK_REFILLED = "ph_tank_refilled"
SERVICE_RESET_PH_LOCK = "reset_ph_lock"
SERVICE_RESET_SEASON = "reset_season"
SERVICE_PH_CORRECTION = "calculate_ph_correction"
SERVICE_SALT_CORRECTION = "calculate_salt_correction"

BASE_SCHEMA = vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string})

SCHEMAS: dict[str, vol.Schema] = {
    SERVICE_START_BOOST: BASE_SCHEMA.extend(
        {vol.Optional(ATTR_HOURS): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=24))}
    ),
    SERVICE_STOP_BOOST: BASE_SCHEMA,
    SERVICE_TANK_REFILLED: BASE_SCHEMA.extend(
        {
            vol.Optional(ATTR_REFILLED_ML): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Optional(ATTR_LEVEL_ML): vol.All(vol.Coerce(float), vol.Range(min=0)),
        }
    ),
    SERVICE_RESET_PH_LOCK: BASE_SCHEMA,
    SERVICE_RESET_SEASON: BASE_SCHEMA,
    SERVICE_PH_CORRECTION: BASE_SCHEMA.extend(
        {
            vol.Optional(ATTR_CURRENT_PH): vol.All(vol.Coerce(float), vol.Range(min=6, max=9)),
            vol.Optional(ATTR_TARGET_PH): vol.All(vol.Coerce(float), vol.Range(min=6, max=9)),
        }
    ),
    SERVICE_SALT_CORRECTION: BASE_SCHEMA.extend(
        {
            vol.Required(ATTR_CURRENT_PPM): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Optional(ATTR_TARGET_PPM, default=3500): vol.All(
                vol.Coerce(float), vol.Range(min=0)
            ),
        }
    ),
}


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> PoolCoordinator:
    entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
    entry: PoolConfigEntry | None = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
            translation_placeholders={"entry_id": entry_id},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
            translation_placeholders={"entry_id": entry_id},
        )
    return entry.runtime_data


async def _start_boost(hass: HomeAssistant, call: ServiceCall) -> None:
    await _coordinator(hass, call).async_start_boost(call.data.get(ATTR_HOURS))


async def _stop_boost(hass: HomeAssistant, call: ServiceCall) -> None:
    await _coordinator(hass, call).async_stop_boost()


async def _tank_refilled(hass: HomeAssistant, call: ServiceCall) -> None:
    await _coordinator(hass, call).async_tank_refilled(
        call.data.get(ATTR_REFILLED_ML), call.data.get(ATTR_LEVEL_ML)
    )


async def _reset_ph_lock(hass: HomeAssistant, call: ServiceCall) -> None:
    await _coordinator(hass, call).async_reset_ph_lock()


async def _reset_season(hass: HomeAssistant, call: ServiceCall) -> None:
    await _coordinator(hass, call).async_reset_season()


async def _ph_correction(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    coordinator = _coordinator(hass, call)
    current = call.data.get(ATTR_CURRENT_PH)
    if current is None:
        current = coordinator.data.measurement.ph or coordinator.state.last_valid_ph
    if current is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_ph_value")
    target = call.data.get(ATTR_TARGET_PH, coordinator.state.ph_target)
    product_dose = coordinator.controller.ph_product_dose
    dose = chemistry.ph_dose_ml(coordinator.settings.volume, current - target, product_dose)
    return {
        "current_ph": round(current, 2),
        "target_ph": round(target, 2),
        "dose_ml": round(dose),
        "product_dose": product_dose,
    }


async def _salt_correction(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    coordinator = _coordinator(hass, call)
    volume = coordinator.settings.volume
    current = call.data[ATTR_CURRENT_PPM]
    target = call.data[ATTR_TARGET_PPM]
    return {
        "current_ppm": current,
        "target_ppm": target,
        "salt_kg": round(chemistry.salt_correction_kg(volume, current, target), 2),
        "water_exchange_m3": round(chemistry.salt_dilution_m3(volume, current, target), 2),
    }


HANDLERS: dict[str, tuple[Any, SupportsResponse]] = {
    SERVICE_START_BOOST: (_start_boost, SupportsResponse.NONE),
    SERVICE_STOP_BOOST: (_stop_boost, SupportsResponse.NONE),
    SERVICE_TANK_REFILLED: (_tank_refilled, SupportsResponse.NONE),
    SERVICE_RESET_PH_LOCK: (_reset_ph_lock, SupportsResponse.NONE),
    SERVICE_RESET_SEASON: (_reset_season, SupportsResponse.NONE),
    SERVICE_PH_CORRECTION: (_ph_correction, SupportsResponse.ONLY),
    SERVICE_SALT_CORRECTION: (_salt_correction, SupportsResponse.ONLY),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration services."""
    for service, (handler, supports_response) in HANDLERS.items():

        async def _handle(call: ServiceCall, handler: Any = handler) -> ServiceResponse:
            return await handler(hass, call)

        hass.services.async_register(
            DOMAIN,
            service,
            _handle,
            schema=SCHEMAS[service],
            supports_response=supports_response,
        )
