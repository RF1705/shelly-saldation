from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_POWER,
    CONF_SOURCE_DEVICE_CONNECTIONS,
    CONF_SOURCE_DEVICE,
    CONF_SOURCE_DEVICE_IDENTIFIERS,
    DEFAULT_NAME,
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

            if not sources.power:
                errors["base"] = "missing_power_sources"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()

                title = sources.device_name or DEFAULT_NAME
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_SOURCE_DEVICE: device_id,
                        CONF_SOURCE_DEVICE_IDENTIFIERS: [
                            list(identifier)
                            for identifier in sources.device_identifiers
                        ],
                        CONF_SOURCE_DEVICE_CONNECTIONS: [
                            list(connection)
                            for connection in sources.device_connections
                        ],
                        CONF_POWER: list(sources.power),
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE_DEVICE): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(integration="shelly")
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
