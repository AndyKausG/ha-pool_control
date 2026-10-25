# Changelog

All notable changes to this project are documented in this file. The format
is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/).

## [1.0.0-beta.2] - 2026-10-25

### Fixed

- Dashboard card: schematic limited in size on wide dashboards
- Dashboard card is registered even if the frontend loads after the
  integration

### Added

- Test bench and guide for trying Pool Control without hardware

## [1.0.0-beta.1] - 2026-10-25

Complete rewrite. Existing config entries are not migrated and must be set up
again.

### Added

- Temperature based filtration schedule with blocks, catch-up and demand
  extension
- ORP controlled chlorination with pH compensated set point
- pH minus dosing with pulses, mixing pause, quiet hours, daily limit, effect
  check and learning of the product dose
- Tank tracking with pump rate calibration on refill
- Frost protection based on weather or outdoor temperature
- Measurement validation (stabilization, age, plausibility, stuck values) and
  backup sensors
- Operating modes, dry run, extra circulation
- Swimming assessment
- Logbook entries, `pool_control_event`, repairs, diagnostics
- Notification blueprint and Shelly interlock script
- English and German translations
- Hourly dosing limit, primary/backup sensor deviation check, Home Assistant
  watchdog in the Shelly script
- Manual water tests, Langelier saturation index, shock chlorination,
  stabilizer warning
- Maintenance reminders
- Solar heating (differential control or external signal) and PV surplus
  filtration
- Icon and logo shipped with the integration (Home Assistant 2026.3+)
- Pool Control dashboard card shipped with the integration, dashboard example

### Notes

- A new installation starts in dry run and does not switch anything until
  dry run is disabled.

### Removed

- Recovery strategies, smart monitoring, hot weather strategy, swimming
  detection, adaptive learning and the `reload_config` service of the 0.x
  versions
