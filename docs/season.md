# Season start and end

## Installing outside the season

A new installation starts with **Dry run** enabled: the controller
calculates all decisions and writes them to the logbook, but does not switch
anything. This makes it safe to install and configure Pool Control while the
pool is closed.

For the winter:

- Pool drained or dismantled: set the operating mode to **Off**. Nothing is
  switched, frost protection is inactive.
- Pool filled over the winter: set the operating mode to **Winter**. Only
  frost protection runs the pump (requires a weather entity or an outdoor
  temperature sensor and dry run disabled).

## Season start checklist

1. Install the probes, calibrate pH and ORP (see
   [hardware.md](hardware.md#calibration-of-the-w2839)) and press the
   corresponding *calibration done* buttons.
2. Check salt level and water balance, record the water test
   (`pool_control.record_water_test` or the number entities).
3. Fill the pH minus tank and press *pH minus tank refilled*.
4. Check the hardware safeguards: auto-off of the dosing pump in the relay,
   interlock and watchdog script on the Shelly.
5. Set the operating mode to **Manual**, switch the filter pump on by hand and
   check after 30 minutes that `binary_sensor.<pool>_measurement_valid` is on.
   If not, the attribute `reason` names the cause (for example `stale`:
   increase *Maximum sensor age*).
6. Disable other automations that switch the pump, chlorinator or dosing pump.
7. Start conservatively: daily pH maximum 300 mL, hourly maximum 100 mL,
   fixed ORP set point.
8. Set the operating mode to **Automatic** and disable **Dry run**.
9. Check the logbook of the Pool Control device daily during the first week.
   Every action is listed with its reason.

To fall back, set the operating mode to **Off**.

## Season end checklist

1. Set the operating mode to **Winter** (pool stays filled) or **Off** (pool
   drained or dismantled).
2. Remove and store the probes as recommended by the manufacturer (pH probe
   in storage solution, never dry).
3. Empty and rinse the dosing pump and hose.
4. Reset the seasonal counter (`pool_control.reset_season`) at the next
   season start.
