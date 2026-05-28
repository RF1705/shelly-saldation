# Shelly Saldation

Custom integration for Home Assistant that creates phase-balanced grid import/export sensors from existing Shelly energy meter entities.

The Shelly 3EM Gen1 reports energy per phase. In countries with saldierende Zaehler, the Home Assistant Energy Dashboard often needs grid import and export after the three phases have been netted. This integration reads the Shelly sensors that already exist in Home Assistant, compares their per-phase import/export counters, and exposes:

- Balanced grid import energy in kWh
- Balanced grid export energy in kWh
- Balanced net power in W

## Installation with HACS

1. Publish this folder as a GitHub repository.
2. In HACS, add it as a custom repository of type `Integration`.
3. Install `Shelly Saldation`.
4. Restart Home Assistant.
5. Add the integration from **Settings > Devices & services > Add integration**.
6. Select the existing Shelly import energy, export energy, and optional power sensors.

## Manual installation

Copy `custom_components/shelly_saldation` into your Home Assistant `custom_components` folder and restart Home Assistant.

## Notes

The first update after initial setup initializes the baseline. After that, the integration stores both the last source counters and its own balanced import/export counters in Home Assistant storage. On restart, it can continue from the last known values.

The selected import and export source lists must have the same number of sensors. For a Shelly 3EM this is usually three import energy sensors and three returned/export energy sensors, one pair per phase. Optional power sensors are only used for the `Balanced net power` sensor.

For the Energy Dashboard, select the `Balanced grid import energy` entity as grid consumption and `Balanced grid export energy` as return to grid.
