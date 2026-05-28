from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import BasicAuth, ClientError, ClientResponseError, ClientSession
from async_timeout import timeout


class Shelly3EMError(Exception):
    """Raised when the Shelly 3EM cannot be read."""


@dataclass(frozen=True)
class Shelly3EMStatus:
    phase_powers: tuple[float, float, float]
    phase_import_wh: tuple[float, float, float]
    phase_export_wh: tuple[float, float, float]

    @property
    def net_power_w(self) -> float:
        return sum(self.phase_powers)


class Shelly3EMClient:
    def __init__(
        self,
        session: ClientSession,
        host: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._session = session
        self._host = host.strip()
        self._auth = BasicAuth(username, password or "") if username else None

    async def async_get_status(self) -> Shelly3EMStatus:
        url = f"http://{self._host}/status"
        try:
            async with timeout(10):
                response = await self._session.get(url, auth=self._auth)
                response.raise_for_status()
                payload = await response.json()
        except (ClientError, ClientResponseError, TimeoutError, ValueError) as err:
            raise Shelly3EMError from err

        return self._parse_status(payload)

    def _parse_status(self, payload: dict[str, Any]) -> Shelly3EMStatus:
        emeters = payload.get("emeters")
        if not isinstance(emeters, list) or len(emeters) < 3:
            raise Shelly3EMError("Shelly response does not contain three emeters")

        powers: list[float] = []
        imported: list[float] = []
        exported: list[float] = []

        for emeter in emeters[:3]:
            if not isinstance(emeter, dict):
                raise Shelly3EMError("Invalid emeter response")
            powers.append(float(emeter.get("power", 0) or 0))
            imported.append(float(emeter.get("total", 0) or 0))
            exported.append(float(emeter.get("total_returned", 0) or 0))

        return Shelly3EMStatus(
            phase_powers=(powers[0], powers[1], powers[2]),
            phase_import_wh=(imported[0], imported[1], imported[2]),
            phase_export_wh=(exported[0], exported[1], exported[2]),
        )
