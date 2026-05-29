from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_EXPORT_ENERGY,
    CONF_IMPORT_ENERGY,
    CONF_POWER,
    CONF_SOURCE_DEVICE_CONNECTIONS,
    CONF_SOURCE_DEVICE_IDENTIFIERS,
    DOMAIN,
)
from .coordinator import BalancedSample, ShellySaldationCoordinator


@dataclass(frozen=True, kw_only=True)
class ShellySaldationSensorDescription(SensorEntityDescription):
    value_fn: Callable[[BalancedSample], float | None]


SENSORS: tuple[ShellySaldationSensorDescription, ...] = (
    ShellySaldationSensorDescription(
        key="net_power",
        translation_key="net_power",
        name="Balanced net power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            round(data.snapshot.net_power_w, 2)
            if data.snapshot.net_power_w is not None
            else None
        ),
    ),
    ShellySaldationSensorDescription(
        key="import_energy",
        translation_key="import_energy",
        name="Balanced grid import energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: round(data.import_total_kwh, 6),
    ),
    ShellySaldationSensorDescription(
        key="export_energy",
        translation_key="export_energy",
        name="Balanced grid export energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: round(data.export_total_kwh, 6),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = ShellySaldationCoordinator(hass, entry)
    await coordinator.async_load_previous_snapshot()
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    async_add_entities(
        [
            ShellySaldationSensor(coordinator, entry, description)
            for description in SENSORS
        ]
    )


class ShellySaldationBaseEntity(CoordinatorEntity[ShellySaldationCoordinator]):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ShellySaldationCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = self._device_info()

    def _device_info(self) -> dict:
        identifiers = {
            tuple(identifier)
            for identifier in self._entry.data.get(CONF_SOURCE_DEVICE_IDENTIFIERS, [])
        }
        connections = {
            tuple(connection)
            for connection in self._entry.data.get(CONF_SOURCE_DEVICE_CONNECTIONS, [])
        }

        device_info: dict = {"name": self._entry.title}
        if identifiers:
            device_info["identifiers"] = identifiers
        if connections:
            device_info["connections"] = connections
        if not identifiers and not connections:
            device_info["identifiers"] = {(DOMAIN, self._entry.entry_id)}
        return device_info


class ShellySaldationSensor(ShellySaldationBaseEntity, SensorEntity):
    entity_description: ShellySaldationSensorDescription

    def __init__(
        self,
        coordinator: ShellySaldationCoordinator,
        entry: ConfigEntry,
        description: ShellySaldationSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, list[str]]:
        return {
            "import_sources": self._entry.data[CONF_IMPORT_ENERGY],
            "export_sources": self._entry.data[CONF_EXPORT_ENERGY],
            "power_sources": self._entry.data.get(CONF_POWER, []),
        }
