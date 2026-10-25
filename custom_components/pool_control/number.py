"""Number entities for Pool Control set points."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PoolConfigEntry, PoolCoordinator
from .entity import PoolEntity

PPM = "ppm"


@dataclass(frozen=True, kw_only=True)
class PoolNumberDescription(NumberEntityDescription):
    """Describes a number bound to a runtime state attribute."""

    attribute: str
    requires_chlorinator: bool = False
    requires_ph_pump: bool = False


NUMBERS: tuple[PoolNumberDescription, ...] = (
    PoolNumberDescription(
        key="ph_target",
        attribute="ph_target",
        native_min_value=6.8,
        native_max_value=7.8,
        native_step=0.05,
        mode=NumberMode.BOX,
        requires_ph_pump=True,
    ),
    PoolNumberDescription(
        key="chlorine_target",
        attribute="chlorine_target",
        native_min_value=0.5,
        native_max_value=5.0,
        native_step=0.1,
        native_unit_of_measurement=PPM,
        mode=NumberMode.BOX,
        requires_chlorinator=True,
    ),
    PoolNumberDescription(
        key="boost_hours",
        attribute="boost_hours",
        native_min_value=0.5,
        native_max_value=24,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTime.HOURS,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator = entry.runtime_data
    settings = coordinator.settings
    async_add_entities(
        PoolNumber(coordinator, description)
        for description in NUMBERS
        if (settings.has_chlorinator or not description.requires_chlorinator)
        and (settings.has_ph_pump or not description.requires_ph_pump)
    )


class PoolNumber(PoolEntity, NumberEntity):
    """Number for a controller set point."""

    entity_description: PoolNumberDescription

    def __init__(self, coordinator: PoolCoordinator, description: PoolNumberDescription) -> None:
        """Initialize the number."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return float(getattr(self.coordinator.state, self.entity_description.attribute))

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        await self.coordinator.async_set_runtime(**{self.entity_description.attribute: value})
