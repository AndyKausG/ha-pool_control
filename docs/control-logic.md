# Control logic

The controller runs every 60 seconds and on every change of a configured
sensor or switch (debounced to at most one run per 10 seconds). Each run
evaluates the measurement, decides the state of each actuator, executes the
decision and records the reason in the logbook.

## Operating modes

| Mode | Filter pump | Chlorination / pH dosing | Frost protection |
|---|---|---|---|
| Automatic | Schedule, demand extension, extra circulation | active | yes |
| Manual | User; extra circulation possible | active while the pump runs | yes |
| Maintenance | User; extra circulation possible | locked | yes |
| Winter | Off | locked | yes |
| Off | not touched | locked | no |

The interlock (see below) is active in every mode, including dry run.

In *Manual* and *Maintenance* the controller only switches the pump on for
frost protection or an extra circulation and switches it off again when that
ends. In *Automatic* and *Winter* the controller owns the pump: a pump switched
on by hand outside the schedule is switched off on the next run.

## Measurement

Primary readings (pH, ORP, water temperature) come from sensors in the flow
cell. They are **valid** only if all conditions hold:

1. The filter pump is on and, if configured, the flow sensor reports flow
   (or the pump power is above the minimum).
2. The pump has been running for the stabilization time (default 30 min).
3. pH is within 4.0-9.0 and ORP within 200-1000 mV.
4. The last report is not older than the maximum age (default 5 min).
5. The value has changed within the stuck detection time (default 60 min,
   only checked once the pump has run that long).

Chlorination and pH dosing use valid primary readings only.

If the primary readings are invalid, backup sensors (for example a floating
probe) are used for display, water quality alarms and the swimming assessment,
as long as their last report is not older than the backup maximum age.

**Water temperature** is handled separately: a sensor in a pipe shows the
pool temperature only while water flows, but it needs only a few minutes, not
the full stabilization time. The water temperature of the filter circuit is
therefore valid after 5 minutes of flow. While no water flows, the last valid
value is used where a pool temperature is needed (the pool temperature changes
slowly).

The mean of all valid water temperatures of a day is the reference for the
filtration target of the next day.

## Filtration

**Daily target** = water temperature / divisor (default 2), limited to the
configured minimum and maximum. Example: 24 °C gives 12 h, 16 °C gives 8 h.

The filtration window (default 08:00-22:00) is divided into equally sized
slots, one per block (default 2). In slot *i* the pump runs until the run time
of the day reaches *(i + 1) / n* of the target.

- Run time from manual runs or frost protection counts towards the target.
- Missed run time is caught up in the following slots.
- The pump is not started for less than 15 minutes.

**Other reasons to run:** PV surplus and solar heating (see below), extra
circulation and frost protection.

**Demand extension:** while the chlorinator runs or the pH is above the set
point and dosing is possible, the pump keeps running inside the window up to
the daily maximum.

**Post run:** before the pump is switched off, chlorinator and dosing pump are
switched off and the pump runs until the next controller run (about one
minute) to flush the cell.

**Extra circulation:** runs the pump for the configured duration on top of
the schedule, for example after adding chemicals by hand.

## Solar heating

Solar heating means heating the pool water with a solar absorber. It is
independent of a photovoltaic system (see PV surplus below).

Two ways to control the absorber:

- **Differential control** (absorber temperature sensor configured): solar
  heating starts when the absorber is at least the switch-on difference
  (default 6 K) warmer than the pool water and stops when the difference falls
  below the switch-off difference (default 3 K) or the water reaches the
  maximum temperature (default 30 °C).

  Pool water temperature for the differential, in this order:
  1. Sensor in the solar circuit before the absorber, after the absorber pump
     has run for 5 minutes
  2. Sensor in the filter circuit, after the filter pump has run for 5 minutes
  3. Last valid value of one of these sensors

  The absorber sensor on the roof is always valid.

  **No cycling:** when the absorber pump starts, cold pool water cools the
  absorber and the difference collapses for a while. A minimum run time
  (default 15 min) bridges this phase, a minimum pause (default 10 min)
  prevents an immediate restart. Together with the hysteresis between
  switch-on and switch-off difference this avoids short cycles.
- **External signal** (demand signal configured): the switching output of an
  existing solar heating controller, for example read by a Shelly input, is
  used as demand.

