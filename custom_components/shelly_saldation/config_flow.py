from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    CONF_EXPORT_ENERGY,
    CONF_IMPORT_ENERGY,
    CONF_POWER,
    CONF_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class ShellySaldationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            import_entities = user_input[CONF_IMPORT_ENERGY]
            export_entities = user_input[CONF_EXPORT_ENERGY]

            if not import_entities or not export_entities:
                errors["base"] = "missing_sources"
            elif len(import_entities) != len(export_entities):
                errors["base"] = "source_count_mismatch"
            else:
                selected_entities = [
                    *import_entities,
                    *export_entities,
                    *user_input.get(CONF_POWER, []),
                ]
                await self.async_set_unique_id(",".join(sorted(selected_entities)))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or DEFAULT_NAME,
                    data=user_input,
                )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_IMPORT_ENERGY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class=SensorDeviceClass.ENERGY,
                        multiple=True,
                    )
                ),
                vol.Required(CONF_EXPORT_ENERGY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class=SensorDeviceClass.ENERGY,
                        multiple=True,
                    )
                ),
                vol.Optional(CONF_POWER): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class=SensorDeviceClass.POWER,
                        multiple=True,
                    )
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
