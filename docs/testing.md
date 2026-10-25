# Trying Pool Control without hardware

The test bench in [`examples/test_bench.yaml`](examples/test_bench.yaml)
provides switches for pump, chlorinator and pH pump and sliders for pH, ORP,
water temperature and salt. Pool Control controls the switches as if they
were real devices.

## Setup

1. Copy `test_bench.yaml` to `/config/packages/pool_test_bench.yaml`.
2. Enable packages in `configuration.yaml` (if not done yet):

   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

3. Restart Home Assistant.
4. Add Pool Control with the name **Pool Test**:

   | Field | Entity |
   |---|---|
   | Filter pump | `input_boolean.pool_test_pump` |
   | Salt chlorinator | `input_boolean.pool_test_chlorinator` |
   | pH minus dosing pump | `input_boolean.pool_test_ph_pump` |
   | pH / ORP / water temperature | `sensor.pool_test_ph` / `sensor.pool_test_orp` / `sensor.pool_test_water_temperature` |
   | Salt sensor | `sensor.pool_test_salt` |
   | Weather | your weather entity (optional) |

5. Speed up the test: *Configure > Measurement* > stabilization time **1 min**.
6. Disable **Dry run** on the device page. Only the test switches are switched.
7. Reload the browser and add the card (`type: custom:pool-control-card`).

## Scenarios

| Scenario | Action | Expected |
|---|---|---|
| Filtration | Mode *Automatic* inside the filtration window (08:00-22:00) | Pump switches on, status *Stabilizing*, after 1 min *Filtering* |
| Outside the window | Mode *Automatic* outside the window | Pump stays off, *Next filtration* shows the next start |
| Manual | Mode *Manual*, switch the pump on by hand | Pump stays on, controller does not switch it off |
| Chlorination | Pump running, ORP slider to 700 | Chlorinator on (`orp_low`); ORP to 790 after 30 min: off (`target_reached`) |
| pH dosing | pH slider to 7.5 | pH pump on for 50 s, tank level and *dosed today* change; next pulse after 10 min |
| Quiet hours | pH 7.5 between 22:00 and 07:00 | No pulse, status attribute `ph_dosing_blocked_reason: quiet_hours` |
| Interlock | Chlorinator on, switch the pump off by hand | Chlorinator off immediately, logbook entry `interlock` |
| Interlock | Pump off, switch the pH pump on by hand | pH pump off immediately |
| Water quality | pH slider to 8.4 | `binary_sensor.pool_test_problem` on (`water_quality`) |
| Safety minimum | pH slider to 6.7 | No dosing (`ph_too_low`), problem `ph_too_low` |
| Swimming | pH 7.2, ORP 720 | *Swimming allowed* on; ORP 600: off (`orp_low`) |
| Salt | Salt slider to 2000 | Problem `salt_low` |
| Extra circulation | Button *Start extra circulation* outside the window | Pump runs for the configured duration |
| Shock | Button *Start shock chlorination* | ORP set point rises, swimming status *Shock* |
| Dry run | Enable *Dry run* | Nothing is switched, logbook shows *Simulation: ...* |

All decisions are listed with their reason in the logbook of the device and
in the attributes of `sensor.pool_test_status`.

## Remove

Delete the Pool Test integration entry and `packages/pool_test_bench.yaml`,
then restart Home Assistant.
