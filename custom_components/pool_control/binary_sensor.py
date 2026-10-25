"""Binary sensors for Pool Control."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import Problem, SwimmingStatus
from .coordinator import PoolConfigEntry, PoolCoordinator
from .entity import PoolEntity


@dataclass(frozen=True, kw_only=True)
class PoolBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a Pool Control binary sensor."""

    is_on_fn: Callable[[PoolCoordinator], bool]
    attrs_fn: Callable[[PoolCoordinator], dict[str, Any]] | None = None
    requires_ph_pump: bool = False


BINARY_SENSORS: tuple[PoolBinarySensorDescription, ...] = (
    PoolBinarySensorDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda c: bool(c.data.problems),
        attrs_fn=lambda c: {"problems": sorted(p.value for p in c.data.problems)},
    ),
    PoolBinarySensorDescription(
        key="swimming_allowed",
        is_on_fn=lambda c: c.data.swimming is SwimmingStatus.OK,
    ),
    PoolBinarySensorDescription(
        key="measurement_valid",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda c: c.data.measurement.primary_valid,
        attrs_fn=lambda c: {"reason": c.data.measurement.invalid_reason},
    ),
    PoolBinarySensorDescription(
        key="frost_protection",
        device_class=BinarySensorDeviceClass.COLD,
        is_on_fn=lambda c: c.state.frost_active,
    ),
    PoolBinarySensorDescription(
        key="ph_dosing_locked",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda c: c.state.ph_dosing_locked,
        requires_ph_pump=True,
    ),
    PoolBinarySensorDescription(
        key="ph_tank_low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda c: bool({Problem.PH_TANK_LOW, Problem.PH_TANK_EMPTY} & c.data.problems),
        requires_ph_pump=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        PoolBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if coordinator.settings.has_ph_pump or not description.requires_ph_pump
    )


class PoolBinarySensor(PoolEntity, BinarySensorEntity):
    """A Pool Control binary sensor."""

    entity_description: PoolBinarySensorDescription

    def __init__(
        self, coordinator: PoolCoordinator, description: PoolBinarySensorDescription
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return self.entity_description.is_on_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator)
