"""Base entity for Pool Control."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PoolCoordinator


class PoolEntity(CoordinatorEntity[PoolCoordinator]):
    """Common base for all Pool Control entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PoolCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Pool Control",
            model="Pool controller",
        )
