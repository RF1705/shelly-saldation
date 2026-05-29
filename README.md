# Shelly Saldation

[![Validate](https://github.com/RF1705/shelly-saldation/actions/workflows/validate.yml/badge.svg)](https://github.com/RF1705/shelly-saldation/actions/workflows/validate.yml)
[![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-rf1705-yellow?logo=buymeacoffee)](https://buymeacoffee.com/rf1705)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Custom integration for Home Assistant that creates phase-balanced grid import/export sensors from an existing Shelly energy meter device.

The Shelly 3EM Gen1 reports power per phase. In installations where the utility meter nets all three phases, the Home Assistant Energy Dashboard often needs grid import and export after the phases have been balanced. This integration lets you select the main Shelly device that already exists in Home Assistant, finds the power sensors on its phase sub-devices, balances the phases, and exposes:

- Grid import energy in kWh
- Grid export energy in kWh
- Net power in W

## Installation with HACS

1. Publish this folder as a GitHub repository.
2. In HACS, add it as a custom repository of type `Integration`.
3. Install `Shelly Saldation`.
4. Restart Home Assistant.
5. Add the integration from **Settings > Devices & services > Add integration**.
6. Select your existing Shelly device.

## Manual installation

Copy `custom_components/shelly_saldation` into your Home Assistant `custom_components` folder and restart Home Assistant.

## Notes

The first update after initial setup initializes the baseline. After that, the integration stores the last balanced power sample, timestamp, and its own balanced import/export counters in Home Assistant storage. On restart, it can continue from the last known values.

Shelly Saldation automatically detects power sensors from the phase sub-devices below the selected Shelly device. The main device itself is not used as a source. Detected source entity IDs are shown as attributes on the created sensors, which makes checking the setup easier.

Shelly Saldation does not poll on a fixed interval. It listens for state changes from the detected power sensors and recalculates when Home Assistant receives new values.

Grid import/export energy is calculated from net power with trapezoidal integration. This avoids large jumps that can happen when phase energy counter deltas are netted while a battery system is actively regulating the grid point around zero.

The created sensors are attached to the selected Shelly device in Home Assistant. On the device page you should see both integrations, `Shelly` and `Shelly Saldation`, and the balanced sensors will appear directly on that Shelly device.

For the Energy Dashboard, select the `Grid import energy` entity as grid consumption and `Grid export energy` as return to grid.

## Support

If Shelly Saldation is useful for you, you can support the project here: [buymeacoffee.com/rf1705](https://buymeacoffee.com/rf1705).

## License

Shelly Saldation is released under the [MIT License](LICENSE).
