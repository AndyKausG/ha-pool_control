"""Operating mode select for Pool Control."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import OperatingMode
from .coordinator import PoolConfigEntry, PoolCoordinator
from .entity import PoolEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the mode select."""
    async_add_entities([PoolModeSelect(entry.runtime_data)])


class PoolModeSelect(PoolEntity, SelectEntity):
    """Select for the operating mode."""

    def __init__(self, coordinator: PoolCoordinator) -> None:
        """Initialize the select."""
        super().__init__(coordinator, "mode")
        self._attr_options = [mode.value for mode in OperatingMode]

    @property
    def current_option(self) -> str:
        """Return the current mode."""
        return self.coordinator.state.mode

    async def async_select_option(self, option: str) -> None:
        """Change the operating mode."""
        await self.coordinator.async_set_runtime(mode=OperatingMode(option).value)
