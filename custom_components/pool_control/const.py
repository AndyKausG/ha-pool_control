"""Constants for the Pool Control integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

DOMAIN: Final = "pool_control"
EVENT_POOL_CONTROL: Final = f"{DOMAIN}_event"

STORAGE_VERSION: Final = 1
UPDATE_INTERVAL_SECONDS: Final = 60

# --- Config keys: actuators -------------------------------------------------
CONF_PUMP: Final = "pump"
CONF_CHLORINATOR: Final = "chlorinator"
CONF_PH_PUMP: Final = "ph_pump"

# --- Config keys: sensors ---------------------------------------------------
CONF_PH_SENSOR: Final = "ph_sensor"
CONF_ORP_SENSOR: Final = "orp_sensor"
CONF_TEMP_SENSOR: Final = "temperature_sensor"
CONF_BACKUP_PH_SENSOR: Final = "backup_ph_sensor"
CONF_BACKUP_ORP_SENSOR: Final = "backup_orp_sensor"
CONF_BACKUP_TEMP_SENSOR: Final = "backup_temperature_sensor"
CONF_SALT_SENSOR: Final = "salt_sensor"
CONF_WEATHER: Final = "weather"
CONF_OUTDOOR_TEMP_SENSOR: Final = "outdoor_temperature_sensor"
CONF_FLOW_SENSOR: Final = "flow_sensor"
CONF_PUMP_POWER_SENSOR: Final = "pump_power_sensor"
CONF_SOLAR_PUMP: Final = "solar_pump"
CONF_SOLAR_COLLECTOR_SENSOR: Final = "solar_collector_sensor"
CONF_SOLAR_DEMAND_SENSOR: Final = "solar_demand_sensor"
CONF_PV_SURPLUS_SENSOR: Final = "pv_surplus_sensor"

# --- Config keys: pool ------------------------------------------------------
CONF_VOLUME: Final = "volume"

# --- Config keys: filtration ------------------------------------------------
CONF_WINDOW_START: Final = "filtration_window_start"
CONF_WINDOW_END: Final = "filtration_window_end"
CONF_BLOCKS: Final = "filtration_blocks"
CONF_RUNTIME_DIVISOR: Final = "runtime_divisor"
CONF_RUNTIME_MIN: Final = "runtime_min_hours"
CONF_RUNTIME_MAX: Final = "runtime_max_hours"
CONF_DEMAND_EXTENSION: Final = "demand_extension"
CONF_PUMP_MIN_POWER: Final = "pump_min_power"

# --- Config keys: measurement -----------------------------------------------
CONF_STABILIZATION: Final = "stabilization_minutes"
CONF_MAX_AGE: Final = "sensor_max_age_minutes"
CONF_STUCK_MINUTES: Final = "stuck_detection_minutes"
CONF_BACKUP_MAX_AGE: Final = "backup_max_age_minutes"

# --- Config keys: chlorination ----------------------------------------------
CONF_ORP_MODE: Final = "orp_target_mode"
CONF_ORP_FIXED_TARGET: Final = "orp_fixed_target"
CONF_ORP_HYSTERESIS: Final = "orp_hysteresis"
CONF_CHLOR_MIN_ON: Final = "chlorinator_min_on_minutes"
CONF_CHLOR_MIN_OFF: Final = "chlorinator_min_off_minutes"
CONF_CHLOR_MAX_DAILY: Final = "chlorinator_max_daily_hours"
CONF_CHLOR_NO_EFFECT: Final = "chlorinator_no_effect_hours"
CONF_ORP_HOLDOFF: Final = "orp_holdoff_after_dosing_minutes"
CONF_SALT_MIN: Final = "salt_min"
CONF_SALT_MAX: Final = "salt_max"

# --- Config keys: pH dosing -------------------------------------------------
CONF_PH_DEADBAND: Final = "ph_deadband"
CONF_PH_DOSING_MODE: Final = "ph_dosing_mode"
CONF_PH_PULSE: Final = "ph_pulse_seconds"
CONF_PH_PUMP_AUTO_OFF: Final = "ph_pump_auto_off_seconds"
CONF_PH_LOCKOUT: Final = "ph_lockout_minutes"
CONF_PH_PUMP_RATE: Final = "ph_pump_rate"
CONF_PH_PRODUCT_DOSE: Final = "ph_product_dose"
CONF_PH_MAX_DAILY: Final = "ph_max_daily_ml"
CONF_PH_MAX_HOURLY: Final = "ph_max_hourly_ml"
CONF_PH_MIN_SAFE: Final = "ph_min_safe"
CONF_PH_QUIET_START: Final = "ph_quiet_start"
CONF_PH_QUIET_END: Final = "ph_quiet_end"
CONF_PH_NO_EFFECT: Final = "ph_no_effect_expected_drop"
CONF_TANK_CAPACITY: Final = "tank_capacity_ml"
CONF_TANK_WARN: Final = "tank_warning_ml"

# --- Config keys: frost and swimming ----------------------------------------
CONF_FROST_TEMP: Final = "frost_temperature"
CONF_FROST_MODE: Final = "frost_mode"
CONF_FROST_ON_MINUTES: Final = "frost_on_minutes"
CONF_SWIM_PH_MIN: Final = "swim_ph_min"
CONF_SWIM_PH_MAX: Final = "swim_ph_max"
CONF_SWIM_ORP_MIN: Final = "swim_orp_min"
CONF_SWIM_DATA_MAX_AGE: Final = "swim_data_max_age_hours"


# --- Config keys: solar and PV ----------------------------------------------
CONF_SOLAR_DELTA_ON: Final = "solar_delta_on"
CONF_SOLAR_DELTA_OFF: Final = "solar_delta_off"
CONF_SOLAR_MAX_TEMP: Final = "solar_max_water_temperature"
CONF_SOLAR_MIN_SWITCH: Final = "solar_min_switch_minutes"
CONF_SOLAR_NEEDS_FILTER: Final = "solar_requires_filter_pump"
CONF_PV_MIN_SURPLUS: Final = "pv_min_surplus"
CONF_PV_MIN_RUN: Final = "pv_min_run_minutes"
CONF_PV_START_DELAY: Final = "pv_start_delay_minutes"

# --- Config keys: maintenance ----------------------------------------------
CONF_MAINT_PH_CAL: Final = "maintenance_ph_calibration_days"
CONF_MAINT_ORP_CAL: Final = "maintenance_orp_calibration_days"
CONF_MAINT_BACKWASH: Final = "maintenance_backwash_days"
CONF_MAINT_CELL: Final = "maintenance_cell_cleaning_days"


class MaintenanceTask(StrEnum):
    """Recurring maintenance tasks."""

    PH_CALIBRATION = "ph_calibration"
    ORP_CALIBRATION = "orp_calibration"
    BACKWASH = "backwash"
    CELL_CLEANING = "cell_cleaning"


MAINTENANCE_OPTIONS: Final = {
    MaintenanceTask.PH_CALIBRATION: CONF_MAINT_PH_CAL,
    MaintenanceTask.ORP_CALIBRATION: CONF_MAINT_ORP_CAL,
    MaintenanceTask.BACKWASH: CONF_MAINT_BACKWASH,
    MaintenanceTask.CELL_CLEANING: CONF_MAINT_CELL,
}


class SolarMode(StrEnum):
    """How solar heating is controlled."""

    NONE = "none"
    DIFFERENTIAL = "differential"
    EXTERNAL = "external"


class OperatingMode(StrEnum):
    """Operating mode selected by the user."""

    AUTO = "auto"
    MANUAL = "manual"
    MAINTENANCE = "maintenance"
    WINTER = "winter"
    OFF = "off"


class OrpTargetMode(StrEnum):
    """How the ORP set point is determined."""

    PH_COMPENSATED = "ph_compensated"
    FIXED = "fixed"


class PhDosingMode(StrEnum):
    """How the length of a pH dosing pulse is determined."""

    FIXED = "fixed"
    PROPORTIONAL = "proportional"


class FrostMode(StrEnum):
    """How the pump runs while frost protection is active."""

    INTERVAL = "interval"
    CONTINUOUS = "continuous"


class Status(StrEnum):
    """Overall controller status."""

    OFF = "off"
    WINTER = "winter"
    MAINTENANCE = "maintenance"
    FROST_PROTECTION = "frost_protection"
    DOSING = "dosing"
    CHLORINATING = "chlorinating"
    STABILIZING = "stabilizing"
    FILTERING = "filtering"
    IDLE = "idle"


class MeasurementSource(StrEnum):
    """Which sensor set currently provides valid readings."""

    PRIMARY = "primary"
    BACKUP = "backup"
    NONE = "none"


class SwimmingStatus(StrEnum):
    """Result of the swimming assessment."""

    OK = "ok"
    PH_LOW = "ph_low"
    PH_HIGH = "ph_high"
    ORP_LOW = "orp_low"
    DOSING = "dosing"
    SHOCK = "shock"
    NO_DATA = "no_data"


class Problem(StrEnum):
    """Problems reported by the controller."""

    NO_FLOW = "no_flow"
    SENSOR_STUCK = "sensor_stuck"
    SENSOR_DEVIATION = "sensor_deviation"
    WATER_QUALITY = "water_quality"
    PH_TOO_LOW = "ph_too_low"
    PH_DOSING_LOCKED = "ph_dosing_locked"
    PH_DAILY_LIMIT = "ph_daily_limit"
    PH_TANK_LOW = "ph_tank_low"
    PH_TANK_EMPTY = "ph_tank_empty"
    CHLORINATOR_NO_EFFECT = "chlorinator_no_effect"
    CHLORINATOR_DAILY_LIMIT = "chlorinator_daily_limit"
    SALT_LOW = "salt_low"
    SALT_HIGH = "salt_high"
    OUTDOOR_TEMP_UNAVAILABLE = "outdoor_temperature_unavailable"


# Plausibility limits for raw sensor values.
PH_PLAUSIBLE: Final = (4.0, 9.0)
ORP_PLAUSIBLE: Final = (200.0, 1000.0)
TEMP_PLAUSIBLE: Final = (-5.0, 45.0)

# Water quality alarm limits (independent of the set points).
ALARM_PH_MIN: Final = 6.8
ALARM_PH_MAX: Final = 8.2
ALARM_ORP_MIN: Final = 500.0

# Maximum deviation between primary and backup sensors.
DEVIATION_PH: Final = 0.3
DEVIATION_ORP: Final = 100.0

# Fixed controller constants.
PUMP_MIN_START_MINUTES: Final = 15
CHLOR_NO_EFFECT_MIN_RISE_MV: Final = 10.0
PH_SUCCESS_MIN_DROP: Final = 0.03
FROST_HYSTERESIS: Final = 1.0
SWIM_DOSING_BLOCK_MINUTES: Final = 30
SALT_MAX_AGE_HOURS: Final = 48
FALLBACK_WATER_TEMP: Final = 20.0

DEFAULT_NAME: Final = "Pool"

DEFAULTS: Final[dict[str, object]] = {
    CONF_VOLUME: 17.2,
    # Filtration
    CONF_WINDOW_START: "08:00:00",
    CONF_WINDOW_END: "22:00:00",
    CONF_BLOCKS: 2,
    CONF_RUNTIME_DIVISOR: 2.0,
    CONF_RUNTIME_MIN: 2.0,
    CONF_RUNTIME_MAX: 12.0,
    CONF_DEMAND_EXTENSION: True,
    CONF_PUMP_MIN_POWER: 20.0,
    # Measurement
    CONF_STABILIZATION: 30,
    CONF_MAX_AGE: 5,
    CONF_STUCK_MINUTES: 60,
    CONF_BACKUP_MAX_AGE: 120,
    # Chlorination
    CONF_ORP_MODE: OrpTargetMode.PH_COMPENSATED.value,
    CONF_ORP_FIXED_TARGET: 735,
    CONF_ORP_HYSTERESIS: 15,
    CONF_CHLOR_MIN_ON: 30,
    CONF_CHLOR_MIN_OFF: 15,
    CONF_CHLOR_MAX_DAILY: 12.0,
    CONF_CHLOR_NO_EFFECT: 3.0,
    CONF_ORP_HOLDOFF: 15,
    CONF_SALT_MIN: 2500,
    CONF_SALT_MAX: 4500,
    # pH dosing
    CONF_PH_DEADBAND: 0.05,
    CONF_PH_DOSING_MODE: PhDosingMode.FIXED.value,
    CONF_PH_PULSE: 50,
    CONF_PH_PUMP_AUTO_OFF: 60,
    CONF_PH_LOCKOUT: 10,
    CONF_PH_PUMP_RATE: 21.0,
    CONF_PH_PRODUCT_DOSE: 300.0,
    CONF_PH_MAX_DAILY: 1500,
    CONF_PH_MAX_HOURLY: 300,
    CONF_PH_MIN_SAFE: 6.8,
    CONF_PH_QUIET_START: "22:00:00",
    CONF_PH_QUIET_END: "07:00:00",
    CONF_PH_NO_EFFECT: 0.15,
    CONF_TANK_CAPACITY: 5000,
    CONF_TANK_WARN: 500,
    # Frost and swimming
    CONF_FROST_TEMP: 2.0,
    CONF_FROST_MODE: FrostMode.INTERVAL.value,
    CONF_FROST_ON_MINUTES: 15,
    CONF_SWIM_PH_MIN: 7.0,
    CONF_SWIM_PH_MAX: 7.8,
    CONF_SWIM_ORP_MIN: 650,
    CONF_SWIM_DATA_MAX_AGE: 6,
    # Solar and PV
    CONF_SOLAR_DELTA_ON: 6.0,
    CONF_SOLAR_DELTA_OFF: 3.0,
    CONF_SOLAR_MAX_TEMP: 30.0,
    CONF_SOLAR_MIN_SWITCH: 10,
    CONF_SOLAR_NEEDS_FILTER: False,
    CONF_PV_MIN_SURPLUS: 300,
    CONF_PV_MIN_RUN: 60,
    CONF_PV_START_DELAY: 10,
    # Maintenance intervals in days, 0 disables the reminder
    CONF_MAINT_PH_CAL: 90,
    CONF_MAINT_ORP_CAL: 90,
    CONF_MAINT_BACKWASH: 14,
    CONF_MAINT_CELL: 90,
}

# Runtime settings exposed as entities, persisted in the store.
DEFAULT_PH_TARGET: Final = 7.2
DEFAULT_CHLORINE_TARGET: Final = 2.0
DEFAULT_BOOST_HOURS: Final = 2.0
DEFAULT_SHOCK_TARGET: Final = 5.0
DEFAULT_SHOCK_HOURS: Final = 24.0
DEFAULT_TDS: Final = 1000.0
STABILIZER_WARNING_PPM: Final = 20.0
