from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_EXPORT_ENERGY,
    CONF_IMPORT_ENERGY,
    CONF_POWER,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1


@dataclass(frozen=True)
class SourceSnapshot:
    import_wh: tuple[float, ...]
    export_wh: tuple[float, ...]
    power_w: tuple[float, ...]

    @property
    def net_power_w(self) -> float | None:
        if not self.power_w:
            return None
        return sum(self.power_w)


@dataclass(frozen=True)
class BalancedSample:
    snapshot: SourceSnapshot
    import_delta_wh: float
    export_delta_wh: float
    import_total_kwh: float
    export_total_kwh: float


class ShellySaldationCoordinator(DataUpdateCoordinator[BalancedSample]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._entry = entry
        self._previous_snapshot: SourceSnapshot | None = None
        self._import_total_kwh = 0.0
        self._export_total_kwh = 0.0
        self._store: Store[dict] = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry.entry_id}",
        )

        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=None,
        )

    @callback
    def async_start_listening(self) -> None:
        tracked_entities = [
            *self._entry.data[CONF_IMPORT_ENERGY],
            *self._entry.data[CONF_EXPORT_ENERGY],
            *self._entry.data.get(CONF_POWER, []),
        ]

        @callback
        def _handle_state_change(event: Event) -> None:
            new_state = event.data.get("new_state")
            if new_state is None or new_state.state in ("unknown", "unavailable"):
                return
            self.hass.async_create_task(self.async_request_refresh())

        self._entry.async_on_unload(
            async_track_state_change_event(
                self.hass,
                tracked_entities,
                _handle_state_change,
            )
        )

    async def async_load_previous_snapshot(self) -> None:
        stored = await self._store.async_load()
        if stored is None:
            return

        try:
            self._previous_snapshot = SourceSnapshot(
                import_wh=tuple(float(value) for value in stored["import_wh"]),
                export_wh=tuple(float(value) for value in stored["export_wh"]),
                power_w=(),
            )
            self._import_total_kwh = float(stored.get("import_total_kwh", 0) or 0)
            self._export_total_kwh = float(stored.get("export_total_kwh", 0) or 0)
        except (KeyError, TypeError, ValueError):
            self._previous_snapshot = None

    async def _async_update_data(self) -> BalancedSample:
        snapshot = self._read_source_snapshot()

        import_delta_wh = 0.0
        export_delta_wh = 0.0

        if self._previous_snapshot is not None:
            raw_delta_wh = self._net_energy_delta_wh(self._previous_snapshot, snapshot)
            if raw_delta_wh > 0:
                import_delta_wh = raw_delta_wh
            elif raw_delta_wh < 0:
                export_delta_wh = abs(raw_delta_wh)

        self._import_total_kwh += import_delta_wh / 1000
        self._export_total_kwh += export_delta_wh / 1000
        self._previous_snapshot = snapshot

        await self._store.async_save(
            {
                "import_wh": list(snapshot.import_wh),
                "export_wh": list(snapshot.export_wh),
                "import_total_kwh": self._import_total_kwh,
                "export_total_kwh": self._export_total_kwh,
            }
        )

        return BalancedSample(
            snapshot,
            import_delta_wh,
            export_delta_wh,
            self._import_total_kwh,
            self._export_total_kwh,
        )

    def _read_source_snapshot(self) -> SourceSnapshot:
        return SourceSnapshot(
            import_wh=tuple(
                self._read_energy_wh(entity_id)
                for entity_id in self._entry.data[CONF_IMPORT_ENERGY]
            ),
            export_wh=tuple(
                self._read_energy_wh(entity_id)
                for entity_id in self._entry.data[CONF_EXPORT_ENERGY]
            ),
            power_w=tuple(
                self._read_power_w(entity_id)
                for entity_id in self._entry.data.get(CONF_POWER, [])
            ),
        )

    def _read_energy_wh(self, entity_id: str) -> float:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            raise UpdateFailed(f"Energy source unavailable: {entity_id}")

        value = self._read_float_state(entity_id)
        unit = state.attributes.get("unit_of_measurement")

        if unit == UnitOfEnergy.KILO_WATT_HOUR:
            return value * 1000
        if unit == UnitOfEnergy.MEGA_WATT_HOUR:
            return value * 1000000
        if unit == UnitOfEnergy.WATT_HOUR:
            return value

        # Some integrations expose percent-like units accidentally while keeping
        # device_class=energy. Failing loudly avoids silently corrupting totals.
        if unit == PERCENTAGE:
            raise UpdateFailed(f"Energy source has invalid unit: {entity_id}")

        return value * 1000

    def _read_power_w(self, entity_id: str) -> float:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            raise UpdateFailed(f"Power source unavailable: {entity_id}")

        value = self._read_float_state(entity_id)
        unit = state.attributes.get("unit_of_measurement")

        if unit == UnitOfPower.KILO_WATT:
            return value * 1000
        if unit == UnitOfPower.WATT:
            return value

        return value

    def _read_float_state(self, entity_id: str) -> float:
        state = self.hass.states.get(entity_id)
        if state is None:
            raise UpdateFailed(f"Source unavailable: {entity_id}")

        try:
            return float(state.state)
        except ValueError as err:
            raise UpdateFailed(f"Source is not numeric: {entity_id}") from err

    def _net_energy_delta_wh(
        self,
        previous: SourceSnapshot,
        current: SourceSnapshot,
    ) -> float:
        import_delta = self._positive_delta_sum(previous.import_wh, current.import_wh)
        export_delta = self._positive_delta_sum(previous.export_wh, current.export_wh)
        return import_delta - export_delta

    def _positive_delta_sum(
        self,
        previous_values: tuple[float, ...],
        current_values: tuple[float, ...],
    ) -> float:
        total = 0.0
        for previous, current in zip(previous_values, current_values, strict=True):
            delta = current - previous
            if delta > 0:
                total += delta
        return total
