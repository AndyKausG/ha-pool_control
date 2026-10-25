"""Data models shared by the controller, coordinator and entities."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime, time
from typing import Any

from .const import (
    CONF_BACKUP_MAX_AGE,
    CONF_BLOCKS,
    CONF_CHLOR_MAX_DAILY,
    CONF_CHLOR_MIN_OFF,
    CONF_CHLOR_MIN_ON,
    CONF_CHLOR_NO_EFFECT,
    CONF_CHLORINATOR,
    CONF_DEMAND_EXTENSION,
    CONF_FROST_MODE,
    CONF_FROST_ON_MINUTES,
    CONF_FROST_TEMP,
    CONF_MAX_AGE,
    CONF_ORP_FIXED_TARGET,
    CONF_ORP_HOLDOFF,
    CONF_ORP_HYSTERESIS,
    CONF_ORP_MODE,
    CONF_PH_DEADBAND,
    CONF_PH_DOSING_MODE,
    CONF_PH_LOCKOUT,
    CONF_PH_MAX_DAILY,
    CONF_PH_MAX_HOURLY,
    CONF_PH_MIN_SAFE,
    CONF_PH_NO_EFFECT,
    CONF_PH_PRODUCT_DOSE,
    CONF_PH_PULSE,
    CONF_PH_PUMP,
    CONF_PH_PUMP_RATE,
    CONF_PH_QUIET_END,
    CONF_PH_QUIET_START,
    CONF_RUNTIME_DIVISOR,
    CONF_RUNTIME_MAX,
    CONF_RUNTIME_MIN,
    CONF_SALT_MAX,
    CONF_SALT_MIN,
    CONF_STABILIZATION,
    CONF_STUCK_MINUTES,
    CONF_SWIM_DATA_MAX_AGE,
    CONF_SWIM_ORP_MIN,
    CONF_SWIM_PH_MAX,
    CONF_SWIM_PH_MIN,
    CONF_TANK_CAPACITY,
    CONF_TANK_WARN,
    CONF_VOLUME,
    CONF_WINDOW_END,
    CONF_WINDOW_START,
    DEFAULT_BOOST_HOURS,
    DEFAULT_CHLORINE_TARGET,
    DEFAULT_PH_TARGET,
    DEFAULTS,
    FrostMode,
    MeasurementSource,
    OperatingMode,
    OrpTargetMode,
    PhDosingMode,
    Problem,
    Status,
    SwimmingStatus,
)


def parse_time(value: str | time) -> time:
    """Parse a HH:MM[:SS] string into a time object."""
    if isinstance(value, time):
        return value
    parts = [int(part) for part in str(value).split(":")]
    while len(parts) < 3:
        parts.append(0)
    return time(parts[0], parts[1], parts[2])


@dataclass(frozen=True, slots=True)
class Settings:
    """Static controller configuration (from the config entry options)."""

    volume: float
    has_chlorinator: bool
    has_ph_pump: bool
    window_start: time
    window_end: time
    blocks: int
    runtime_divisor: float
    runtime_min: float
    runtime_max: float
    demand_extension: bool
    stabilization_min: float
    max_age_min: float
    stuck_min: float
    backup_max_age_min: float
    orp_mode: OrpTargetMode
    orp_fixed_target: float
    orp_hysteresis: float
    chlor_min_on_min: float
    chlor_min_off_min: float
    chlor_max_daily_h: float
    chlor_no_effect_h: float
    orp_holdoff_min: float
    salt_min: float
    salt_max: float
    ph_deadband: float
    ph_dosing_mode: PhDosingMode
    ph_pulse_s: float
    ph_lockout_min: float
    ph_pump_rate: float
    ph_product_dose: float
    ph_max_daily_ml: float
    ph_max_hourly_ml: float
    ph_min_safe: float
    ph_quiet_start: time
    ph_quiet_end: time
    ph_no_effect_drop: float
    tank_capacity_ml: float
    tank_warn_ml: float
    frost_temp: float
    frost_mode: FrostMode
    frost_on_min: float
    swim_ph_min: float
    swim_ph_max: float
    swim_orp_min: float
    swim_data_max_age_h: float

    @classmethod
    def from_options(cls, options: dict[str, Any]) -> Settings:
        """Build settings from config entry options, filling in defaults."""
        merged: dict[str, Any] = {**DEFAULTS, **options}

        def num(key: str) -> float:
            return float(merged[key])

        return cls(
            volume=num(CONF_VOLUME),
            has_chlorinator=bool(merged.get(CONF_CHLORINATOR)),
            has_ph_pump=bool(merged.get(CONF_PH_PUMP)),
            window_start=parse_time(merged[CONF_WINDOW_START]),
            window_end=parse_time(merged[CONF_WINDOW_END]),
            blocks=max(1, int(merged[CONF_BLOCKS])),
            runtime_divisor=num(CONF_RUNTIME_DIVISOR),
            runtime_min=num(CONF_RUNTIME_MIN),
            runtime_max=num(CONF_RUNTIME_MAX),
            demand_extension=bool(merged[CONF_DEMAND_EXTENSION]),
            stabilization_min=num(CONF_STABILIZATION),
            max_age_min=num(CONF_MAX_AGE),
            stuck_min=num(CONF_STUCK_MINUTES),
            backup_max_age_min=num(CONF_BACKUP_MAX_AGE),
            orp_mode=OrpTargetMode(merged[CONF_ORP_MODE]),
            orp_fixed_target=num(CONF_ORP_FIXED_TARGET),
            orp_hysteresis=num(CONF_ORP_HYSTERESIS),
            chlor_min_on_min=num(CONF_CHLOR_MIN_ON),
            chlor_min_off_min=num(CONF_CHLOR_MIN_OFF),
            chlor_max_daily_h=num(CONF_CHLOR_MAX_DAILY),
            chlor_no_effect_h=num(CONF_CHLOR_NO_EFFECT),
            orp_holdoff_min=num(CONF_ORP_HOLDOFF),
            salt_min=num(CONF_SALT_MIN),
            salt_max=num(CONF_SALT_MAX),
            ph_deadband=num(CONF_PH_DEADBAND),
            ph_dosing_mode=PhDosingMode(merged[CONF_PH_DOSING_MODE]),
            ph_pulse_s=num(CONF_PH_PULSE),
            ph_lockout_min=num(CONF_PH_LOCKOUT),
            ph_pump_rate=num(CONF_PH_PUMP_RATE),
            ph_product_dose=num(CONF_PH_PRODUCT_DOSE),
            ph_max_daily_ml=num(CONF_PH_MAX_DAILY),
            ph_max_hourly_ml=num(CONF_PH_MAX_HOURLY),
            ph_min_safe=num(CONF_PH_MIN_SAFE),
            ph_quiet_start=parse_time(merged[CONF_PH_QUIET_START]),
            ph_quiet_end=parse_time(merged[CONF_PH_QUIET_END]),
            ph_no_effect_drop=num(CONF_PH_NO_EFFECT),
            tank_capacity_ml=num(CONF_TANK_CAPACITY),
            tank_warn_ml=num(CONF_TANK_WARN),
            frost_temp=num(CONF_FROST_TEMP),
            frost_mode=FrostMode(merged[CONF_FROST_MODE]),
            frost_on_min=num(CONF_FROST_ON_MINUTES),
            swim_ph_min=num(CONF_SWIM_PH_MIN),
            swim_ph_max=num(CONF_SWIM_PH_MAX),
            swim_orp_min=num(CONF_SWIM_ORP_MIN),
            swim_data_max_age_h=num(CONF_SWIM_DATA_MAX_AGE),
        )


@dataclass(frozen=True, slots=True)
class Reading:
    """A raw sensor reading taken from the state machine."""

    value: float | None
    last_reported: datetime | None = None
    last_changed: datetime | None = None


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Inputs for one controller step."""

    now: datetime
    pump_on: bool
    chlorinator_on: bool
    ph_pump_on: bool
    ph: Reading
    orp: Reading
    temperature: Reading
    backup_ph: Reading = field(default_factory=lambda: Reading(None))
    backup_orp: Reading = field(default_factory=lambda: Reading(None))
    backup_temperature: Reading = field(default_factory=lambda: Reading(None))
    salt: Reading = field(default_factory=lambda: Reading(None))
    outdoor_temperature: float | None = None
    outdoor_configured: bool = False
    flow_ok: bool | None = None


