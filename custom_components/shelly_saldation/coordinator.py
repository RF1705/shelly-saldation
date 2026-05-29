from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_POWER, DOMAIN

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 2


@dataclass(frozen=True)
class SourceSnapshot:
    power_w: tuple[float, ...]

    @property
    def net_power_w(self) -> float:
        return sum(self.power_w)

    @property
    def import_power_w(self) -> float:
        return max(self.net_power_w, 0.0)

    @property
    def export_power_w(self) -> float:
        return max(-self.net_power_w, 0.0)


@dataclass(frozen=True)
class BalancedSample:
    snapshot: SourceSnapshot
    import_delta_wh: float
    export_delta_wh: float
    import_total_kwh: float
    export_total_kwh: float


class ShellySaldationStore(Store[dict]):
    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict,
    ) -> dict:
        if old_major_version == 1:
            return {
                "power_w": [],
                "timestamp": None,
                "import_total_kwh": old_data.get("import_total_kwh", 0),
                "export_total_kwh": old_data.get("export_total_kwh", 0),
            }
        return old_data


class ShellySaldationCoordinator(DataUpdateCoordinator[BalancedSample]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._entry = entry
        self._previous_snapshot: SourceSnapshot | None = None
        self._previous_timestamp: datetime | None = None
        self._import_total_kwh = 0.0
        self._export_total_kwh = 0.0
        self._store: ShellySaldationStore = ShellySaldationStore(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry.entry_id}",
            minor_version=1,
        )

        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=None,
        )

    @callback
    def async_start_listening(self) -> None:
        tracked_entities = self._entry.data.get(CONF_POWER, [])

        @callback
        def _handle_state_change(event: Event) -> None:
            new_state = event.data.get("new_state")
            if new_state is None or new_state.state in ("unknown", "unavailable"):
                return
            self.async_update_from_current_states()

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
            power_w = tuple(float(value) for value in stored["power_w"])
            self._previous_snapshot = (
                SourceSnapshot(power_w=power_w) if power_w else None
            )
            timestamp = stored.get("timestamp")
            self._previous_timestamp = (
                dt_util.parse_datetime(timestamp)
                if timestamp is not None and self._previous_snapshot is not None
                else None
            )
            self._import_total_kwh = float(stored.get("import_total_kwh", 0) or 0)
            self._export_total_kwh = float(stored.get("export_total_kwh", 0) or 0)
        except (KeyError, TypeError, ValueError):
            self._previous_snapshot = None
            self._previous_timestamp = None

    async def _async_update_data(self) -> BalancedSample:
        sample = self._calculate_sample_from_current_states()
        await self._async_save_state()
        return sample

    @callback
    def async_update_from_current_states(self) -> None:
        try:
            sample = self._calculate_sample_from_current_states()
        except UpdateFailed as err:
            self.last_update_success = False
            _LOGGER.debug("Unable to update Shelly Saldation state: %s", err)
            return

        self.last_update_success = True
        self.async_set_updated_data(sample)
        self.hass.async_create_task(self._async_save_state())

    def _calculate_sample_from_current_states(self) -> BalancedSample:
        snapshot = self._read_source_snapshot()
        timestamp = dt_util.utcnow()

        import_delta_wh = 0.0
        export_delta_wh = 0.0

        if self._previous_snapshot is not None and self._previous_timestamp is not None:
            elapsed_hours = (
                timestamp - self._previous_timestamp
            ).total_seconds() / 3600
            if elapsed_hours > 0:
                import_delta_wh = self._trapezoid_delta_wh(
                    self._previous_snapshot.import_power_w,
                    snapshot.import_power_w,
                    elapsed_hours,
                )
                export_delta_wh = self._trapezoid_delta_wh(
                    self._previous_snapshot.export_power_w,
                    snapshot.export_power_w,
                    elapsed_hours,
                )

        self._import_total_kwh += import_delta_wh / 1000
        self._export_total_kwh += export_delta_wh / 1000
        self._previous_snapshot = snapshot
        self._previous_timestamp = timestamp

        return BalancedSample(
            snapshot,
            import_delta_wh,
            export_delta_wh,
            self._import_total_kwh,
            self._export_total_kwh,
        )

    async def _async_save_state(self) -> None:
        if self._previous_snapshot is None or self._previous_timestamp is None:
            return

        await self._store.async_save(
            {
                "power_w": list(self._previous_snapshot.power_w),
                "timestamp": self._previous_timestamp.isoformat(),
                "import_total_kwh": self._import_total_kwh,
                "export_total_kwh": self._export_total_kwh,
            }
        )

    def _read_source_snapshot(self) -> SourceSnapshot:
        power_entities = self._entry.data.get(CONF_POWER, [])
        if not power_entities:
            raise UpdateFailed("No power sources configured")

        return SourceSnapshot(
            power_w=tuple(self._read_power_w(entity_id) for entity_id in power_entities),
        )

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

    def _trapezoid_delta_wh(
        self,
        previous_power_w: float,
        current_power_w: float,
        elapsed_hours: float,
    ) -> float:
        return ((previous_power_w + current_power_w) / 2) * elapsed_hours
