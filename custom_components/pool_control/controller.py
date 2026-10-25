"""Control logic for filtration, chlorination, pH dosing and frost protection.

The controller is independent of Home Assistant. It receives a snapshot of
all inputs, updates its persistent state and returns a decision describing
what the actuators should do. Executing the decision is the job of the
coordinator.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from . import chemistry
from .const import (
    ALARM_ORP_MIN,
    ALARM_PH_MAX,
    ALARM_PH_MIN,
    CHLOR_NO_EFFECT_MIN_RISE_MV,
    DEFAULT_TDS,
    DEVIATION_ORP,
    DEVIATION_PH,
    FALLBACK_WATER_TEMP,
    FROST_HYSTERESIS,
    ORP_PLAUSIBLE,
    PH_PLAUSIBLE,
    PH_SUCCESS_MIN_DROP,
    PUMP_MIN_START_MINUTES,
    SALT_MAX_AGE_HOURS,
    SWIM_DOSING_BLOCK_MINUTES,
    TEMP_PLAUSIBLE,
    FrostMode,
    MaintenanceTask,
    MeasurementSource,
    OperatingMode,
    OrpTargetMode,
    PhDosingMode,
    Problem,
    Status,
    SwimmingStatus,
)
from .models import Decision, Measurement, Reading, RuntimeState, Settings, Snapshot

PH_PULSE_MIN_SECONDS = 5.0
PH_PULSE_OVERRUN_SECONDS = 30.0
PH_PROPORTIONAL_MAX_STEP = 0.1
PH_SESSION_TIMEOUT = timedelta(hours=24)
LEARNING_WEIGHT = 0.3

CHEMISTRY_MODES = (OperatingMode.AUTO, OperatingMode.MANUAL)


def minutes_between(start: datetime | None, end: datetime) -> float:
    """Return minutes from start to end, infinity if start is unknown."""
    if start is None:
        return float("inf")
    return (end - start).total_seconds() / 60.0


def in_time_window(now: time, start: time, end: time) -> bool:
    """Return True if now lies in [start, end); supports windows over midnight."""
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


def _plausible(value: float | None, limits: tuple[float, float]) -> bool:
    return value is not None and limits[0] <= value <= limits[1]


class PoolController:
    """Stateful pool controller."""

    def __init__(self, settings: Settings, state: RuntimeState) -> None:
        """Initialize the controller."""
        self.settings = settings
        self.state = state
        self._prev_pump_on: bool | None = None
        self._prev_chlorinator_on: bool | None = None
        self._sensor_stuck = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def step(self, snap: Snapshot) -> Decision:
        """Evaluate all inputs and return the desired actuator states."""
        now = snap.now
        self._accumulate(snap)
        self._roll_day(now)
        for task in self.settings.maintenance_days:
            # Start counting the interval when a reminder is first enabled.
            self.state.maintenance_done.setdefault(task.value, now.isoformat())
        if self.state.shock_until is not None and now >= self.state.shock_until:
            self.state.shock_until = None
        self._track_switches(snap)

        decision = Decision()
        measurement = self._evaluate_measurement(snap)
        decision.measurement = measurement
        self._remember_measurement(now, measurement)

        decision.orp_target = self._orp_target(measurement)
        decision.filtration_target_h = self.filtration_target_hours()
        self._update_frost(snap.outdoor_temperature)

        self._decide_pump(snap, decision)
        self._decide_chlorinator(snap, decision)
        self._decide_ph(snap, decision)
        self._stop_dosing_before_pump(snap, decision)
        self._check_ph_session(now, measurement)

        decision.swimming = self._swimming_status(now, measurement)
        decision.next_filtration_start = self._next_filtration_start(snap)
        decision.problems = self._problems(snap, measurement)
        decision.status = self._status(snap)
        decision.maintenance_due = self.maintenance_due(now)
        return decision

    def filtration_target_hours(self) -> float:
        """Return today's filtration target based on the water temperature."""
        reference = self.state.temp_mean_yesterday
        if reference is None:
            reference = self.state.last_valid_temperature
        if reference is None:
            reference = FALLBACK_WATER_TEMP
        s = self.settings
        return chemistry.filtration_hours(
            reference, s.runtime_divisor, s.runtime_min, s.runtime_max
        )

    @property
    def ph_pump_rate(self) -> float:
        """Return the effective dosing pump rate in ml/min."""
        return self.state.ph_pump_rate_calibrated or self.settings.ph_pump_rate

    @property
    def ph_product_dose(self) -> float:
        """Return the effective product dose (ml per 10 m3 per 0.1 pH)."""
        if self.settings.ph_dosing_mode is PhDosingMode.PROPORTIONAL:
            return self.state.ph_product_dose_learned or self.settings.ph_product_dose
        return self.settings.ph_product_dose

    def register_ph_pulse_start(self, now: datetime, seconds: float) -> None:
        """Record the start of a dosing pulse and start the lockout."""
        st = self.state
        st.last_ph_pulse = now
        st.ph_lockout_until = now + timedelta(seconds=seconds, minutes=self.settings.ph_lockout_min)
        if st.ph_session_start_ph is None and st.last_valid_ph is not None:
            st.ph_session_start_ph = st.last_valid_ph
            st.ph_session_ml = 0.0
        st.ph_session_last_pulse = now

    def record_ph_dose(self, seconds: float, now: datetime) -> float:
        """Account for a finished dosing run of the given length; return ml."""
        st = self.state
        dose = chemistry.dose_for_pump_seconds(seconds, self.ph_pump_rate)
        cutoff = now - timedelta(hours=1)
        st.ph_dose_log = [
            (ts, ml) for ts, ml in st.ph_dose_log if datetime.fromisoformat(ts) > cutoff
        ]
        st.ph_dose_log.append((now.isoformat(), round(dose, 2)))
        st.ph_dosed_today_ml += dose
        st.ph_dosed_season_ml += dose
        st.ph_session_ml += dose
        st.ph_pulses_today += 1
        st.ph_pump_seconds_since_refill += seconds
        if st.tank_level_ml is not None:
            st.tank_level_ml = max(0.0, st.tank_level_ml - dose)
        return dose

    def tank_refilled(self, refilled_ml: float | None, level_ml: float | None) -> None:
        """Record a tank refill and calibrate the pump rate if possible.

        refilled_ml is the amount poured into the tank. Assuming the tank is
        refilled to the same level each time, it equals the consumption since
        the last refill, which together with the accumulated pump run time
        yields the real pump rate.
        """
        st = self.state
        if refilled_ml and st.ph_pump_seconds_since_refill >= 60:
            st.ph_pump_rate_calibrated = round(
                refilled_ml / (st.ph_pump_seconds_since_refill / 60.0), 2
            )
        st.ph_pump_seconds_since_refill = 0.0
        st.tank_level_ml = level_ml if level_ml is not None else self.settings.tank_capacity_ml

    def reset_ph_lock(self) -> None:
        """Release a dosing lock caused by missing effect."""
        self.state.ph_dosing_locked = False
        self._end_ph_session()

    def start_boost(self, now: datetime, hours: float | None = None) -> None:
        """Run the pump for an additional period."""
        duration = hours if hours is not None else self.state.boost_hours
        self.state.boost_until = now + timedelta(hours=duration)

    def stop_boost(self) -> None:
        """Cancel an active circulation boost."""
        self.state.boost_until = None

    def maintenance_done(self, task: MaintenanceTask, now: datetime) -> None:
        """Mark a maintenance task as done."""
        self.state.maintenance_done[task.value] = now.isoformat()

    def maintenance_next(self, task: MaintenanceTask) -> datetime | None:
        """Return when a maintenance task is due next."""
        days = self.settings.maintenance_days.get(task)
        done = self.state.maintenance_done.get(task.value)
        if days is None or done is None:
            return None
        return datetime.fromisoformat(done) + timedelta(days=days)

    def maintenance_due(self, now: datetime) -> list[MaintenanceTask]:
        """Return the maintenance tasks that are due."""
        due = []
        for task in self.settings.maintenance_days:
            next_due = self.maintenance_next(task)
            if next_due is not None and now >= next_due:
                due.append(task)
        return due

    def start_shock(self, now: datetime) -> None:
        """Raise the free chlorine target for the configured shock duration."""
        self.state.shock_until = now + timedelta(hours=self.state.shock_hours)

    def stop_shock(self) -> None:
        """End a shock chlorination."""
        self.state.shock_until = None

    def shock_active(self, now: datetime) -> bool:
        """Return True while a shock chlorination is running."""
        return self.state.shock_until is not None and now < self.state.shock_until

    def record_water_test(self, now: datetime, **values: float) -> None:
        """Store the results of a manual water test."""
        for key, value in values.items():
            setattr(self.state, key, value)
        self.state.last_water_test = now

    def saturation_index(self, ph: float | None, salt: float | None) -> float | None:
        """Return the Langelier saturation index from test values and readings."""
        st = self.state
        temperature = st.last_valid_temperature
        ph = ph if ph is not None else st.last_valid_ph
        if None in (ph, temperature, st.calcium_hardness, st.alkalinity):
            return None
        return chemistry.saturation_index(
            ph,  # type: ignore[arg-type]
            temperature,  # type: ignore[arg-type]
            st.calcium_hardness,  # type: ignore[arg-type]
            st.alkalinity,  # type: ignore[arg-type]
            cyanuric_acid_ppm=st.cyanuric_acid or 0.0,
            tds_ppm=salt if salt else DEFAULT_TDS,
        )

    # ------------------------------------------------------------------
    # Bookkeeping
    # ------------------------------------------------------------------
    def _accumulate(self, snap: Snapshot) -> None:
        st = self.state
        now = snap.now
        if self._prev_pump_on is None:
            self._prev_pump_on = st.pump_on_since is not None
            self._prev_chlorinator_on = st.chlorinator_on_since is not None
        if st.last_accumulated is not None and now > st.last_accumulated:
            elapsed = (now - st.last_accumulated).total_seconds()
            if self._prev_pump_on:
                st.pump_runtime_today_s += elapsed
            if self._prev_chlorinator_on:
                st.chlorinator_runtime_today_s += elapsed
        st.last_accumulated = now

    def _roll_day(self, now: datetime) -> None:
        st = self.state
        today = now.date().isoformat()
        if st.day == today:
            return
        if st.day is not None:
            if st.temp_count_today:
                st.temp_mean_yesterday = round(st.temp_sum_today / st.temp_count_today, 2)
            st.pump_runtime_today_s = 0.0
            st.chlorinator_runtime_today_s = 0.0
            st.ph_dosed_today_ml = 0.0
            st.ph_pulses_today = 0
            st.temp_sum_today = 0.0
            st.temp_count_today = 0
        st.day = today

    def _track_switches(self, snap: Snapshot) -> None:
        st = self.state
        now = snap.now
        if snap.pump_on:
            if st.pump_on_since is None:
                st.pump_on_since = now
            st.pump_off_since = None
        else:
            st.pump_on_since = None
            if st.pump_off_since is None:
                st.pump_off_since = now
        if snap.chlorinator_on:
            if st.chlorinator_on_since is None:
                st.chlorinator_on_since = now
                st.chlorinator_start_orp = st.last_valid_orp
            st.chlorinator_off_since = None
        else:
            st.chlorinator_on_since = None
            st.chlorinator_start_orp = None
            if st.chlorinator_off_since is None:
                st.chlorinator_off_since = now
        self._prev_pump_on = snap.pump_on
        self._prev_chlorinator_on = snap.chlorinator_on

    # ------------------------------------------------------------------
    # Measurement
    # ------------------------------------------------------------------
    def _flow(self, snap: Snapshot) -> bool:
        return snap.pump_on and snap.flow_ok is not False

    def _evaluate_measurement(self, snap: Snapshot) -> Measurement:
        s = self.settings
        now = snap.now
        result = Measurement()
        self._sensor_stuck = False

        reason: str | None = None
        if not snap.pump_on:
            reason = "pump_off"
        elif snap.flow_ok is False:
            reason = "no_flow"
        elif minutes_between(self.state.pump_on_since, now) < s.stabilization_min:
            reason = "stabilizing"
        else:
            reason = self._primary_reading_problem(snap.ph, PH_PLAUSIBLE, now) or (
                self._primary_reading_problem(snap.orp, ORP_PLAUSIBLE, now)
            )

        if reason is None:
            result.source = MeasurementSource.PRIMARY
            result.primary_valid = True
            result.ph = snap.ph.value
            result.orp = snap.orp.value
            if self._primary_reading_problem(snap.temperature, TEMP_PLAUSIBLE, now) is None:
                result.temperature = snap.temperature.value
            return result

        result.invalid_reason = reason
        backup_ph = self._backup_value(snap.backup_ph, PH_PLAUSIBLE, now)
        backup_orp = self._backup_value(snap.backup_orp, ORP_PLAUSIBLE, now)
        if backup_ph is not None or backup_orp is not None:
            result.source = MeasurementSource.BACKUP
            result.ph = backup_ph
            result.orp = backup_orp
            result.temperature = self._backup_value(snap.backup_temperature, TEMP_PLAUSIBLE, now)
        return result

    def _primary_reading_problem(
        self, reading: Reading, limits: tuple[float, float], now: datetime
    ) -> str | None:
        s = self.settings
        if reading.value is None:
            return "unavailable"
        if not _plausible(reading.value, limits):
            return "implausible"
        if minutes_between(reading.last_reported, now) > s.max_age_min:
            return "stale"
        if (
            s.stuck_min > 0
            and minutes_between(reading.last_changed, now) > s.stuck_min
            and minutes_between(self.state.pump_on_since, now) > s.stuck_min
        ):
            self._sensor_stuck = True
            return "stuck"
        return None

    def _backup_value(
        self, reading: Reading, limits: tuple[float, float], now: datetime
    ) -> float | None:
        if not _plausible(reading.value, limits):
            return None
        if minutes_between(reading.last_reported, now) > self.settings.backup_max_age_min:
            return None
        return reading.value

    def _sensors_deviate(self, snap: Snapshot, m: Measurement) -> bool:
        """Return True if primary and backup sensors disagree significantly."""
        if not m.primary_valid:
            return False
        backup_ph = self._backup_value(snap.backup_ph, PH_PLAUSIBLE, snap.now)
        backup_orp = self._backup_value(snap.backup_orp, ORP_PLAUSIBLE, snap.now)
        return (
            backup_ph is not None and m.ph is not None and abs(m.ph - backup_ph) > DEVIATION_PH
        ) or (
            backup_orp is not None and m.orp is not None and abs(m.orp - backup_orp) > DEVIATION_ORP
        )

    def _remember_measurement(self, now: datetime, m: Measurement) -> None:
        if not m.primary_valid:
            return
        st = self.state
        st.last_valid_measurement = now
        st.last_valid_ph = m.ph
        st.last_valid_orp = m.orp
        if m.temperature is not None:
            st.last_valid_temperature = m.temperature
            st.temp_sum_today += m.temperature
            st.temp_count_today += 1

    @property
    def _chlorine_target(self) -> float:
        st = self.state
        if st.shock_until is not None:
            return max(st.chlorine_target, st.shock_target)
        return st.chlorine_target

    def _orp_target(self, m: Measurement) -> float:
        s = self.settings
        if s.orp_mode is OrpTargetMode.PH_COMPENSATED:
            ph = m.ph if m.ph is not None else self.state.last_valid_ph
            if ph is not None:
                return chemistry.orp_target(ph, self._chlorine_target)
        # Fixed set point: raise it by the chart difference during a shock.
        raise_mv = chemistry.orp_target(7.4, self._chlorine_target) - chemistry.orp_target(
            7.4, self.state.chlorine_target
        )
        return s.orp_fixed_target + raise_mv

    # ------------------------------------------------------------------
    # Frost protection
    # ------------------------------------------------------------------
    def _update_frost(self, outdoor: float | None) -> None:
        if outdoor is None:
            return
        threshold = self.settings.frost_temp
        if self.state.frost_active:
            self.state.frost_active = outdoor < threshold + FROST_HYSTERESIS
        else:
            self.state.frost_active = outdoor < threshold

    def _frost_wants_pump(self, now: datetime) -> bool:
        if not self.state.frost_active:
            return False
        if self.state.operating_mode is OperatingMode.OFF:
            return False
        if self.settings.frost_mode is FrostMode.CONTINUOUS:
            return True
        return now.minute < self.settings.frost_on_min

    # ------------------------------------------------------------------
    # Filtration
    # ------------------------------------------------------------------
    def _window(self, now: datetime) -> tuple[datetime, datetime]:
        s = self.settings
        start = now.replace(
            hour=s.window_start.hour,
            minute=s.window_start.minute,
            second=s.window_start.second,
            microsecond=0,
        )
        end = now.replace(
            hour=s.window_end.hour,
            minute=s.window_end.minute,
            second=s.window_end.second,
            microsecond=0,
        )
        return start, end

    def _schedule_wants_pump(self, snap: Snapshot, target_h: float) -> tuple[bool, str]:
        """Distribute the daily target over equally sized slots in the window.

        In slot i the pump runs until the cumulative runtime reaches
        (i + 1) / n of the daily target. Run time accumulated earlier (manual
        runs, frost protection) counts towards the quota, and missed time is
        caught up in the following slots.
        """
        now = snap.now
        start, end = self._window(now)
        if not start <= now < end:
            return False, "outside_window"
        slot_len = (end - start) / self.settings.blocks
        index = min(int((now - start) / slot_len), self.settings.blocks - 1)
        quota_s = target_h * 3600 * (index + 1) / self.settings.blocks
        remaining_s = quota_s - self.state.pump_runtime_today_s
        if snap.pump_on:
            return remaining_s > 0, "schedule"
        return remaining_s >= PUMP_MIN_START_MINUTES * 60, "schedule"

    def _chemistry_demand(self, snap: Snapshot, m: Measurement) -> bool:
        if snap.chlorinator_on:
            return True
        return self._ph_needs_dosing(m) and not self._ph_dosing_blocked_hard(snap)

    def _decide_pump(self, snap: Snapshot, decision: Decision) -> None:
        st = self.state
        now = snap.now
        mode = st.operating_mode
        if st.boost_until is not None and now >= st.boost_until:
            st.boost_until = None
        boost = st.boost_until is not None and mode in (
            OperatingMode.AUTO,
            OperatingMode.MANUAL,
            OperatingMode.MAINTENANCE,
        )
        frost = self._frost_wants_pump(now)

        if mode is OperatingMode.OFF:
            st.pump_owned = False
            return

        if mode in (OperatingMode.AUTO, OperatingMode.WINTER):
            st.pump_owned = False
            want, reason = False, "idle"
            if mode is OperatingMode.AUTO:
                want, reason = self._schedule_wants_pump(snap, decision.filtration_target_h)
                if not want and self._extension_allowed(snap, decision):
                    want, reason = True, "demand_extension"
            if boost:
                want, reason = True, "boost"
            if frost:
                want, reason = True, "frost_protection"
            if not want:
                reason = "winter" if mode is OperatingMode.WINTER else "schedule_done"
                if mode is OperatingMode.AUTO and reason == "schedule_done":
                    start, end = self._window(now)
                    if not start <= now < end:
                        reason = "outside_window"
            decision.pump = want
            decision.pump_reason = reason
            return

        # Manual and maintenance: the user controls the pump. The controller
        # only switches it on for frost protection or a boost and switches it
        # off again afterwards.
        if frost or boost:
            st.pump_owned = True
            decision.pump = True
            decision.pump_reason = "frost_protection" if frost else "boost"
        elif st.pump_owned:
            st.pump_owned = False
            decision.pump = False
            decision.pump_reason = "boost_finished"

    def _stop_dosing_before_pump(self, snap: Snapshot, decision: Decision) -> None:
        """Switch off chlorinator and dosing pump one step before the pump.

        The pump keeps running until the next step, which flushes the cell.
        """
        if decision.pump is not False or not snap.pump_on:
            return
        if not (snap.chlorinator_on or snap.ph_pump_on):
            return
        if snap.chlorinator_on:
            decision.chlorinator, decision.chlorinator_reason = False, "pump_stopping"
        if snap.ph_pump_on:
            decision.ph_pump_stop, decision.ph_pulse_reason = True, "pump_stopping"
        decision.ph_pulse_seconds = 0.0
        decision.pump = None
        decision.pump_reason = "post_run"

    def _extension_allowed(self, snap: Snapshot, decision: Decision) -> bool:
        s = self.settings
        if not (s.demand_extension and snap.pump_on):
            return False
        start, end = self._window(snap.now)
        if not start <= snap.now < end:
            return False
        if self.state.pump_runtime_today_s >= s.runtime_max * 3600:
            return False
        return self._chemistry_demand(snap, decision.measurement)

    def _next_filtration_start(self, snap: Snapshot) -> datetime | None:
        if self.state.operating_mode is not OperatingMode.AUTO or snap.pump_on:
            return None
        now = snap.now
        start, end = self._window(now)
        slot_len = (end - start) / self.settings.blocks
        for index in range(self.settings.blocks):
            slot_start = start + slot_len * index
            if slot_start > now:
                return slot_start
        return start + timedelta(days=1)

    # ------------------------------------------------------------------
    # Chlorination
    # ------------------------------------------------------------------
    def _decide_chlorinator(self, snap: Snapshot, decision: Decision) -> None:
        s = self.settings
        st = self.state
        now = snap.now
        if not s.has_chlorinator:
            return
        m = decision.measurement
        target = decision.orp_target or s.orp_fixed_target
        active = st.operating_mode in CHEMISTRY_MODES and st.chlorine_control_enabled
        daily_limit_reached = st.chlorinator_runtime_today_s >= s.chlor_max_daily_h * 3600

        if not self._flow(snap):
            if snap.chlorinator_on:
                decision.chlorinator, decision.chlorinator_reason = False, "interlock"
            return

        if snap.chlorinator_on:
            if not active:
                decision.chlorinator, decision.chlorinator_reason = False, "disabled"
            elif not m.primary_valid:
                decision.chlorinator, decision.chlorinator_reason = (
                    False,
                    "measurement_invalid",
                )
            elif daily_limit_reached:
                decision.chlorinator, decision.chlorinator_reason = False, "daily_limit"
            elif self._orp_holdoff(now):
                return
            elif (
                m.orp is not None
                and m.orp > target + s.orp_hysteresis
                and minutes_between(st.chlorinator_on_since, now) >= s.chlor_min_on_min
            ):
                decision.chlorinator, decision.chlorinator_reason = False, "target_reached"
            return

        if (
            active
            and m.primary_valid
            and m.orp is not None
            and not daily_limit_reached
            and not self._orp_holdoff(now)
            and m.orp < target - s.orp_hysteresis
            and minutes_between(st.chlorinator_off_since, now) >= s.chlor_min_off_min
        ):
            decision.chlorinator, decision.chlorinator_reason = True, "orp_low"

    def _orp_holdoff(self, now: datetime) -> bool:
        return minutes_between(self.state.last_ph_pulse, now) < self.settings.orp_holdoff_min

    def _chlorinator_ineffective(self, snap: Snapshot, m: Measurement) -> bool:
        st = self.state
        if not snap.chlorinator_on or st.chlorinator_start_orp is None or m.orp is None:
            return False
        hours_on = minutes_between(st.chlorinator_on_since, snap.now) / 60
        if hours_on < self.settings.chlor_no_effect_h:
            return False
        return m.orp - st.chlorinator_start_orp < CHLOR_NO_EFFECT_MIN_RISE_MV

    # ------------------------------------------------------------------
    # pH dosing
    # ------------------------------------------------------------------
    def _ph_needs_dosing(self, m: Measurement) -> bool:
        return (
            m.primary_valid
            and m.ph is not None
            and m.ph > self.state.ph_target + self.settings.ph_deadband
        )

    def _ph_dosing_blocked_hard(self, snap: Snapshot) -> bool:
        """Return True if dosing is impossible for the rest of the run."""
        s = self.settings
        st = self.state
        return (
            not s.has_ph_pump
            or st.operating_mode not in CHEMISTRY_MODES
            or not st.ph_control_enabled
            or st.ph_dosing_locked
            or st.ph_dosed_today_ml >= s.ph_max_daily_ml
            or (st.tank_level_ml is not None and st.tank_level_ml <= 0)
            or in_time_window(snap.now.time(), s.ph_quiet_start, s.ph_quiet_end)
        )

    def ph_blocked_reason(self, snap: Snapshot, m: Measurement) -> str | None:
        """Return why no dosing pulse may start now, None if it may."""
        s = self.settings
        st = self.state
        now = snap.now
        checks: tuple[tuple[bool, str], ...] = (
            (st.operating_mode not in CHEMISTRY_MODES, "mode"),
            (not st.ph_control_enabled, "disabled"),
            (st.ph_dosing_locked, "locked"),
            (snap.ph_pump_on, "pulse_running"),
            (not self._flow(snap), "pump_off"),
            (not m.primary_valid or m.ph is None, "measurement_invalid"),
            (in_time_window(now.time(), s.ph_quiet_start, s.ph_quiet_end), "quiet_hours"),
            (st.ph_lockout_until is not None and now < st.ph_lockout_until, "lockout"),
            (m.ph is not None and m.ph < s.ph_min_safe, "ph_too_low"),
            (not self._ph_needs_dosing(m), "in_range"),
            (st.ph_dosed_today_ml >= s.ph_max_daily_ml, "daily_limit"),
            (st.tank_level_ml is not None and st.tank_level_ml <= 0, "tank_empty"),
            (self.ph_dosed_last_hour(now) >= s.ph_max_hourly_ml, "hourly_limit"),
        )
        for failed, reason in checks:
            if failed:
                return reason
        return None

    def manual_pulse_blocked_reason(self, snap: Snapshot, m: Measurement) -> str | None:
        """Return why a manual dosing pulse is not possible, None if it is.

        A manual pulse ignores set point, lockout and quiet hours but never
        the safety rules.
        """
        s = self.settings
        st = self.state
        checks: tuple[tuple[bool, str], ...] = (
            (snap.ph_pump_on, "pulse_running"),
            (not self._flow(snap), "pump_off"),
            (st.ph_dosing_locked, "locked"),
            (m.ph is not None and m.ph < s.ph_min_safe, "ph_too_low"),
            (st.ph_dosed_today_ml >= s.ph_max_daily_ml, "daily_limit"),
            (st.tank_level_ml is not None and st.tank_level_ml <= 0, "tank_empty"),
            (self.ph_dosed_last_hour(snap.now) >= s.ph_max_hourly_ml, "hourly_limit"),
        )
        return next((reason for failed, reason in checks if failed), None)

    def ph_dosed_last_hour(self, now: datetime) -> float:
        """Return the amount dosed within the last hour."""
        cutoff = now - timedelta(hours=1)
        return sum(ml for ts, ml in self.state.ph_dose_log if datetime.fromisoformat(ts) > cutoff)

    def ph_remaining_ml(self, now: datetime) -> float:
        """Return the amount that may still be dosed (daily, hourly and tank limit)."""
        s = self.settings
        st = self.state
        remaining = min(
            s.ph_max_daily_ml - st.ph_dosed_today_ml,
            s.ph_max_hourly_ml - self.ph_dosed_last_hour(now),
        )
        if st.tank_level_ml is not None:
            remaining = min(remaining, st.tank_level_ml)
        return max(0.0, remaining)

    def _ph_pulse_seconds(self, ph: float, now: datetime) -> float:
        s = self.settings
        st = self.state
        if s.ph_dosing_mode is PhDosingMode.PROPORTIONAL:
            step = min(ph - st.ph_target, PH_PROPORTIONAL_MAX_STEP)
            dose = chemistry.ph_dose_ml(s.volume, step, self.ph_product_dose)
            seconds = chemistry.pump_seconds_for_dose(dose, self.ph_pump_rate)
            seconds = max(PH_PULSE_MIN_SECONDS, min(seconds, s.ph_pulse_s))
        else:
            seconds = s.ph_pulse_s
        remaining_ml = self.ph_remaining_ml(now)
        return min(seconds, chemistry.pump_seconds_for_dose(remaining_ml, self.ph_pump_rate))

    def _decide_ph(self, snap: Snapshot, decision: Decision) -> None:
        s = self.settings
        st = self.state
        now = snap.now
        if not s.has_ph_pump:
            return
        m = decision.measurement
        if snap.ph_pump_on:
            overrun = minutes_between(st.last_ph_pulse, now) * 60 > (
                s.ph_pulse_s + PH_PULSE_OVERRUN_SECONDS
            )
            if not self._flow(snap):
                decision.ph_pump_stop, decision.ph_pulse_reason = True, "interlock"
            elif m.ph is not None and m.primary_valid and m.ph < s.ph_min_safe:
                decision.ph_pump_stop, decision.ph_pulse_reason = True, "ph_too_low"
            elif overrun:
                decision.ph_pump_stop, decision.ph_pulse_reason = True, "overrun"
            decision.ph_blocked_reason = "pulse_running"
            return

        reason = self.ph_blocked_reason(snap, m)
        decision.ph_blocked_reason = reason
        if reason is not None or m.ph is None:
            return
        seconds = self._ph_pulse_seconds(m.ph, now)
        if seconds < PH_PULSE_MIN_SECONDS:
            decision.ph_blocked_reason = "limit"
            return
        decision.ph_pulse_seconds = round(seconds, 1)
        decision.ph_pulse_reason = "ph_high"

    def _end_ph_session(self) -> None:
        self.state.ph_session_start_ph = None
        self.state.ph_session_ml = 0.0
        self.state.ph_session_last_pulse = None

    def _check_ph_session(self, now: datetime, m: Measurement) -> None:
        """Verify that dosing lowers the pH and learn the product dose."""
        s = self.settings
        st = self.state
        if st.ph_session_start_ph is None:
            return
        if (
            st.ph_session_last_pulse is not None
            and now - st.ph_session_last_pulse > PH_SESSION_TIMEOUT
        ):
            self._end_ph_session()
            return
        if not m.primary_valid or m.ph is None:
            return
        if st.ph_lockout_until is not None and now < st.ph_lockout_until:
            return
        drop = st.ph_session_start_ph - m.ph
        if m.ph <= st.ph_target + s.ph_deadband:
            observed = chemistry.product_dose_from_observation(s.volume, st.ph_session_ml, drop)
            if observed is not None and drop >= PH_SUCCESS_MIN_DROP:
                previous = st.ph_product_dose_learned
                st.ph_product_dose_learned = round(
                    observed
                    if previous is None
                    else previous + LEARNING_WEIGHT * (observed - previous),
                    1,
                )
            self._end_ph_session()
            return
        expected = chemistry.ph_drop_for_dose(s.volume, st.ph_session_ml, s.ph_product_dose)
        if expected >= s.ph_no_effect_drop and drop < PH_SUCCESS_MIN_DROP:
            st.ph_dosing_locked = True

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------
    def _swimming_status(self, now: datetime, m: Measurement) -> SwimmingStatus:
        s = self.settings
        st = self.state
        ph, orp = m.ph, m.orp
        recent = minutes_between(st.last_valid_measurement, now) <= s.swim_data_max_age_h * 60
        if (ph is None or orp is None) and recent:
            ph, orp = st.last_valid_ph, st.last_valid_orp
        if ph is None or orp is None:
            return SwimmingStatus.NO_DATA
        if minutes_between(st.last_ph_pulse, now) < SWIM_DOSING_BLOCK_MINUTES:
            return SwimmingStatus.DOSING
        if self.shock_active(now):
            return SwimmingStatus.SHOCK
        if ph < s.swim_ph_min:
            return SwimmingStatus.PH_LOW
        if ph > s.swim_ph_max:
            return SwimmingStatus.PH_HIGH
        if orp < s.swim_orp_min:
            return SwimmingStatus.ORP_LOW
        return SwimmingStatus.OK

    def _problems(self, snap: Snapshot, m: Measurement) -> set[Problem]:
        s = self.settings
        st = self.state
        problems: set[Problem] = set()
        if snap.pump_on and snap.flow_ok is False:
            problems.add(Problem.NO_FLOW)
        if self._sensor_stuck:
            problems.add(Problem.SENSOR_STUCK)
        if self._sensors_deviate(snap, m):
            problems.add(Problem.SENSOR_DEVIATION)
        if (m.ph is not None and not ALARM_PH_MIN <= m.ph <= ALARM_PH_MAX) or (
            m.orp is not None and m.orp < ALARM_ORP_MIN
        ):
            problems.add(Problem.WATER_QUALITY)
        if m.primary_valid and m.ph is not None and m.ph < s.ph_min_safe:
            problems.add(Problem.PH_TOO_LOW)
        if s.has_ph_pump:
            if st.ph_dosing_locked:
                problems.add(Problem.PH_DOSING_LOCKED)
            if st.ph_dosed_today_ml >= s.ph_max_daily_ml:
                problems.add(Problem.PH_DAILY_LIMIT)
            if st.tank_level_ml is not None:
                if st.tank_level_ml <= 0:
                    problems.add(Problem.PH_TANK_EMPTY)
                elif st.tank_level_ml <= s.tank_warn_ml:
                    problems.add(Problem.PH_TANK_LOW)
        if s.has_chlorinator:
            if self._chlorinator_ineffective(snap, m):
                problems.add(Problem.CHLORINATOR_NO_EFFECT)
            if st.chlorinator_runtime_today_s >= s.chlor_max_daily_h * 3600:
                problems.add(Problem.CHLORINATOR_DAILY_LIMIT)
        salt = snap.salt
        if (
            salt.value is not None
            and minutes_between(salt.last_reported, snap.now) <= SALT_MAX_AGE_HOURS * 60
        ):
            if salt.value < s.salt_min:
                problems.add(Problem.SALT_LOW)
            elif salt.value > s.salt_max:
                problems.add(Problem.SALT_HIGH)
        if snap.outdoor_configured and snap.outdoor_temperature is None:
            problems.add(Problem.OUTDOOR_TEMP_UNAVAILABLE)
        return problems

    def _status(self, snap: Snapshot) -> Status:
        st = self.state
        mode = st.operating_mode
        if mode is OperatingMode.OFF:
            return Status.OFF
        if st.frost_active and snap.pump_on:
            return Status.FROST_PROTECTION
        if mode is OperatingMode.WINTER:
            return Status.WINTER
        if mode is OperatingMode.MAINTENANCE:
            return Status.MAINTENANCE
        if snap.ph_pump_on:
            return Status.DOSING
        if snap.chlorinator_on:
            return Status.CHLORINATING
        if snap.pump_on:
            if minutes_between(st.pump_on_since, snap.now) < self.settings.stabilization_min:
                return Status.STABILIZING
            return Status.FILTERING
        return Status.IDLE
