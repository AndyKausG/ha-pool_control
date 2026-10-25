# Configuration reference

All parameters are changed in Settings > Devices & services > Pool Control >
*Configure*. Saving reloads the integration.

## Entities

| Option | Required | Description |
|---|---|---|
| Filter pump | yes | `switch`, `input_boolean` or `light` |
| Salt chlorinator | no | Switch of the chlorinator |
| pH minus dosing pump | no | Switch of the dosing pump |
| pH sensor | yes | Primary pH sensor in the flow cell |
| ORP sensor | yes | Primary ORP sensor (mV) |
| Water temperature sensor | yes | Primary water temperature |
| Backup pH / ORP / temperature | no | Used while the pump is off |
| Salt sensor | no | ppm, warnings only |
| Weather | no | Outdoor temperature for frost protection |
| Outdoor temperature sensor | no | Takes precedence over the weather entity |
| Flow sensor | no | `binary_sensor`, on while water flows |
| Pump power sensor | no | Flow indicator if no flow sensor exists |

## Filtration

| Option | Default | Description |
|---|---|---|
| Pool volume | 17.2 m³ | Used for dosing calculations |
| Filtration window | 08:00-22:00 | Scheduled runs only inside the window |
| Filtration blocks | 2 | Number of runs per day |
| Temperature divisor | 2.0 | Daily hours = water temperature / divisor |
| Minimum / maximum daily filtration | 2 h / 12 h | Limits; the maximum also limits the demand extension |
| Demand extension | on | Keep running while chemistry is needed |
| Minimum pump power | 20 W | Below: no flow (only with pump power sensor) |

## Measurement

| Option | Default | Description |
|---|---|---|
| Stabilization time | 30 min | After pump start |
| Maximum sensor age | 5 min | Older readings are invalid |
| Stuck sensor detection | 60 min | 0 disables |
| Maximum backup sensor age | 120 min | |

## Chlorination

| Option | Default | Description |
|---|---|---|
| ORP set point | pH compensated | Or fixed |
| Fixed ORP set point | 735 mV | Fixed mode and fallback |
| ORP hysteresis | 15 mV | |
| Minimum on / off time | 30 / 15 min | Protects the cell |
| Maximum per day | 12 h | |
| Effect check | 3 h | Warning if ORP has not risen |
| ORP hold-off after dosing | 15 min | |
| Minimum / maximum salt | 2500 / 4500 ppm | Warnings |

## pH dosing

| Option | Default | Description |
|---|---|---|
| Pulse length mode | Fixed | Or proportional |
| pH dead band | 0.05 | Dose above set point + dead band |
| Pulse length | 50 s | Fixed length or maximum |
| Hardware auto-off | 60 s | Auto-off of the relay, 0 if none |
| Mixing pause | 10 min | |
| Pump rate | 21 mL/min | Replaced by the calibrated rate after a refill |
| Product dose | 300 mL | Per 10 m³ per 0.1 pH (manufacturer data) |
| Maximum per day | 1500 mL | |
| pH safety minimum | 6.8 | |
| No dosing from / until | 22:00 / 07:00 | |
| Effect check | 0.15 pH | Expected drop before locking |
| Tank capacity | 5000 mL | |
| Tank warning level | 500 mL | |

## Frost protection and swimming

| Option | Default | Description |
|---|---|---|
| Frost protection temperature | 2 °C | Ends 1 K above |
| Frost protection mode | Interval | Or continuous |
| Pump minutes per hour | 15 min | Interval mode |
| Swimming pH range | 7.0-7.8 | |
| Swimming minimum ORP | 650 mV | |
| Swimming maximum data age | 6 h | |

## Settings as entities

These values are changed directly on the device page and take effect
immediately:

| Entity | Default |
|---|---|
| Operating mode | Automatic |
| Dry run | off |
| Chlorine control / pH control | on |
| pH set point | 7.2 |
| Free chlorine target | 2.0 ppm |
| Extra circulation duration | 2 h |
