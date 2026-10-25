"""Config and options flow for Pool Control."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    CONF_BACKUP_MAX_AGE,
    CONF_BACKUP_ORP_SENSOR,
    CONF_BACKUP_PH_SENSOR,
    CONF_BACKUP_TEMP_SENSOR,
    CONF_BLOCKS,
    CONF_CHLOR_MAX_DAILY,
    CONF_CHLOR_MIN_OFF,
    CONF_CHLOR_MIN_ON,
    CONF_CHLOR_NO_EFFECT,
    CONF_CHLORINATOR,
    CONF_DEMAND_EXTENSION,
    CONF_FLOW_SENSOR,
    CONF_FROST_MODE,
    CONF_FROST_ON_MINUTES,
    CONF_FROST_TEMP,
    CONF_MAX_AGE,
    CONF_ORP_FIXED_TARGET,
    CONF_ORP_HOLDOFF,
    CONF_ORP_HYSTERESIS,
    CONF_ORP_MODE,
    CONF_ORP_SENSOR,
    CONF_OUTDOOR_TEMP_SENSOR,
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
    CONF_PH_PUMP_AUTO_OFF,
    CONF_PH_PUMP_RATE,
    CONF_PH_QUIET_END,
    CONF_PH_QUIET_START,
    CONF_PH_SENSOR,
    CONF_PUMP,
    CONF_PUMP_MIN_POWER,
    CONF_PUMP_POWER_SENSOR,
    CONF_RUNTIME_DIVISOR,
    CONF_RUNTIME_MAX,
    CONF_RUNTIME_MIN,
    CONF_SALT_MAX,
    CONF_SALT_MIN,
    CONF_SALT_SENSOR,
    CONF_STABILIZATION,
    CONF_STUCK_MINUTES,
    CONF_SWIM_DATA_MAX_AGE,
    CONF_SWIM_ORP_MIN,
    CONF_SWIM_PH_MAX,
    CONF_SWIM_PH_MIN,
    CONF_TANK_CAPACITY,
    CONF_TANK_WARN,
    CONF_TEMP_SENSOR,
    CONF_VOLUME,
    CONF_WEATHER,
    CONF_WINDOW_END,
    CONF_WINDOW_START,
    DEFAULT_NAME,
    DEFAULTS,
    DOMAIN,
    MAINTENANCE_OPTIONS,
    FrostMode,
    OrpTargetMode,
    PhDosingMode,
)
from .models import parse_time

SWITCH_DOMAINS = ["switch", "input_boolean", "light"]

PH_PULSE_MARGIN_SECONDS = 5


def _entity(domains: list[str], device_class: str | None = None) -> selector.EntitySelector:
    config = selector.EntitySelectorConfig(domain=domains)
    if device_class is not None:
        config = selector.EntitySelectorConfig(domain=domains, device_class=device_class)
    return selector.EntitySelector(config)


def _number(
    minimum: float, maximum: float, step: float, unit: str | None = None
) -> selector.NumberSelector:
    config = selector.NumberSelectorConfig(
        min=minimum, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX
    )
    if unit is not None:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


def _choice(options: list[str], key: str) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(options=options, translation_key=key)
    )


TIME = selector.TimeSelector()
BOOLEAN = selector.BooleanSelector()
MINUTES = UnitOfTime.MINUTES
HOURS = UnitOfTime.HOURS
SECONDS = UnitOfTime.SECONDS

# (key, selector, required)
ACTUATOR_FIELDS: list[tuple[str, Any, bool]] = [
    (CONF_PUMP, _entity(SWITCH_DOMAINS), True),
    (CONF_CHLORINATOR, _entity(SWITCH_DOMAINS), False),
    (CONF_PH_PUMP, _entity(SWITCH_DOMAINS), False),
]
SENSOR_FIELDS: list[tuple[str, Any, bool]] = [
    (CONF_PH_SENSOR, _entity(["sensor"]), True),
    (CONF_ORP_SENSOR, _entity(["sensor"]), True),
    (CONF_TEMP_SENSOR, _entity(["sensor"]), True),
    (CONF_BACKUP_PH_SENSOR, _entity(["sensor"]), False),
    (CONF_BACKUP_ORP_SENSOR, _entity(["sensor"]), False),
    (CONF_BACKUP_TEMP_SENSOR, _entity(["sensor"]), False),
    (CONF_SALT_SENSOR, _entity(["sensor"]), False),
    (CONF_WEATHER, _entity(["weather"]), False),
    (CONF_OUTDOOR_TEMP_SENSOR, _entity(["sensor"], "temperature"), False),
    (CONF_FLOW_SENSOR, _entity(["binary_sensor"]), False),
    (CONF_PUMP_POWER_SENSOR, _entity(["sensor"], "power"), False),
]
ENTITY_KEYS = [key for key, _, _ in ACTUATOR_FIELDS + SENSOR_FIELDS]

FILTRATION_FIELDS: list[tuple[str, Any, bool]] = [
    (CONF_VOLUME, _number(1, 500, 0.1, "m³"), True),
    (CONF_WINDOW_START, TIME, True),
    (CONF_WINDOW_END, TIME, True),
    (CONF_BLOCKS, _number(1, 6, 1), True),
    (CONF_RUNTIME_DIVISOR, _number(1, 5, 0.1), True),
    (CONF_RUNTIME_MIN, _number(0, 24, 0.5, HOURS), True),
    (CONF_RUNTIME_MAX, _number(1, 24, 0.5, HOURS), True),
    (CONF_DEMAND_EXTENSION, BOOLEAN, True),
    (CONF_PUMP_MIN_POWER, _number(0, 5000, 1, "W"), True),
]
MEASUREMENT_FIELDS: list[tuple[str, Any, bool]] = [
    (CONF_STABILIZATION, _number(0, 120, 1, MINUTES), True),
    (CONF_MAX_AGE, _number(1, 120, 1, MINUTES), True),
    (CONF_STUCK_MINUTES, _number(0, 720, 5, MINUTES), True),
    (CONF_BACKUP_MAX_AGE, _number(5, 1440, 5, MINUTES), True),
]
CHLORINE_FIELDS: list[tuple[str, Any, bool]] = [
    (CONF_ORP_MODE, _choice([m.value for m in OrpTargetMode], CONF_ORP_MODE), True),
    (CONF_ORP_FIXED_TARGET, _number(500, 900, 5, "mV"), True),
    (CONF_ORP_HYSTERESIS, _number(0, 100, 1, "mV"), True),
    (CONF_CHLOR_MIN_ON, _number(0, 240, 1, MINUTES), True),
    (CONF_CHLOR_MIN_OFF, _number(0, 240, 1, MINUTES), True),
    (CONF_CHLOR_MAX_DAILY, _number(0.5, 24, 0.5, HOURS), True),
    (CONF_CHLOR_NO_EFFECT, _number(0.5, 24, 0.5, HOURS), True),
    (CONF_ORP_HOLDOFF, _number(0, 120, 1, MINUTES), True),
    (CONF_SALT_MIN, _number(0, 10000, 100, "ppm"), True),
    (CONF_SALT_MAX, _number(0, 10000, 100, "ppm"), True),
]
PH_FIELDS: list[tuple[str, Any, bool]] = [
    (CONF_PH_DOSING_MODE, _choice([m.value for m in PhDosingMode], CONF_PH_DOSING_MODE), True),
    (CONF_PH_DEADBAND, _number(0, 0.5, 0.01), True),
    (CONF_PH_PULSE, _number(5, 600, 1, SECONDS), True),
    (CONF_PH_PUMP_AUTO_OFF, _number(0, 3600, 1, SECONDS), True),
    (CONF_PH_LOCKOUT, _number(1, 240, 1, MINUTES), True),
    (CONF_PH_PUMP_RATE, _number(0.1, 1000, 0.1, "mL/min"), True),
    (CONF_PH_PRODUCT_DOSE, _number(1, 5000, 1, "mL"), True),
    (CONF_PH_MAX_DAILY, _number(0, 20000, 50, "mL"), True),
    (CONF_PH_MAX_HOURLY, _number(0, 5000, 10, "mL"), True),
    (CONF_PH_MIN_SAFE, _number(6.0, 7.4, 0.05), True),
    (CONF_PH_QUIET_START, TIME, True),
    (CONF_PH_QUIET_END, TIME, True),
    (CONF_PH_NO_EFFECT, _number(0.05, 1.0, 0.01), True),
    (CONF_TANK_CAPACITY, _number(0, 100000, 100, "mL"), True),
    (CONF_TANK_WARN, _number(0, 100000, 50, "mL"), True),
]
FROST_SWIM_FIELDS: list[tuple[str, Any, bool]] = [
    (CONF_FROST_TEMP, _number(-10, 10, 0.5, "°C"), True),
    (CONF_FROST_MODE, _choice([m.value for m in FrostMode], CONF_FROST_MODE), True),
    (CONF_FROST_ON_MINUTES, _number(5, 60, 5, MINUTES), True),
    (CONF_SWIM_PH_MIN, _number(6.5, 7.6, 0.05), True),
    (CONF_SWIM_PH_MAX, _number(7.2, 8.4, 0.05), True),
    (CONF_SWIM_ORP_MIN, _number(400, 800, 5, "mV"), True),
    (CONF_SWIM_DATA_MAX_AGE, _number(1, 72, 1, HOURS), True),
]

MAINTENANCE_FIELDS: list[tuple[str, Any, bool]] = [
    (key, _number(0, 365, 1, UnitOfTime.DAYS), True) for key in MAINTENANCE_OPTIONS.values()
]

OPTION_STEPS: dict[str, list[tuple[str, Any, bool]]] = {
    "entities": ACTUATOR_FIELDS + SENSOR_FIELDS,
    "filtration": FILTRATION_FIELDS,
    "measurement": MEASUREMENT_FIELDS,
    "chlorine": CHLORINE_FIELDS,
    "ph_dosing": PH_FIELDS,
    "frost_swimming": FROST_SWIM_FIELDS,
    "maintenance": MAINTENANCE_FIELDS,
}


def _schema(fields: list[tuple[str, Any, bool]], values: dict[str, Any]) -> vol.Schema:
    schema: dict[Any, Any] = {}
    for key, sel, required in fields:
        value = values.get(key, DEFAULTS.get(key))
        if key in ENTITY_KEYS:
            marker = vol.Required if required else vol.Optional
            schema[marker(key, description={"suggested_value": value})] = sel
        else:
            schema[vol.Required(key, default=value)] = sel
    return vol.Schema(schema)


def _merge(
    current: dict[str, Any], fields: list[tuple[str, Any, bool]], user_input: dict[str, Any]
) -> dict[str, Any]:
    """Replace the values of the given fields, dropping cleared optional entities."""
    merged = {k: v for k, v in current.items() if k not in {key for key, _, _ in fields}}
    merged.update({k: v for k, v in user_input.items() if v not in (None, "")})
    return merged


def _validate(options: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    merged = {**DEFAULTS, **options}
    if parse_time(merged[CONF_WINDOW_START]) >= parse_time(merged[CONF_WINDOW_END]):
        errors[CONF_WINDOW_END] = "window_invalid"
    if float(merged[CONF_RUNTIME_MIN]) > float(merged[CONF_RUNTIME_MAX]):
        errors[CONF_RUNTIME_MAX] = "runtime_invalid"
    auto_off = float(merged[CONF_PH_PUMP_AUTO_OFF])
    if auto_off > 0 and float(merged[CONF_PH_PULSE]) > auto_off - PH_PULSE_MARGIN_SECONDS:
        errors[CONF_PH_PULSE] = "pulse_exceeds_auto_off"
    if float(merged[CONF_SALT_MIN]) >= float(merged[CONF_SALT_MAX]):
        errors[CONF_SALT_MAX] = "salt_invalid"
    if float(merged[CONF_SWIM_PH_MIN]) >= float(merged[CONF_SWIM_PH_MAX]):
        errors[CONF_SWIM_PH_MAX] = "swim_ph_invalid"
    actuators = [merged.get(key) for key, _, _ in ACTUATOR_FIELDS if merged.get(key)]
    if len(actuators) != len(set(actuators)):
        errors["base"] = "duplicate_actuator"
    return errors


class PoolControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize the flow."""
        self._title = DEFAULT_NAME
        self._options: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for name, pool volume and actuators."""
        errors: dict[str, str] = {}
        fields = [(CONF_VOLUME, FILTRATION_FIELDS[0][1], True), *ACTUATOR_FIELDS]
        if user_input is not None:
            self._title = user_input.pop(CONF_NAME)
            self._options = _merge(self._options, fields, user_input)
            errors = _validate(self._options)
            if not errors:
                return await self.async_step_sensors()
        schema = vol.Schema(
            {vol.Required(CONF_NAME, default=self._title): selector.TextSelector()}
        ).extend(_schema(fields, self._options).schema)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the sensors."""
        if user_input is not None:
            self._options = _merge(self._options, SENSOR_FIELDS, user_input)
            return self.async_create_entry(title=self._title, data={}, options=self._options)
        return self.async_show_form(
            step_id="sensors", data_schema=_schema(SENSOR_FIELDS, self._options)
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> PoolControlOptionsFlow:
        """Return the options flow."""
        return PoolControlOptionsFlow()


class PoolControlOptionsFlow(OptionsFlow):
    """Change entities and tuning parameters."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the menu."""
        return self.async_show_menu(step_id="init", menu_options=list(OPTION_STEPS))

    async def _async_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        fields = OPTION_STEPS[step_id]
        current = dict(self.config_entry.options)
        errors: dict[str, str] = {}
        if user_input is not None:
            options = _merge(current, fields, user_input)
            errors = _validate(options)
            if not errors:
                return self.async_create_entry(data=options)
            current = {**current, **user_input}
        return self.async_show_form(
            step_id=step_id, data_schema=_schema(fields, current), errors=errors
        )

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit entity assignments."""
        return await self._async_step("entities", user_input)

    async def async_step_filtration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit filtration settings."""
        return await self._async_step("filtration", user_input)

    async def async_step_measurement(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit measurement settings."""
        return await self._async_step("measurement", user_input)

    async def async_step_chlorine(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit chlorination settings."""
        return await self._async_step("chlorine", user_input)

    async def async_step_ph_dosing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit pH dosing settings."""
        return await self._async_step("ph_dosing", user_input)

    async def async_step_maintenance(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit maintenance intervals."""
        return await self._async_step("maintenance", user_input)

    async def async_step_frost_swimming(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit frost protection and swimming settings."""
        return await self._async_step("frost_swimming", user_input)