def _dt_to_str(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _dt_from_str(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


_DATETIME_FIELDS = {
    "pump_on_since",
    "pump_off_since",
    "chlorinator_on_since",
    "chlorinator_off_since",
    "ph_lockout_until",
    "last_ph_pulse",
    "boost_until",
    "last_valid_measurement",
    "ph_session_last_pulse",
    "last_accumulated",
}


@dataclass(slots=True)
class RuntimeState:
    """Persistent controller state."""

    # User settings exposed as entities
    mode: str = OperatingMode.AUTO.value
    dry_run: bool = False
    ph_control_enabled: bool = True
    chlorine_control_enabled: bool = True
    ph_target: float = DEFAULT_PH_TARGET
    chlorine_target: float = DEFAULT_CHLORINE_TARGET
    boost_hours: float = DEFAULT_BOOST_HOURS

    # Daily counters
    day: str | None = None
    pump_runtime_today_s: float = 0.0
    chlorinator_runtime_today_s: float = 0.0
    ph_dosed_today_ml: float = 0.0
    ph_pulses_today: int = 0
    temp_sum_today: float = 0.0
    temp_count_today: int = 0
    temp_mean_yesterday: float | None = None
    last_accumulated: datetime | None = None

    # Switch tracking
    pump_on_since: datetime | None = None
    pump_off_since: datetime | None = None
    pump_owned: bool = False
    chlorinator_on_since: datetime | None = None
    chlorinator_off_since: datetime | None = None
    chlorinator_start_orp: float | None = None

    # Measurement
    last_valid_measurement: datetime | None = None
    last_valid_ph: float | None = None
    last_valid_orp: float | None = None
    last_valid_temperature: float | None = None

    # pH dosing
    ph_lockout_until: datetime | None = None
    last_ph_pulse: datetime | None = None
    ph_dosed_season_ml: float = 0.0
    ph_dose_log: list[tuple[str, float]] = field(default_factory=list)
    ph_session_start_ph: float | None = None
    ph_session_ml: float = 0.0
    ph_session_last_pulse: datetime | None = None
    ph_dosing_locked: bool = False
    ph_product_dose_learned: float | None = None
    tank_level_ml: float | None = None
    ph_pump_seconds_since_refill: float = 0.0
    ph_pump_rate_calibrated: float | None = None

    # Misc
    boost_until: datetime | None = None
    frost_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        data = asdict(self)
        for key in _DATETIME_FIELDS:
            data[key] = _dt_to_str(data[key])
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeState:
        """Deserialize from storage, ignoring unknown keys."""
        known = {f.name for f in fields(cls)}
        values = {key: value for key, value in data.items() if key in known}
        for key in _DATETIME_FIELDS & values.keys():
            values[key] = _dt_from_str(values[key])
        return cls(**values)

    @property
    def operating_mode(self) -> OperatingMode:
        """Return the operating mode as enum."""
        return OperatingMode(self.mode)

    def current_day(self) -> date | None:
        """Return the day the daily counters belong to."""
        return date.fromisoformat(self.day) if self.day else None


@dataclass(slots=True)
class Measurement:
    """Evaluated measurement used by the controller and the entities."""

    source: MeasurementSource = MeasurementSource.NONE
    ph: float | None = None
    orp: float | None = None
    temperature: float | None = None
    primary_valid: bool = False
    invalid_reason: str | None = None


@dataclass(slots=True)
class Decision:
    """Result of one controller step."""

    status: Status = Status.IDLE
    measurement: Measurement = field(default_factory=Measurement)
    pump: bool | None = None
    pump_reason: str = ""
    chlorinator: bool | None = None
    chlorinator_reason: str = ""
    ph_pulse_seconds: float = 0.0
    ph_pump_stop: bool = False
    ph_pulse_reason: str = ""
    ph_blocked_reason: str | None = None
    orp_target: float | None = None
    filtration_target_h: float = 0.0
    next_filtration_start: datetime | None = None
    swimming: SwimmingStatus = SwimmingStatus.NO_DATA
    problems: set[Problem] = field(default_factory=set)
