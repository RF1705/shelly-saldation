# Shelly Saldation

Custom integration for Home Assistant that creates phase-balanced grid import/export sensors from an existing Shelly energy meter device.

The Shelly 3EM Gen1 reports energy per phase. In countries with saldierende Zaehler, the Home Assistant Energy Dashboard often needs grid import and export after the three phases have been netted. This integration lets you select the Shelly device that already exists in Home Assistant, finds its import/export energy sensors, compares their counters, and exposes:

- Balanced grid import energy in kWh
- Balanced grid export energy in kWh
- Balanced net power in W

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

The first update after initial setup initializes the baseline. After that, the integration stores both the last source counters and its own balanced import/export counters in Home Assistant storage. On restart, it can continue from the last known values.

Shelly Saldation automatically detects import, returned/export, and power sensors from the selected Shelly device. The detected source entity IDs are shown as attributes on the created sensors, which makes checking the setup easier.

For the Energy Dashboard, select the `Balanced grid import energy` entity as grid consumption and `Balanced grid export energy` as return to grid.
