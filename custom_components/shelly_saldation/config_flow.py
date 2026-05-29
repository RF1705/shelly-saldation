from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    CONF_EXPORT_ENERGY,
    CONF_IMPORT_ENERGY,
    CONF_POWER,
    CONF_SCAN_INTERVAL,
    CONF_SOURCE_DEVICE_CONNECTIONS,
    CONF_SOURCE_DEVICE,
    CONF_SOURCE_DEVICE_IDENTIFIERS,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .discovery import discover_sources_for_device


class ShellySaldationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = user_input[CONF_SOURCE_DEVICE]
            sources = discover_sources_for_device(self.hass, device_id)

            if not sources.import_energy:
                errors["base"] = "missing_import_sources"
            elif not sources.export_energy:
                errors["base"] = "missing_export_sources"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()

                title = user_input.get(CONF_NAME) or sources.device_name or DEFAULT_NAME
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_NAME: title,
                        CONF_SOURCE_DEVICE: device_id,
                        CONF_SOURCE_DEVICE_IDENTIFIERS: [
                            list(identifier)
                            for identifier in sources.device_identifiers
                        ],
                        CONF_SOURCE_DEVICE_CONNECTIONS: [
                            list(connection)
                            for connection in sources.device_connections
                        ],
                        CONF_IMPORT_ENERGY: list(sources.import_energy),
                        CONF_EXPORT_ENERGY: list(sources.export_energy),
                        CONF_POWER: list(sources.power),
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME): str,
                vol.Required(CONF_SOURCE_DEVICE): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(integration="shelly")
                ),
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=300)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
