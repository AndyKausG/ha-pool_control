# Hardware example

Pool Control works with any switch and sensor entities. This page describes
the reference installation and the recommended hardware safeguards.

## Reference installation

| Function | Device | Integration |
|---|---|---|
| Relays | Shelly Pro 3 | Shelly |
| Filter pump | Shelly channel 1 | |
| Salt chlorinator (Intex) | Shelly channel 2 | |
| pH minus dosing pump | Shelly channel 3 | |
| pH, ORP, water temperature | W2839 controller with probes in a flow cell (50 mm bypass) | Tuya Local |
| Backup sensor, salt | Ondilo ICO (floating) | Ondilo |

The W2839 is powered permanently. While the pump is off, the flow cell holds
standing water; these readings are discarded by the validity rules. The
internal relay outputs of the W2839 are not used.

## Hardware safeguards

Configure these in the relay so they work when Home Assistant is down.

### Auto-off of the dosing pump

Set an auto-off timer for the dosing pump channel, for example 60 s. Set the
same value as *Hardware auto-off* in the pH dosing options; the pulse length
must be at least 5 s shorter.

### Auto-off of the chlorinator and the pump

Optional: an auto-off of 12 h for the chlorinator and the pump limits the run
time if Home Assistant fails while they run. Intex chlorinators stop
producing after 12 h anyway.

### Interlock and watchdog script

[`examples/shelly_interlock.js`](examples/shelly_interlock.js) runs on the
Shelly Pro 3 (Settings > Scripts, enable *Run on startup*). It switches off
channels 2 and 3 when channel 1 stops and prevents them from being switched
on while channel 1 is off.

The watchdog part calls the Home Assistant API every minute. After five
failed calls it switches off the chlorinator and the dosing pump, so they do
not keep running while Home Assistant is down. Enter the URL of your Home
Assistant and a long-lived access token (preferably of a dedicated user) at
the top of the script. Adjust the channel numbers if your wiring differs. If the dosing pump is
on a different device, it can only be protected by its auto-off timer and by
Pool Control.

## Calibration of the W2839

Interval: about once a month, or when the readings differ significantly from
a reference measurement (for example a photometer). Pool Control reminds you
every 30 days (configurable) and offers *pH calibration done* and *ORP
calibration done* buttons.

Preparation for both probes: distilled water, three clean cups rinsed with
distilled water, a separate stirrer per cup, paper towels.

### ORP probe

Requires a 650 mV reference solution (temperature dependent, 650 mV at 25 °C).

1. Remove the probe, place it in distilled water for 5 minutes, move it
   gently and wait for a stable value.
2. Place it in the 650 mV solution and wait until the value no longer
   changes.
3. Hold the CAL button for 5 s to enter calibration mode.
4. Correct the value to 650 mV with CAL- / CAL+.
5. Wait about 5 s; the value is saved automatically.

After reinstalling, the ORP probe may show completely wrong values for a
while (for example 220 mV); the diaphragm reacts to the pressure change. Put
the probe in salty water (pool water or a little salt in water) for
5 minutes and install it without rinsing. The value settles shortly after.
Pool Control ignores the readings during the stabilization time after each
pump start.

### pH probe

Requires buffer solutions pH 4.01, 6.86 and 9.18 at room temperature. The
device detects the buffer automatically; start with 6.86.

1. **pH 6.86:** clean the probe with distilled water and dab it dry. Place it
   in the buffer, move it gently and wait at least 10 minutes for an
   absolutely stable value. Hold CAL for 3 s until the display flashes; the
   value is saved. Dab dry and rinse with distilled water.
2. **pH 4.01:** place the probe in the buffer, wait for a stable value, hold
   CAL for 3 s. Dab dry and rinse.
3. **pH 9.18:** as above. Clean and rinse the probe afterwards.

Optionally repeat the 6.86 step as a check; this mid-range value matters most
for pool water.

The calibration is stored in the device, not in the probe: replacing a probe
requires a new calibration.

### Dosing pump rate

Either measure it once (run the pump 60 s into a measuring cylinder) or give
the refilled amount with the action `ph_tank_refilled` after each refill.

## Brand images

`custom_components/pool_control/brand/` contains icon and logo
(`icon.png` 256x256, `icon@2x.png` 512x512, `logo.png`, `logo@2x.png`).
Home Assistant 2026.3 and newer shows them without an entry in the central
brands repository. The SVG sources are in `docs/brand/`.