If an absorber pump or valve is configured, it is switched according to the
demand.

*Solar absorber in the filter circuit* describes the piping:

- **Off (default):** the absorber has its own circuit and pump. The filter
  pump is not affected.
- **On:** the filter pump supplies the absorber. In automatic mode the filter
  pump is started on demand (also outside the filtration window), the absorber
  valve or pump only runs while the filter pump runs and is part of the
  interlock. Run time during solar heating counts towards the filtration
  target. Each start costs the stabilization time before readings are valid,
  so use a minimum switching interval of at least 30 minutes in this setup.

Solar heating is active in *Automatic* and *Manual* mode and can be disabled
with `switch.<pool>_solar_heating_control`.

## PV surplus

With a PV surplus sensor, the filtration run time of the day is pulled
forward into times with photovoltaic surplus. It does not add run time.

Every pump start costs the stabilization time (default 30 min) without valid
readings and therefore without chlorination or pH control. To keep the number
of starts low:

- A run is only started when surplus has been available for the start delay
  (default 10 min), so passing clouds do not start the pump.
- A run is only started when the remaining daily target is at least the
  minimum run time.
- A started run lasts at least the minimum run time (default 60 min), even if
  the surplus disappears. With the default values each run yields at least
  30 minutes of valid readings.
- While surplus is available the run continues until the daily target is
  reached.

The schedule remains the fallback: target run time not covered by surplus is
run in the regular slots. The surplus sensor can be a binary sensor or a power
sensor in W compared with the minimum surplus. With a pump power sensor, the
pump's own consumption is added while it runs.

## Chlorination

**Set point:** with *pH compensated* (default) the ORP set point is taken
from the ORP/free chlorine chart of PoolRx for the current pH and the free
chlorine target (default 2.0 ppm). Values are interpolated in both
directions; inputs outside the chart are clamped to its edges. Without a pH
value, or with *fixed*, the fixed set point is used.

| pH | 7.0 | 7.2 | 7.4 | 7.6 | 7.8 | 8.0 |
|---|---|---|---|---|---|---|
| ORP at 2.0 ppm | 780 | 763 | 748 | 732 | 717 | 705 |

A lower pH reduces the required ORP and thereby the chlorinator run time.

**Switching:**

- On: ORP below set point - hysteresis, minimum off time elapsed, daily limit
  not reached.
- Off: ORP above set point + hysteresis and minimum on time elapsed, or
  invalid measurement, daily limit, controller disabled, mode without
  chemistry.
- No switching for the ORP hold-off time after a pH pulse, because acid
  dosing briefly affects the ORP reading.

**Effect check:** if the ORP has risen less than 10 mV after the configured
run time, the problem `chlorinator_no_effect` is raised (salt level, cell or
probe). Chlorination continues.

**Shock chlorination:** raises the free chlorine target to the shock target
(default 5.0 ppm) for the shock duration (default 24 h). With a fixed set
point, the set point is raised by the chart difference at pH 7.4. Swimming is
not recommended while a shock is active.

**Stabilizer:** the ORP chart is valid for water without cyanuric acid.
Stabilizer binds part of the free chlorine, so the same ORP corresponds to a
higher total free chlorine. If a water test reports 20 ppm cyanuric acid or
more while the pH compensated set point is used, a repair issue recommends
checking the free chlorine with a test kit and adjusting the target.

## Water tests and saturation index

Results of manual water tests (total alkalinity, calcium hardness, cyanuric
acid, free chlorine) are entered as number entities or with the action
`record_water_test`. From these values and the measured pH and water
temperature the Langelier saturation index is calculated:

| Index | Meaning |
|---|---|
| below -0.3 | Corrosive, raise alkalinity or calcium hardness |
| -0.3 to +0.3 | Balanced |
| above +0.3 | Scaling, lower pH or alkalinity |

The total alkalinity is corrected for cyanuric acid (one third of it), the
salt reading is used as dissolved solids (1000 ppm without salt sensor).

## pH dosing

A pulse starts when all conditions hold:

- Mode *Automatic* or *Manual*, pH control enabled, dosing not locked
- Filter pump running, valid measurement
- Outside the quiet hours (default 22:00-07:00)
- Mixing pause since the last pulse elapsed (default 10 min)
- pH above the safety minimum and above set point + dead band
- Daily and hourly limit not reached, tank not empty

