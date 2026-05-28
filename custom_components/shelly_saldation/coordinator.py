from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Shelly3EMClient, Shelly3EMError, Shelly3EMStatus
from .const import CONF_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1


@dataclass(frozen=True)
class BalancedSample:
    status: Shelly3EMStatus
    import_delta_wh: float
    export_delta_wh: float
    import_total_kwh: float
    export_total_kwh: float


class Shelly3EMBalancedCoordinator(DataUpdateCoordinator[BalancedSample]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.client = Shelly3EMClient(
            async_get_clientsession(hass),
            entry.data[CONF_HOST],
            entry.data.get(CONF_USERNAME),
            entry.data.get(CONF_PASSWORD),
        )
        self._previous_status: Shelly3EMStatus | None = None
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
            update_interval=timedelta(seconds=entry.data[CONF_SCAN_INTERVAL]),
        )

    async def async_load_previous_status(self) -> None:
        stored = await self._store.async_load()
        if stored is None:
            return

        try:
            import_values = tuple(float(value) for value in stored["phase_import_wh"])
            export_values = tuple(float(value) for value in stored["phase_export_wh"])
            if len(import_values) != 3 or len(export_values) != 3:
                raise ValueError
            self._previous_status = Shelly3EMStatus(
                phase_powers=(0.0, 0.0, 0.0),
                phase_import_wh=import_values,
                phase_export_wh=export_values,
            )
            self._import_total_kwh = float(stored.get("import_total_kwh", 0) or 0)
            self._export_total_kwh = float(stored.get("export_total_kwh", 0) or 0)
        except (KeyError, TypeError, ValueError):
            self._previous_status = None

    async def _async_update_data(self) -> BalancedSample:
        try:
            status = await self.client.async_get_status()
        except Shelly3EMError as err:
            raise UpdateFailed("Unable to read Shelly 3EM") from err

        import_delta_wh = 0.0
        export_delta_wh = 0.0

        if self._previous_status is not None:
            raw_delta_wh = self._net_energy_delta_wh(self._previous_status, status)
            if raw_delta_wh > 0:
                import_delta_wh = raw_delta_wh
            elif raw_delta_wh < 0:
                export_delta_wh = abs(raw_delta_wh)

        self._import_total_kwh += import_delta_wh / 1000
        self._export_total_kwh += export_delta_wh / 1000
        self._previous_status = status
        await self._store.async_save(
            {
                "phase_import_wh": list(status.phase_import_wh),
                "phase_export_wh": list(status.phase_export_wh),
                "import_total_kwh": self._import_total_kwh,
                "export_total_kwh": self._export_total_kwh,
            }
        )
        return BalancedSample(
            status,
            import_delta_wh,
            export_delta_wh,
            self._import_total_kwh,
            self._export_total_kwh,
        )

    def _net_energy_delta_wh(
        self,
        previous: Shelly3EMStatus,
        current: Shelly3EMStatus,
    ) -> float:
        import_delta = self._positive_delta_sum(
            previous.phase_import_wh, current.phase_import_wh
        )
        export_delta = self._positive_delta_sum(
            previous.phase_export_wh, current.phase_export_wh
        )
        return import_delta - export_delta

    def _positive_delta_sum(
        self,
        previous_values: tuple[float, float, float],
        current_values: tuple[float, float, float],
    ) -> float:
        total = 0.0
        for previous, current in zip(previous_values, current_values, strict=True):
            delta = current - previous
            if delta > 0:
                total += delta
        return total
