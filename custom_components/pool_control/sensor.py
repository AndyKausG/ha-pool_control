"""Sensors for Pool Control."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MaintenanceTask, MeasurementSource, Status, SwimmingStatus
from .coordinator import PoolConfigEntry, PoolCoordinator
from .entity import PoolEntity

ML_PER_MIN = "mL/min"
ML_PER_10M3 = "mL/10 m³/0.1 pH"

type SensorValue = float | str | datetime | None


@dataclass(frozen=True, kw_only=True)
class PoolSensorDescription(SensorEntityDescription):
    """Describes a Pool Control sensor."""

    value_fn: Callable[[PoolCoordinator], SensorValue]
    attrs_fn: Callable[[PoolCoordinator], dict[str, Any]] | None = None
    requires_chlorinator: bool = False
    requires_ph_pump: bool = False


def _hours(seconds: float) -> float:
    return round(seconds / 3600, 2)


def _tank_percent(c: PoolCoordinator) -> float | None:
    level = c.state.tank_level_ml
    capacity = c.settings.tank_capacity_ml
    if level is None or capacity <= 0:
        return None
    return round(level / capacity * 100, 1)


SENSORS: tuple[PoolSensorDescription, ...] = (
    PoolSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in Status],
        value_fn=lambda c: c.data.status.value,
        attrs_fn=lambda c: {
            "pump_reason": c.data.pump_reason or None,
            "chlorinator_reason": c.data.chlorinator_reason or None,
            "ph_dosing_blocked_reason": c.data.ph_blocked_reason,
            "measurement_invalid_reason": c.data.measurement.invalid_reason,
            "problems": sorted(problem.value for problem in c.data.problems),
        },
    ),
    PoolSensorDescription(
        key="ph",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PH,
        suggested_display_precision=2,
        value_fn=lambda c: c.data.measurement.ph,
    ),
    PoolSensorDescription(
        key="orp",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda c: c.data.measurement.orp,
    ),
    PoolSensorDescription(
        key="water_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda c: c.data.measurement.temperature,
    ),
    PoolSensorDescription(
        key="measurement_source",
        device_class=SensorDeviceClass.ENUM,
        options=[source.value for source in MeasurementSource],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.data.measurement.source.value,
    ),
    PoolSensorDescription(
        key="orp_target",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=0,
        value_fn=lambda c: c.data.orp_target,
        requires_chlorinator=True,
    ),
    PoolSensorDescription(
        key="saturation_index",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda c: c.controller.saturation_index(c.data.measurement.ph, c.salt_ppm()),
    ),
    PoolSensorDescription(
        key="free_chlorine_test",
        native_unit_of_measurement="ppm",
        suggested_display_precision=1,
        value_fn=lambda c: c.state.free_chlorine,
        attrs_fn=lambda c: {"last_water_test": c.state.last_water_test},
    ),
    PoolSensorDescription(
        key="swimming_status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in SwimmingStatus],
        value_fn=lambda c: c.data.swimming.value,
    ),
    PoolSensorDescription(
        key="filtration_target",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        suggested_display_precision=1,
        value_fn=lambda c: c.data.filtration_target_h,
        attrs_fn=lambda c: {"reference_temperature": c.state.temp_mean_yesterday},
    ),
    PoolSensorDescription(
        key="pump_runtime_today",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda c: _hours(c.state.pump_runtime_today_s),
    ),
    PoolSensorDescription(
        key="next_filtration",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.data.next_filtration_start,
    ),
    PoolSensorDescription(
        key="chlorinator_runtime_today",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda c: _hours(c.state.chlorinator_runtime_today_s),
        requires_chlorinator=True,
    ),
    PoolSensorDescription(
        key="ph_dosed_today",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda c: round(c.state.ph_dosed_today_ml, 1),
        attrs_fn=lambda c: {"pulses": c.state.ph_pulses_today},
        requires_ph_pump=True,
    ),
    PoolSensorDescription(
        key="ph_dosed_season",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda c: round(c.state.ph_dosed_season_ml, 1),
        requires_ph_pump=True,
    ),
    PoolSensorDescription(
        key="ph_tank_level",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda c: (
            round(c.state.tank_level_ml, 0) if c.state.tank_level_ml is not None else None
        ),
        requires_ph_pump=True,
    ),
    PoolSensorDescription(
        key="ph_tank_level_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_tank_percent,
        requires_ph_pump=True,
    ),
    PoolSensorDescription(
        key="ph_pump_rate",
        native_unit_of_measurement=ML_PER_MIN,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda c: c.controller.ph_pump_rate,
        attrs_fn=lambda c: {
            "configured": c.settings.ph_pump_rate,
            "calibrated": c.state.ph_pump_rate_calibrated,
        },
        requires_ph_pump=True,
    ),
    PoolSensorDescription(
        key="ph_product_dose_learned",
        native_unit_of_measurement=ML_PER_10M3,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        value_fn=lambda c: c.state.ph_product_dose_learned,
        attrs_fn=lambda c: {"configured": c.settings.ph_product_dose},
        requires_ph_pump=True,
    ),
)


def _maintenance_sensor(task: MaintenanceTask) -> PoolSensorDescription:
    return PoolSensorDescription(
        key=f"maintenance_{task.value}",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.controller.maintenance_next(task),
        attrs_fn=lambda c: {"last_done": c.state.maintenance_done.get(task.value)},
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    settings = coordinator.settings
    descriptions = [
        description
        for description in SENSORS
        if (settings.has_chlorinator or not description.requires_chlorinator)
        and (settings.has_ph_pump or not description.requires_ph_pump)
    ]
    descriptions += [_maintenance_sensor(task) for task in settings.maintenance_days]
    async_add_entities(PoolSensor(coordinator, description) for description in descriptions)


class PoolSensor(PoolEntity, SensorEntity):
    """A Pool Control sensor."""

    entity_description: PoolSensorDescription

    def __init__(self, coordinator: PoolCoordinator, description: PoolSensorDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> SensorValue:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator)
