"""Switches for Pool Control settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SolarMode
from .coordinator import PoolConfigEntry, PoolCoordinator
from .entity import PoolEntity


@dataclass(frozen=True, kw_only=True)
class PoolSwitchDescription(SwitchEntityDescription):
    """Describes a switch bound to a runtime state attribute."""

    attribute: str
    requires_chlorinator: bool = False
    requires_ph_pump: bool = False
    requires_solar: bool = False


SWITCHES: tuple[PoolSwitchDescription, ...] = (
    PoolSwitchDescription(
        key="dry_run",
        attribute="dry_run",
        entity_category=EntityCategory.CONFIG,
    ),
    PoolSwitchDescription(
        key="chlorine_control",
        attribute="chlorine_control_enabled",
        entity_category=EntityCategory.CONFIG,
        requires_chlorinator=True,
    ),
    PoolSwitchDescription(
        key="solar_control",
        attribute="solar_enabled",
        entity_category=EntityCategory.CONFIG,
        requires_solar=True,
    ),
    PoolSwitchDescription(
        key="ph_control",
        attribute="ph_control_enabled",
        entity_category=EntityCategory.CONFIG,
        requires_ph_pump=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    coordinator = entry.runtime_data
    settings = coordinator.settings
    async_add_entities(
        PoolSwitch(coordinator, description)
        for description in SWITCHES
        if (settings.has_chlorinator or not description.requires_chlorinator)
        and (settings.has_ph_pump or not description.requires_ph_pump)
        and (settings.solar_mode is not SolarMode.NONE or not description.requires_solar)
    )


class PoolSwitch(PoolEntity, SwitchEntity):
    """Switch for a boolean controller setting."""

    entity_description: PoolSwitchDescription

    def __init__(self, coordinator: PoolCoordinator, description: PoolSwitchDescription) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return bool(getattr(self.coordinator.state, self.entity_description.attribute))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the setting."""
        await self.coordinator.async_set_runtime(**{self.entity_description.attribute: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the setting."""
        await self.coordinator.async_set_runtime(**{self.entity_description.attribute: False})
