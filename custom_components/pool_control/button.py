"""Buttons for Pool Control."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PoolConfigEntry, PoolCoordinator
from .entity import PoolEntity


@dataclass(frozen=True, kw_only=True)
class PoolButtonDescription(ButtonEntityDescription):
    """Describes a Pool Control button."""

    press_fn: Callable[[PoolCoordinator], Awaitable[None]]
    requires_ph_pump: bool = False
    requires_chlorinator: bool = False


BUTTONS: tuple[PoolButtonDescription, ...] = (
    PoolButtonDescription(
        key="start_boost",
        press_fn=lambda c: c.async_start_boost(),
    ),
    PoolButtonDescription(
        key="stop_boost",
        press_fn=lambda c: c.async_stop_boost(),
    ),
    PoolButtonDescription(
        key="start_shock",
        press_fn=lambda c: c.async_start_shock(),
        requires_chlorinator=True,
    ),
    PoolButtonDescription(
        key="stop_shock",
        press_fn=lambda c: c.async_stop_shock(),
        requires_chlorinator=True,
    ),
    PoolButtonDescription(
        key="ph_tank_refilled",
        press_fn=lambda c: c.async_tank_refilled(),
        requires_ph_pump=True,
    ),
    PoolButtonDescription(
        key="ph_manual_pulse",
        press_fn=lambda c: c.async_manual_ph_pulse(),
        requires_ph_pump=True,
    ),
    PoolButtonDescription(
        key="ph_reset_lock",
        press_fn=lambda c: c.async_reset_ph_lock(),
        requires_ph_pump=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        PoolButton(coordinator, description)
        for description in BUTTONS
        if (coordinator.settings.has_ph_pump or not description.requires_ph_pump)
        and (coordinator.settings.has_chlorinator or not description.requires_chlorinator)
    )


class PoolButton(PoolEntity, ButtonEntity):
    """A Pool Control button."""

    entity_description: PoolButtonDescription

    def __init__(self, coordinator: PoolCoordinator, description: PoolButtonDescription) -> None:
        """Initialize the button."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self.coordinator)
