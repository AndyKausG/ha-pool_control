"""Coordinator connecting the pool controller with Home Assistant."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.logbook import async_log_entry
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    CONF_BACKUP_ORP_SENSOR,
    CONF_BACKUP_PH_SENSOR,
    CONF_BACKUP_TEMP_SENSOR,
    CONF_CHLORINATOR,
    CONF_FLOW_SENSOR,
    CONF_ORP_SENSOR,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_PH_PUMP,
    CONF_PH_SENSOR,
    CONF_PUMP,
    CONF_PUMP_MIN_POWER,
    CONF_PUMP_POWER_SENSOR,
    CONF_SALT_SENSOR,
    CONF_TEMP_SENSOR,
    CONF_WEATHER,
    DEFAULTS,
    DOMAIN,
    EVENT_POOL_CONTROL,
    STORAGE_VERSION,
    UPDATE_INTERVAL_SECONDS,
    OperatingMode,
    Problem,
)
from .controller import PoolController
from .models import Decision, Measurement, Reading, RuntimeState, Settings, Snapshot

_LOGGER = logging.getLogger(__name__)

type PoolConfigEntry = ConfigEntry[PoolCoordinator]

SAVE_DELAY_SECONDS = 10

INPUT_KEYS = (
    CONF_PH_SENSOR,
    CONF_ORP_SENSOR,
    CONF_TEMP_SENSOR,
    CONF_BACKUP_PH_SENSOR,
    CONF_BACKUP_ORP_SENSOR,
    CONF_BACKUP_TEMP_SENSOR,
    CONF_SALT_SENSOR,
    CONF_WEATHER,
    CONF_OUTDOOR_TEMP_SENSOR,
)
REQUIRED_KEYS = (CONF_PUMP, CONF_PH_SENSOR, CONF_ORP_SENSOR, CONF_TEMP_SENSOR)


def _float_state(state: State | None) -> float | None:
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    try:
        return float(state.state)
    except ValueError:
        return None


def _to_celsius(value: float | None, unit: str | None) -> float | None:
    if value is None or unit in (None, UnitOfTemperature.CELSIUS):
        return value
    try:
        return TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
    except HomeAssistantError:
        return value


class PoolCoordinator(DataUpdateCoordinator[Decision]):
    """Runs the controller periodically and on relevant state changes."""

    config_entry: PoolConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PoolConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.options: dict[str, Any] = {**DEFAULTS, **entry.options}
        self.settings = Settings.from_options(self.options)
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self.controller = PoolController(self.settings, RuntimeState())
        self._unsubs: list[CALLBACK_TYPE] = []
        self._pulse_off: CALLBACK_TYPE | None = None
        self._ph_pump_on_at: datetime | None = None
        self._problems: set[Problem] = set()
        self._simulated: dict[str, Any] = {}

    @property
    def state(self) -> RuntimeState:
        """Return the persistent controller state."""
        return self.controller.state

    def entity(self, key: str) -> str | None:
        """Return the configured entity ID for a config key."""
        value = self.options.get(key)
        return value or None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Load persisted state and subscribe to state changes."""
        if (stored := await self._store.async_load()) is not None:
            self.controller.state = RuntimeState.from_dict(stored)
        if self.state.tank_level_ml is None and self.settings.has_ph_pump:
            self.state.tank_level_ml = self.settings.tank_capacity_ml

        inputs = [eid for key in INPUT_KEYS if (eid := self.entity(key))]
        flow = [
            eid for key in (CONF_FLOW_SENSOR, CONF_PUMP_POWER_SENSOR) if (eid := self.entity(key))
        ]
        if inputs or flow:
            self._unsubs.append(
                async_track_state_change_event(self.hass, inputs + flow, self._on_input_change)
            )
        actuators = [
            eid for key in (CONF_PUMP, CONF_CHLORINATOR, CONF_PH_PUMP) if (eid := self.entity(key))
        ]
        self._unsubs.append(
            async_track_state_change_event(self.hass, actuators, self._on_actuator_change)
        )

        if self._is_on(CONF_PH_PUMP):
            _LOGGER.warning("pH dosing pump was running at startup, switching it off")
            await self._switch(CONF_PH_PUMP, False)

    async def async_shutdown(self) -> None:
        """Stop listeners, end running pulses and persist state."""
        await super().async_shutdown()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._pulse_off is not None:
            self._pulse_off()
            self._pulse_off = None
            if self._is_on(CONF_PH_PUMP):
                await self._switch(CONF_PH_PUMP, False)
        await self._store.async_save(self.state.to_dict())

    def save(self) -> None:
        """Schedule saving the persistent state."""
        self._store.async_delay_save(self.state.to_dict, SAVE_DELAY_SECONDS)

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------
    def _is_on(self, key: str) -> bool:
        entity_id = self.entity(key)
        if entity_id is None:
            return False
        state = self.hass.states.get(entity_id)
        return state is not None and state.state == STATE_ON

    def _reading(self, key: str, *, temperature: bool = False) -> Reading:
        entity_id = self.entity(key)
        if entity_id is None:
            return Reading(None)
        state = self.hass.states.get(entity_id)
        value = _float_state(state)
        if state is None:
            return Reading(None)
        if temperature:
            value = _to_celsius(value, state.attributes.get("unit_of_measurement"))
        return Reading(value, state.last_reported, state.last_changed)

    def _outdoor_temperature(self) -> float | None:
        if (entity_id := self.entity(CONF_OUTDOOR_TEMP_SENSOR)) is not None:
            state = self.hass.states.get(entity_id)
            return _to_celsius(
                _float_state(state),
                state.attributes.get("unit_of_measurement") if state else None,
            )
        if (entity_id := self.entity(CONF_WEATHER)) is not None:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                return None
            value = state.attributes.get(ATTR_TEMPERATURE)
            if value is None:
                return None
            return _to_celsius(float(value), state.attributes.get("temperature_unit"))
        return None

    def _flow_ok(self) -> bool | None:
        if (entity_id := self.entity(CONF_FLOW_SENSOR)) is not None:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                return None
            return state.state == STATE_ON
        if (entity_id := self.entity(CONF_PUMP_POWER_SENSOR)) is not None:
            power = _float_state(self.hass.states.get(entity_id))
            if power is None:
                return None
            return power >= float(self.options[CONF_PUMP_MIN_POWER])
        return None

    def snapshot(self) -> Snapshot:
        """Collect all controller inputs from the state machine."""
        return Snapshot(
            now=dt_util.now(),
            pump_on=self._is_on(CONF_PUMP),
            chlorinator_on=self._is_on(CONF_CHLORINATOR),
            ph_pump_on=self._is_on(CONF_PH_PUMP),
            ph=self._reading(CONF_PH_SENSOR),
            orp=self._reading(CONF_ORP_SENSOR),
            temperature=self._reading(CONF_TEMP_SENSOR, temperature=True),
            backup_ph=self._reading(CONF_BACKUP_PH_SENSOR),
            backup_orp=self._reading(CONF_BACKUP_ORP_SENSOR),
            backup_temperature=self._reading(CONF_BACKUP_TEMP_SENSOR, temperature=True),
            salt=self._reading(CONF_SALT_SENSOR),
            outdoor_temperature=self._outdoor_temperature(),
            outdoor_configured=bool(
                self.entity(CONF_OUTDOOR_TEMP_SENSOR) or self.entity(CONF_WEATHER)
            ),
            flow_ok=self._flow_ok(),
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    @callback
    def _on_input_change(self, event: Event[EventStateChangedData]) -> None:
        if (
            event.data["entity_id"]
            in (
                self.entity(CONF_FLOW_SENSOR),
                self.entity(CONF_PUMP_POWER_SENSOR),
            )
            and self._flow_ok() is False
        ):
            self.hass.async_create_task(self._enforce_interlock("no_flow"))
        self.hass.async_create_task(self.async_request_refresh())

    @callback
    def _on_actuator_change(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        new_state = event.data["new_state"]
        is_on = new_state is not None and new_state.state == STATE_ON

        if entity_id == self.entity(CONF_PH_PUMP):
            changed = new_state.last_changed if new_state is not None else dt_util.utcnow()
            self._track_ph_pump(is_on, dt_util.as_local(changed))

        pump_running = self._is_on(CONF_PUMP)
        if not pump_running and (self._is_on(CONF_CHLORINATOR) or self._is_on(CONF_PH_PUMP)):
            self.hass.async_create_task(self._enforce_interlock("pump_off"))
        self.hass.async_create_task(self.async_request_refresh())

    @callback
    def _track_ph_pump(self, is_on: bool, now: datetime) -> None:
        if is_on:
            if self._ph_pump_on_at is None:
                self._ph_pump_on_at = now
                if self._pulse_off is None:
                    # Switched on outside the controller: apply the lockout.
                    self.controller.register_ph_pulse_start(now, self.settings.ph_pulse_s)
            return
        if self._ph_pump_on_at is not None:
            seconds = (now - self._ph_pump_on_at).total_seconds()
            self._ph_pump_on_at = None
            dose = self.controller.record_ph_dose(seconds, now)
            self._log(f"pH minus dosed: {dose:.0f} ml in {seconds:.0f} s")
            self._fire("ph_dosed", dose_ml=round(dose, 1), seconds=round(seconds, 1))
            self.save()
            self.async_update_listeners()
        if self._pulse_off is not None:
            self._pulse_off()
            self._pulse_off = None

    async def _enforce_interlock(self, reason: str) -> None:
        """Switch off chlorinator and dosing pump. Always active."""
        for key in (CONF_CHLORINATOR, CONF_PH_PUMP):
            if self._is_on(key):
                await self._switch(key, False)
                self._log(f"{key} switched off by interlock ({reason})")
                self._fire("interlock", actuator=key, reason=reason)

    # ------------------------------------------------------------------
    # Update cycle
    # ------------------------------------------------------------------
    async def _async_update_data(self) -> Decision:
        decision = self.controller.step(self.snapshot())
        await self._execute(decision)
        self._update_problems(decision.problems)
        self._check_missing_entities()
        self.save()
        return decision

    async def _execute(self, decision: Decision) -> None:
        dry_run = self.state.dry_run
        snap_pump = self._is_on(CONF_PUMP)
        snap_chlor = self._is_on(CONF_CHLORINATOR)

        if decision.chlorinator is False and snap_chlor:
            # Interlock stops are executed even in dry-run mode.
            safety = decision.chlorinator_reason == "interlock"
            await self._apply(
                CONF_CHLORINATOR, False, decision.chlorinator_reason, dry_run and not safety
            )
        if decision.ph_pump_stop and self._is_on(CONF_PH_PUMP):
            # Safety stops are executed even in dry-run mode.
            await self._apply(CONF_PH_PUMP, False, decision.ph_pulse_reason, False)

        if decision.pump is not None and decision.pump != snap_pump:
            await self._apply(CONF_PUMP, decision.pump, decision.pump_reason, dry_run)

        if decision.chlorinator is True and not snap_chlor:
            await self._apply(CONF_CHLORINATOR, True, decision.chlorinator_reason, dry_run)

        if decision.ph_pulse_seconds > 0:
            await self._start_pulse(decision.ph_pulse_seconds, dry_run)

    async def _apply(self, key: str, turn_on: bool, reason: str, dry_run: bool) -> None:
        action = "on" if turn_on else "off"
        if dry_run:
            if self._simulated.get(key) != (turn_on, reason):
                self._simulated[key] = (turn_on, reason)
                self._log(f"Simulation: {key} would be switched {action} ({reason})")
                self._fire("simulated_action", actuator=key, action=action, reason=reason)
            return
        self._simulated.pop(key, None)
        await self._switch(key, turn_on)
        self._log(f"{key} switched {action} ({reason})")
        self._fire("action", actuator=key, action=action, reason=reason)

    async def _start_pulse(self, seconds: float, dry_run: bool) -> None:
        now = dt_util.now()
        self.controller.register_ph_pulse_start(now, seconds)
        if dry_run:
            self._log(f"Simulation: pH dosing pulse of {seconds:.0f} s")
            self._fire("simulated_action", actuator=CONF_PH_PUMP, action="pulse", seconds=seconds)
            return
        self._log(f"pH dosing pulse started ({seconds:.0f} s)")
        self._fire("action", actuator=CONF_PH_PUMP, action="pulse", seconds=seconds)
        self._pulse_off = async_call_later(self.hass, seconds, self._end_pulse)
        await self._switch(CONF_PH_PUMP, True)

    async def _end_pulse(self, _now: Any) -> None:
        self._pulse_off = None
        if self._is_on(CONF_PH_PUMP):
            await self._switch(CONF_PH_PUMP, False)

    async def _switch(self, key: str, turn_on: bool) -> None:
        entity_id = self.entity(key)
        if entity_id is None:
            return
        domain = entity_id.split(".", 1)[0]
        await self.hass.services.async_call(
            domain,
            SERVICE_TURN_ON if turn_on else SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    def _log(self, message: str) -> None:
        _LOGGER.debug(message)
        async_log_entry(self.hass, self.config_entry.title, message, DOMAIN)

    def _fire(self, event_type: str, **data: Any) -> None:
        self.hass.bus.async_fire(
            EVENT_POOL_CONTROL,
            {"entry_id": self.config_entry.entry_id, "type": event_type, **data},
        )

    def _update_problems(self, problems: set[Problem]) -> None:
        for problem in problems - self._problems:
            self._log(f"Problem detected: {problem.value}")
            self._fire("problem", problem=problem.value)
        for problem in self._problems - problems:
            self._log(f"Problem resolved: {problem.value}")
            self._fire("problem_resolved", problem=problem.value)
        self._problems = set(problems)

    def _check_missing_entities(self) -> None:
        if not self.hass.is_running:
            return
        for key in (*REQUIRED_KEYS, CONF_CHLORINATOR, CONF_PH_PUMP):
            entity_id = self.entity(key)
            issue_id = f"missing_entity_{self.config_entry.entry_id}_{key}"
            if entity_id is not None and self.hass.states.get(entity_id) is None:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=False,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="missing_entity",
                    translation_placeholders={
                        "entity_id": entity_id,
                        "name": self.config_entry.title,
                    },
                )
            else:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    # ------------------------------------------------------------------
    # User actions
    # ------------------------------------------------------------------
    async def async_set_runtime(self, **values: Any) -> None:
        """Update user settings stored in the runtime state."""
        for key, value in values.items():
            setattr(self.state, key, value)
        if "mode" in values or "dry_run" in values:
            self._simulated.clear()
        self.save()
        await self.async_refresh()

    async def async_start_boost(self, hours: float | None = None) -> None:
        """Start a circulation boost."""
        if self.state.operating_mode in (OperatingMode.WINTER, OperatingMode.OFF):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="boost_not_possible"
            )
        self.controller.start_boost(dt_util.now(), hours)
        self.save()
        await self.async_refresh()

    async def async_stop_boost(self) -> None:
        """Stop a circulation boost."""
        self.controller.stop_boost()
        self.save()
        await self.async_refresh()

    async def async_tank_refilled(
        self, refilled_ml: float | None = None, level_ml: float | None = None
    ) -> None:
        """Record a refill of the pH minus tank."""
        self.controller.tank_refilled(refilled_ml, level_ml)
        self._log("pH minus tank refilled")
        self.save()
        await self.async_refresh()

    async def async_reset_ph_lock(self) -> None:
        """Release the pH dosing lock."""
        self.controller.reset_ph_lock()
        self._log("pH dosing lock released")
        self.save()
        await self.async_refresh()

    async def async_reset_season(self) -> None:
        """Reset the seasonal dosing counter."""
        self.state.ph_dosed_season_ml = 0.0
        self.save()
        await self.async_refresh()

    async def async_manual_ph_pulse(self) -> None:
        """Run one dosing pulse on user request, honouring all safety rules."""
        if not self.settings.has_ph_pump:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="no_ph_pump")
        measurement = self.data.measurement if self.data else Measurement()
        reason = self.controller.manual_pulse_blocked_reason(self.snapshot(), measurement)
        if reason is not None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="pulse_not_possible",
                translation_placeholders={"reason": reason or ""},
            )
        await self._start_pulse(self.settings.ph_pulse_s, False)
        self.save()

    def diagnostics_problems(self) -> list[str]:
        """Return the active problems for diagnostics."""
        return sorted(problem.value for problem in self._problems)