**Pulse length:**

- *Fixed* (default): the configured pulse length.
- *Proportional*: the amount for the deviation (at most 0.1 pH per pulse)
  calculated from pool volume and product dose, limited to the configured
  pulse length.

The pulse is always limited by the remaining daily amount and tank level. The
pulse length must be at least 5 s shorter than the hardware auto-off of the
relay.

**Accounting:** the dosed amount is calculated from the real on-time of the
switch and the pump rate. Pulses started by hand or by other automations are
counted as well and start the mixing pause.

**Effect check:** the pH at the first pulse of a dosing session is stored.
If the amount dosed in the session should have lowered the pH by the
configured value (default 0.15) but the measured drop is below 0.03, dosing is
locked (`ph_dosing_locked`). Release the lock with the button or action after
checking the tank, hose and probe.

**Learning:** when the set point is reached, the observed product dose
(mL per 10 m³ per 0.1 pH) is calculated and averaged. It is shown as a
diagnostic sensor and used by the proportional mode. Note that salt
chlorination raises the pH, so the learned value is conservative.

## Tank and pump rate

The tank level is reduced by every dosing run. *Tank refilled* sets it to the
capacity (or the given level).

If the refilled amount is given (action `ph_tank_refilled`, field
`refilled_ml`) and the tank is always filled to the same level, the amount
equals the consumption since the last refill. Divided by the accumulated pump
on-time, it gives the real pump rate, which replaces the configured one.

## Frost protection

The outdoor temperature comes from the outdoor temperature sensor or, if not
configured, from the weather entity. Frost protection starts below the
threshold (default 2 °C) and ends 1 K above it. The pump then runs in
intervals (default the first 15 minutes of each hour) or continuously.
Chlorination and pH dosing stay locked during winter mode.

## Swimming assessment

Based on valid readings, or on the last valid readings if they are not older
than the maximum data age:

| Status | Condition |
|---|---|
| `no_data` | No recent readings |
| `dosing` | pH pulse within the last 30 minutes |
| `shock` | Shock chlorination active |
| `ph_low` / `ph_high` | pH outside the swimming range (default 7.0-7.8) |
| `orp_low` | ORP below minimum (default 650 mV) |
| `ok` | Swimming allowed |

## Interlock

- Pump switched off: chlorinator and dosing pump are switched off immediately.
- Chlorinator or dosing pump switched on while the pump is off: switched off
  immediately.
- Flow sensor reports no flow: chlorinator and dosing pump are switched off.
- The dosing pump is switched off if it runs 30 s longer than the pulse
  length, if the pH falls below the safety minimum, and at Home Assistant
  start.

## Problems

| Problem | Meaning |
|---|---|
| `no_flow` | Pump on, but no flow |
| `sensor_stuck` | Primary value unchanged for too long |
| `sensor_deviation` | Primary and backup differ by more than 0.3 pH or 100 mV |
| `water_quality` | pH outside 6.8-8.2 or ORP below 500 mV |
| `ph_too_low` | pH below the safety minimum |
| `ph_dosing_locked` | Effect check locked dosing |
| `ph_daily_limit` | Daily dosing limit reached |
| `ph_tank_low` / `ph_tank_empty` | Tank level |
| `chlorinator_no_effect` | ORP does not rise while chlorinating |
| `chlorinator_daily_limit` | Daily chlorinator limit reached |
| `salt_low` / `salt_high` | Salt outside the configured range |
| `outdoor_temperature_unavailable` | Frost protection has no temperature |

Problems are shown by `binary_sensor.<pool>_problem` and fired as
`pool_control_event` with type `problem` and `problem_resolved`.

## Maintenance reminders

Reminders for pH probe calibration, ORP probe calibration, filter backwash
and chlorinator cell cleaning (default 30, 30, 14, 90 days; 0 disables). The
interval starts when a reminder is enabled. Each task has a sensor with the
next due date and a button to mark it as done. `binary_sensor.<pool>_maintenance_due`
is on while a task is due, and `pool_control_event` with type
`maintenance_due` is fired once per task.

## Persistence

Settings exposed as entities, counters, tank level, learned values, lockouts
and switch timestamps are stored in `.storage/pool_control.<entry_id>` and
survive restarts. After a restart with a running pump the stored pump start
is kept, so the stabilization time is not restarted.
