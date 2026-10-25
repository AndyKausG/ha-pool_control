"""Tests for the pool controller logic."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from custom_components.pool_control.const import (
    MeasurementSource,
    OperatingMode,
    Problem,
    Status,
    SwimmingStatus,
)
from custom_components.pool_control.controller import PoolController, in_time_window
from custom_components.pool_control.models import Reading, RuntimeState, Settings, Snapshot

TZ = ZoneInfo("Europe/Berlin")
NOON = datetime(2026, 7, 1, 12, 0, tzinfo=TZ)

BASE_OPTIONS: dict[str, Any] = {
    "pump": "switch.pump",
    "chlorinator": "switch.chlorinator",
    "ph_pump": "switch.ph_pump",
}


def make_controller(state: RuntimeState | None = None, **options: Any) -> PoolController:
    """Return a controller with default settings and optional overrides."""
    return PoolController(
        Settings.from_options({**BASE_OPTIONS, **options}), state or RuntimeState()
    )


def reading(value: float | None, now: datetime, changed_minutes: float = 1) -> Reading:
    """Return a fresh reading."""
    return Reading(value, now, now - timedelta(minutes=changed_minutes))


def snap(
    now: datetime = NOON,
    *,
    pump: bool = True,
    chlorinator: bool = False,
    ph_pump: bool = False,
    ph: float | None = 7.2,
    orp: float | None = 760,
    temp: float | None = 26.0,
    **kwargs: Any,
) -> Snapshot:
    """Return a snapshot with valid primary readings."""
    return Snapshot(
        now=now,
        pump_on=pump,
        chlorinator_on=chlorinator,
        ph_pump_on=ph_pump,
        ph=reading(ph, now),
        orp=reading(orp, now),
        temperature=reading(temp, now),
        **kwargs,
    )


def running(minutes: float = 60, now: datetime = NOON, **state: Any) -> RuntimeState:
    """Return a state where the pump has been running for some minutes."""
    return RuntimeState(
        pump_on_since=now - timedelta(minutes=minutes),
        chlorinator_off_since=now - timedelta(hours=2),
        day=now.date().isoformat(),
        **state,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "start", "end", "expected"),
    [
        ("12:00", "08:00", "22:00", True),
        ("07:59", "08:00", "22:00", False),
        ("22:00", "08:00", "22:00", False),
        ("23:00", "22:00", "07:00", True),
        ("06:59", "22:00", "07:00", True),
        ("07:00", "22:00", "07:00", False),
        ("12:00", "08:00", "08:00", False),
    ],
)
def test_in_time_window(now: str, start: str, end: str, expected: bool) -> None:
    from custom_components.pool_control.models import parse_time

    assert in_time_window(parse_time(now), parse_time(start), parse_time(end)) is expected


# ---------------------------------------------------------------------------
# Measurement validity
# ---------------------------------------------------------------------------


def test_measurement_valid_after_stabilization() -> None:
    decision = make_controller(running(31)).step(snap())
    assert decision.measurement.primary_valid
    assert decision.measurement.source is MeasurementSource.PRIMARY
    assert decision.measurement.ph == 7.2


def test_measurement_invalid_while_stabilizing() -> None:
    decision = make_controller(running(10)).step(snap())
    assert not decision.measurement.primary_valid
    assert decision.measurement.invalid_reason == "stabilizing"
    assert decision.status is Status.STABILIZING


def test_measurement_invalid_when_pump_off() -> None:
    decision = make_controller(RuntimeState(mode="manual")).step(snap(pump=False))
    assert decision.measurement.invalid_reason == "pump_off"
    assert decision.measurement.source is MeasurementSource.NONE


def test_measurement_invalid_without_flow() -> None:
    decision = make_controller(running()).step(snap(flow_ok=False))
    assert decision.measurement.invalid_reason == "no_flow"
    assert Problem.NO_FLOW in decision.problems


@pytest.mark.parametrize(("ph", "orp"), [(3.0, 760), (7.2, 1500), (None, 760)])
def test_measurement_invalid_values(ph: float | None, orp: float | None) -> None:
    decision = make_controller(running()).step(snap(ph=ph, orp=orp))
    assert not decision.measurement.primary_valid


def test_measurement_stale() -> None:
    stale = Reading(7.2, NOON - timedelta(minutes=10), NOON - timedelta(minutes=10))
    decision = make_controller(running()).step(replace(snap(), ph=stale))
    assert decision.measurement.invalid_reason == "stale"


def test_measurement_stuck() -> None:
    stuck = Reading(7.2, NOON, NOON - timedelta(minutes=90))
    decision = make_controller(running(120)).step(replace(snap(), ph=stuck))
    assert decision.measurement.invalid_reason == "stuck"
    assert Problem.SENSOR_STUCK in decision.problems


def test_backup_sensor_used_when_pump_off() -> None:
    now = NOON
    decision = make_controller(RuntimeState(mode="manual")).step(
        snap(
            pump=False,
            backup_ph=Reading(7.4, now - timedelta(minutes=30)),
            backup_orp=Reading(700, now - timedelta(minutes=30)),
        )
    )
    assert decision.measurement.source is MeasurementSource.BACKUP
    assert decision.measurement.ph == 7.4
    assert not decision.measurement.primary_valid


def test_backup_sensor_ignored_when_too_old() -> None:
    now = NOON
    decision = make_controller(RuntimeState(mode="manual")).step(
        snap(pump=False, backup_ph=Reading(7.4, now - timedelta(hours=5)))
    )
    assert decision.measurement.source is MeasurementSource.NONE


def test_water_quality_alarm_from_backup() -> None:
    now = NOON
    decision = make_controller(RuntimeState(mode="manual")).step(
        snap(pump=False, backup_ph=Reading(8.5, now))
    )
    assert Problem.WATER_QUALITY in decision.problems


# ---------------------------------------------------------------------------
# Filtration
# ---------------------------------------------------------------------------


def test_filtration_target_from_yesterday_mean() -> None:
    controller = make_controller(RuntimeState(temp_mean_yesterday=24.0))
    assert controller.filtration_target_hours() == 12.0
    controller.state.temp_mean_yesterday = 16.0
    assert controller.filtration_target_hours() == 8.0
    controller.state.temp_mean_yesterday = 2.0
    assert controller.filtration_target_hours() == 2.0


def test_filtration_target_fallback() -> None:
    controller = make_controller()
    assert controller.filtration_target_hours() == 10.0


def test_schedule_starts_pump_in_first_slot() -> None:
    now = datetime(2026, 7, 1, 8, 0, tzinfo=TZ)
    state = RuntimeState(temp_mean_yesterday=16.0, day=now.date().isoformat())
    decision = make_controller(state).step(snap(now, pump=False))
    assert decision.pump is True
    assert decision.pump_reason == "schedule"


def test_schedule_stops_when_slot_quota_reached() -> None:
    # Target 8 h, 2 slots of 7 h in 08-22: quota of slot 1 is 4 h.
    now = datetime(2026, 7, 1, 12, 5, tzinfo=TZ)
    state = running(
        245,
        now,
        temp_mean_yesterday=16.0,
        pump_runtime_today_s=4 * 3600,
        last_accumulated=now,
    )
    decision = make_controller(state).step(snap(now))
    assert decision.pump is False
    assert decision.pump_reason == "schedule_done"


def test_schedule_second_slot_and_catch_up() -> None:
    now = datetime(2026, 7, 1, 15, 0, tzinfo=TZ)
    state = RuntimeState(
        temp_mean_yesterday=16.0, pump_runtime_today_s=3600, day=now.date().isoformat()
    )
    controller = make_controller(state)
    decision = controller.step(snap(now, pump=False))
    assert decision.pump is True


def test_schedule_does_not_start_for_short_remainder() -> None:
    now = datetime(2026, 7, 1, 16, 0, tzinfo=TZ)
    state = RuntimeState(
        temp_mean_yesterday=16.0,
        pump_runtime_today_s=8 * 3600 - 300,
        day=now.date().isoformat(),
    )
    decision = make_controller(state).step(snap(now, pump=False))
    assert decision.pump is False


def test_chlorinator_stops_before_pump() -> None:
    now = datetime(2026, 7, 1, 23, 0, tzinfo=TZ)
    state = running(60, now, chlorinator_on_since=now - timedelta(minutes=40))
    controller = make_controller(state)
    decision = controller.step(snap(now, chlorinator=True, orp=700))
    assert decision.chlorinator is False
    assert decision.chlorinator_reason == "pump_stopping"
    assert decision.pump is None
    decision = controller.step(snap(now + timedelta(minutes=1)))
    assert decision.pump is False


def test_ph_pump_stops_before_pump() -> None:
    now = datetime(2026, 7, 1, 23, 0, tzinfo=TZ)
    state = running(60, now, last_ph_pulse=now - timedelta(seconds=10))
    decision = make_controller(state).step(snap(now, ph_pump=True))
    assert decision.ph_pump_stop
    assert decision.pump is None


def test_outside_window_pump_off() -> None:
    now = datetime(2026, 7, 1, 23, 0, tzinfo=TZ)
    state = running(60, now)
    decision = make_controller(state).step(snap(now))
    assert decision.pump is False
    assert decision.pump_reason == "outside_window"


def test_next_filtration_start() -> None:
    now = datetime(2026, 7, 1, 6, 0, tzinfo=TZ)
    decision = make_controller().step(snap(now, pump=False))
    assert decision.next_filtration_start == datetime(2026, 7, 1, 8, 0, tzinfo=TZ)
    now = datetime(2026, 7, 1, 23, 0, tzinfo=TZ)
    decision = make_controller().step(snap(now, pump=False))
    assert decision.next_filtration_start == datetime(2026, 7, 2, 8, 0, tzinfo=TZ)


def test_demand_extension_while_chlorinating() -> None:
    now = datetime(2026, 7, 1, 12, 5, tzinfo=TZ)
    state = running(
        245,
        now,
        temp_mean_yesterday=16.0,
        pump_runtime_today_s=4 * 3600,
        last_accumulated=now,
        chlorinator_on_since=now - timedelta(minutes=10),
    )
    decision = make_controller(state).step(snap(now, chlorinator=True, orp=700))
    assert decision.pump is True
    assert decision.pump_reason == "demand_extension"


def test_demand_extension_disabled() -> None:
    now = datetime(2026, 7, 1, 12, 5, tzinfo=TZ)
    state = running(
        245,
        now,
        temp_mean_yesterday=16.0,
        pump_runtime_today_s=4 * 3600,
        last_accumulated=now,
        chlorinator_on_since=now - timedelta(minutes=10),
    )
    controller = make_controller(state, demand_extension=False)
    decision = controller.step(snap(now, chlorinator=True, orp=700))
    assert decision.chlorinator is False
    assert decision.pump_reason == "post_run"


def test_manual_mode_does_not_touch_pump() -> None:
    decision = make_controller(running(mode="manual")).step(snap())
    assert decision.pump is None


def test_off_mode_does_not_touch_pump() -> None:
    decision = make_controller(running(mode="off")).step(snap())
    assert decision.pump is None
    assert decision.status is Status.OFF


def test_boost_in_manual_mode() -> None:
    controller = make_controller(RuntimeState(mode="manual"))
    controller.start_boost(NOON, 2)
    decision = controller.step(snap(pump=False))
    assert decision.pump is True
    assert decision.pump_reason == "boost"
    later = NOON + timedelta(hours=3)
    decision = controller.step(snap(later))
    assert decision.pump is False
    assert decision.pump_reason == "boost_finished"
    assert controller.step(snap(later, pump=False)).pump is None


def test_boost_in_auto_mode_overrides_schedule() -> None:
    now = datetime(2026, 7, 1, 23, 0, tzinfo=TZ)
    controller = make_controller()
    controller.start_boost(now)
    decision = controller.step(snap(now, pump=False))
    assert decision.pump is True
    controller.stop_boost()
    assert controller.step(snap(now)).pump is False


def test_runtime_accumulation_and_day_rollover() -> None:
    start = datetime(2026, 7, 1, 23, 0, tzinfo=TZ)
    controller = make_controller(RuntimeState(mode="manual"))
    controller.step(snap(start))
    controller.step(snap(start + timedelta(minutes=30)))
    assert controller.state.pump_runtime_today_s == pytest.approx(1800)
    controller.step(snap(start + timedelta(minutes=31)))
    controller.state.temp_sum_today = 50
    controller.state.temp_count_today = 2
    controller.step(snap(start + timedelta(hours=1, minutes=1)))
    assert controller.state.day == "2026-07-02"
    assert controller.state.temp_mean_yesterday == 25.0
    assert controller.state.pump_runtime_today_s < 1800


# ---------------------------------------------------------------------------
# Frost protection
# ---------------------------------------------------------------------------


def test_frost_protection_interval() -> None:
    now = datetime(2026, 1, 10, 3, 5, tzinfo=TZ)
    controller = make_controller(RuntimeState(mode="winter"))
    decision = controller.step(snap(now, pump=False, outdoor_temperature=-3.0))
    assert controller.state.frost_active
    assert decision.pump is True
    assert decision.pump_reason == "frost_protection"
    decision = controller.step(snap(now.replace(minute=30), outdoor_temperature=-3.0))
    assert decision.pump is False


def test_frost_protection_continuous_and_hysteresis() -> None:
    now = datetime(2026, 1, 10, 3, 30, tzinfo=TZ)
    controller = make_controller(RuntimeState(mode="winter"), frost_mode="continuous")
    assert controller.step(snap(now, pump=False, outdoor_temperature=1.0)).pump is True
    assert controller.step(snap(now, outdoor_temperature=2.5)).pump is True
    assert controller.step(snap(now, outdoor_temperature=3.5)).pump is False


def test_frost_protection_not_in_off_mode() -> None:
    now = datetime(2026, 1, 10, 3, 5, tzinfo=TZ)
    decision = make_controller(RuntimeState(mode="off")).step(
        snap(now, pump=False, outdoor_temperature=-5.0)
    )
    assert decision.pump is None


def test_frost_protection_in_maintenance_mode() -> None:
    now = datetime(2026, 1, 10, 3, 5, tzinfo=TZ)
    controller = make_controller(RuntimeState(mode="maintenance"))
    decision = controller.step(snap(now, pump=False, outdoor_temperature=-5.0))
    assert decision.pump is True
    decision = controller.step(snap(now, outdoor_temperature=10.0))
    assert decision.pump is False


def test_outdoor_temperature_unavailable_problem() -> None:
    decision = make_controller(running()).step(snap(outdoor_configured=True))
    assert Problem.OUTDOOR_TEMP_UNAVAILABLE in decision.problems


# ---------------------------------------------------------------------------
# Chlorination
# ---------------------------------------------------------------------------


def test_orp_target_ph_compensated() -> None:
    decision = make_controller(running()).step(snap(ph=7.2))
    assert decision.orp_target == 763


def test_orp_target_fixed() -> None:
    decision = make_controller(running(), orp_target_mode="fixed").step(snap())
    assert decision.orp_target == 735


def test_chlorinator_switches_on_when_orp_low() -> None:
    decision = make_controller(running()).step(snap(orp=740))
    assert decision.chlorinator is True
    assert decision.chlorinator_reason == "orp_low"


def test_chlorinator_stays_off_within_hysteresis() -> None:
    decision = make_controller(running()).step(snap(orp=755))
    assert decision.chlorinator is None


def test_chlorinator_respects_min_off_time() -> None:
    state = running()
    state.chlorinator_off_since = NOON - timedelta(minutes=5)
    assert make_controller(state).step(snap(orp=700)).chlorinator is None


def test_chlorinator_not_while_stabilizing() -> None:
    assert make_controller(running(10)).step(snap(orp=700)).chlorinator is None


def test_chlorinator_off_when_target_reached_after_min_on() -> None:
    state = running(chlorinator_on_since=NOON - timedelta(minutes=40))
    decision = make_controller(state).step(snap(chlorinator=True, orp=790))
    assert decision.chlorinator is False
    assert decision.chlorinator_reason == "target_reached"


def test_chlorinator_min_on_time() -> None:
    state = running(chlorinator_on_since=NOON - timedelta(minutes=10))
    assert make_controller(state).step(snap(chlorinator=True, orp=790)).chlorinator is None


def test_chlorinator_interlock_when_pump_off() -> None:
    state = RuntimeState(mode="manual", chlorinator_on_since=NOON)
    decision = make_controller(state).step(snap(pump=False, chlorinator=True))
    assert decision.chlorinator is False
    assert decision.chlorinator_reason == "interlock"


def test_chlorinator_off_when_measurement_invalid() -> None:
    state = running(chlorinator_on_since=NOON - timedelta(minutes=5))
    decision = make_controller(state).step(snap(chlorinator=True, orp=None))
    assert decision.chlorinator is False
    assert decision.chlorinator_reason == "measurement_invalid"


def test_chlorinator_off_when_disabled() -> None:
    state = running(chlorine_control_enabled=False, chlorinator_on_since=NOON)
    decision = make_controller(state).step(snap(chlorinator=True))
    assert decision.chlorinator_reason == "disabled"


def test_chlorinator_daily_limit() -> None:
    state = running(chlorinator_runtime_today_s=12 * 3600, last_accumulated=NOON)
    decision = make_controller(state).step(snap(orp=700))
    assert decision.chlorinator is None
    assert Problem.CHLORINATOR_DAILY_LIMIT in decision.problems


def test_chlorinator_holdoff_after_ph_pulse() -> None:
    state = running(last_ph_pulse=NOON - timedelta(minutes=5))
    assert make_controller(state).step(snap(orp=700)).chlorinator is None


def test_chlorinator_no_effect_problem() -> None:
    state = running(
        240,
        chlorinator_on_since=NOON - timedelta(hours=4),
        chlorinator_start_orp=700,
    )
    decision = make_controller(state).step(snap(chlorinator=True, orp=705))
    assert Problem.CHLORINATOR_NO_EFFECT in decision.problems


def test_no_chlorinator_configured() -> None:
    controller = PoolController(Settings.from_options({"pump": "switch.pump"}), running())
    assert controller.step(snap(orp=600)).chlorinator is None


# ---------------------------------------------------------------------------
# pH dosing
# ---------------------------------------------------------------------------


def test_ph_pulse_when_ph_high() -> None:
    decision = make_controller(running()).step(snap(ph=7.4))
    assert decision.ph_pulse_seconds == 50
    assert decision.ph_pulse_reason == "ph_high"


@pytest.mark.parametrize(
    ("state_overrides", "ph", "now", "reason"),
    [
        ({}, 7.24, NOON, "in_range"),
        ({"mode": "maintenance"}, 7.5, NOON, "mode"),
        ({"ph_control_enabled": False}, 7.5, NOON, "disabled"),
        ({"ph_dosing_locked": True}, 7.5, NOON, "locked"),
        ({"ph_lockout_until": NOON + timedelta(minutes=5)}, 7.5, NOON, "lockout"),
        ({"ph_dosed_today_ml": 1500}, 7.5, NOON, "daily_limit"),
        ({"tank_level_ml": 0}, 7.5, NOON, "tank_empty"),
        ({}, 7.5, datetime(2026, 7, 1, 22, 30, tzinfo=TZ), "quiet_hours"),
    ],
)
def test_ph_pulse_blocked(
    state_overrides: dict[str, Any], ph: float, now: datetime, reason: str
) -> None:
    state = running(60, now, **state_overrides)
    decision = make_controller(state).step(snap(now, ph=ph))
    assert decision.ph_pulse_seconds == 0
    assert decision.ph_blocked_reason == reason


def test_ph_pulse_blocked_below_safety_minimum() -> None:
    state = running(ph_target=6.0)
    decision = make_controller(state).step(snap(ph=6.7))
    assert decision.ph_blocked_reason == "ph_too_low"
    assert Problem.PH_TOO_LOW in decision.problems


def test_ph_pulse_proportional_length() -> None:
    controller = make_controller(running(), ph_dosing_mode="proportional")
    # Step capped to 0.1 pH: 300 * 1.72 = 516 ml -> 1474 s, capped to the pulse length
    decision = controller.step(snap(ph=7.4))
    assert decision.ph_pulse_seconds == 50
    controller = make_controller(running(), ph_dosing_mode="proportional", ph_product_dose=10)
    decision = controller.step(snap(ph=7.26))
    # 0.06 pH -> 10 * 1.72 * 0.6 = 10.32 ml at 21 ml/min = 29.5 s
    assert decision.ph_pulse_seconds == pytest.approx(29.5, abs=0.1)


def test_ph_pulse_limited_by_remaining_daily_amount() -> None:
    state = running(ph_dosed_today_ml=1490)
    decision = make_controller(state).step(snap(ph=7.5))
    assert decision.ph_pulse_seconds == pytest.approx(28.6, abs=0.1)


def test_ph_pulse_too_short_remaining() -> None:
    state = running(ph_dosed_today_ml=1499.5)
    decision = make_controller(state).step(snap(ph=7.5))
    assert decision.ph_pulse_seconds == 0
    assert decision.ph_blocked_reason == "daily_limit"


def test_ph_pump_stopped_by_interlock() -> None:
    state = RuntimeState(mode="manual", last_ph_pulse=NOON)
    decision = make_controller(state).step(snap(pump=False, ph_pump=True))
    assert decision.ph_pump_stop
    assert decision.ph_pulse_reason == "interlock"


def test_ph_pump_stopped_on_overrun() -> None:
    state = running(last_ph_pulse=NOON - timedelta(minutes=5))
    decision = make_controller(state).step(snap(ph_pump=True))
    assert decision.ph_pump_stop
    assert decision.ph_pulse_reason == "overrun"
    assert decision.status is Status.DOSING


def test_ph_pump_running_normally() -> None:
    state = running(last_ph_pulse=NOON - timedelta(seconds=20))
    decision = make_controller(state).step(snap(ph_pump=True, ph=7.4))
    assert not decision.ph_pump_stop
    assert decision.ph_pulse_seconds == 0


def test_register_and_record_dose() -> None:
    controller = make_controller(running(tank_level_ml=1000, last_valid_ph=7.5))
    controller.register_ph_pulse_start(NOON, 50)
    assert controller.state.ph_lockout_until == NOON + timedelta(seconds=50, minutes=10)
    assert controller.state.ph_session_start_ph == 7.5
    dose = controller.record_ph_dose(60)
    assert dose == pytest.approx(21)
    state = controller.state
    assert state.ph_dosed_today_ml == pytest.approx(21)
    assert state.ph_dosed_season_ml == pytest.approx(21)
    assert state.tank_level_ml == pytest.approx(979)
    assert state.ph_pulses_today == 1
    assert state.ph_pump_seconds_since_refill == 60


def test_tank_refill_calibrates_rate() -> None:
    controller = make_controller(running(ph_pump_seconds_since_refill=600))
    controller.tank_refilled(300, None)
    assert controller.state.ph_pump_rate_calibrated == 30
    assert controller.ph_pump_rate == 30
    assert controller.state.tank_level_ml == 5000
    assert controller.state.ph_pump_seconds_since_refill == 0
    controller.tank_refilled(None, 2500)
    assert controller.state.ph_pump_rate_calibrated == 30
    assert controller.state.tank_level_ml == 2500


def test_tank_problems() -> None:
    decision = make_controller(running(tank_level_ml=400)).step(snap())
    assert Problem.PH_TANK_LOW in decision.problems
    decision = make_controller(running(tank_level_ml=0)).step(snap())
    assert Problem.PH_TANK_EMPTY in decision.problems


def test_ph_session_locks_without_effect() -> None:
    state = running(
        ph_session_start_ph=7.5,
        ph_session_ml=800,
        ph_session_last_pulse=NOON - timedelta(minutes=30),
        ph_lockout_until=NOON - timedelta(minutes=1),
    )
    controller = make_controller(state)
    decision = controller.step(snap(ph=7.49))
    assert controller.state.ph_dosing_locked
    assert Problem.PH_DOSING_LOCKED in decision.problems
    controller.reset_ph_lock()
    assert not controller.state.ph_dosing_locked
    assert controller.state.ph_session_start_ph is None


def test_ph_session_learns_product_dose() -> None:
    state = running(
        ph_session_start_ph=7.5,
        ph_session_ml=516,
        ph_session_last_pulse=NOON - timedelta(minutes=30),
    )
    controller = make_controller(state)
    controller.step(snap(ph=7.2))
    # 516 ml lowered 17.2 m3 by 0.3 pH -> 100 ml / 10 m3 / 0.1 pH
    assert controller.state.ph_product_dose_learned == pytest.approx(100, abs=0.5)
    assert controller.state.ph_session_start_ph is None


def test_ph_session_times_out() -> None:
    state = running(
        ph_session_start_ph=7.5,
        ph_session_ml=50,
        ph_session_last_pulse=NOON - timedelta(hours=25),
    )
    controller = make_controller(state)
    controller.step(snap(ph=7.5))
    assert controller.state.ph_session_start_ph is None


def test_learned_dose_used_in_proportional_mode() -> None:
    controller = make_controller(
        running(ph_product_dose_learned=500.0), ph_dosing_mode="proportional"
    )
    assert controller.ph_product_dose == 500
    controller = make_controller(running(ph_product_dose_learned=500.0))
    assert controller.ph_product_dose == 300


def test_manual_pulse_blocked_reasons() -> None:
    controller = make_controller(running())
    m = controller.step(snap(ph=7.2)).measurement
    assert controller.manual_pulse_blocked_reason(snap(ph=7.2), m) is None
    assert controller.manual_pulse_blocked_reason(snap(pump=False), m) == "pump_off"
    controller.state.ph_dosing_locked = True
    assert controller.manual_pulse_blocked_reason(snap(), m) == "locked"


# ---------------------------------------------------------------------------
# Swimming and salt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ph", "orp", "expected"),
    [
        (7.2, 760, SwimmingStatus.OK),
        (6.9, 760, SwimmingStatus.PH_LOW),
        (7.9, 760, SwimmingStatus.PH_HIGH),
        (7.2, 620, SwimmingStatus.ORP_LOW),
    ],
)
def test_swimming_status(ph: float, orp: float, expected: SwimmingStatus) -> None:
    assert make_controller(running()).step(snap(ph=ph, orp=orp)).swimming is expected


def test_swimming_uses_recent_values_when_pump_off() -> None:
    state = RuntimeState(
        mode="manual",
        last_valid_measurement=NOON - timedelta(hours=2),
        last_valid_ph=7.2,
        last_valid_orp=760,
    )
    assert make_controller(state).step(snap(pump=False)).swimming is SwimmingStatus.OK
    state.last_valid_measurement = NOON - timedelta(hours=8)
    assert make_controller(state).step(snap(pump=False)).swimming is SwimmingStatus.NO_DATA


def test_swimming_blocked_after_dosing() -> None:
    state = running(last_ph_pulse=NOON - timedelta(minutes=10))
    assert make_controller(state).step(snap()).swimming is SwimmingStatus.DOSING


@pytest.mark.parametrize(("salt", "problem"), [(2000, Problem.SALT_LOW), (5000, Problem.SALT_HIGH)])
def test_salt_problems(salt: float, problem: Problem) -> None:
    decision = make_controller(running()).step(snap(salt=Reading(salt, NOON)))
    assert problem in decision.problems


def test_salt_ignored_when_old() -> None:
    decision = make_controller(running()).step(snap(salt=Reading(2000, NOON - timedelta(days=3))))
    assert Problem.SALT_LOW not in decision.problems


# ---------------------------------------------------------------------------
# Status and persistence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "kwargs", "expected"),
    [
        (OperatingMode.WINTER, {"pump": False}, Status.WINTER),
        (OperatingMode.MAINTENANCE, {}, Status.MAINTENANCE),
        (OperatingMode.AUTO, {"chlorinator": True}, Status.CHLORINATING),
        (OperatingMode.AUTO, {}, Status.FILTERING),
        (OperatingMode.MANUAL, {"pump": False}, Status.IDLE),
    ],
)
def test_status(mode: OperatingMode, kwargs: dict[str, Any], expected: Status) -> None:
    state = running(mode=mode.value, chlorinator_on_since=NOON)
    assert make_controller(state).step(snap(**kwargs)).status is expected


def test_state_roundtrip() -> None:
    state = running(ph_lockout_until=NOON, tank_level_ml=100.0)
    restored = RuntimeState.from_dict({**state.to_dict(), "unknown": 1})
    assert restored == state
