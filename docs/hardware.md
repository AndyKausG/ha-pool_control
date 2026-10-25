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

## Calibration

- pH probe: two-point calibration (for example buffers 6.86 and 9.18). The
  W2839 stores the calibration in the device, replacing a probe requires a
  new calibration.
- ORP probe: 650 mV reference solution.
- Dosing pump rate: either measure it once (run the pump 60 s into a measuring
  cylinder) or give the refilled amount with the action `ph_tank_refilled`
  after each refill.

## Brand images

`brand/` contains the icon and logo in the sizes required by the
[Home Assistant brands repository](https://github.com/home-assistant/brands)
(`icon.png` 256x256, `icon@2x.png` 512x512, `logo.png`, `logo@2x.png`) plus
the SVG sources. Home Assistant and HACS show the icon once it has been added
to `custom_integrations/pool_control` in that repository.
