from __future__ import annotations

import re
from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


@dataclass(frozen=True)
class DiscoveredSources:
    import_energy: tuple[str, ...]
    export_energy: tuple[str, ...]
    power: tuple[str, ...]
    device_name: str | None
    device_identifiers: tuple[tuple[str, str], ...]
    device_connections: tuple[tuple[str, str], ...]


def discover_sources_for_device(
    hass: HomeAssistant,
    device_id: str,
) -> DiscoveredSources:
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    device_name = None
    device_identifiers: tuple[tuple[str, str], ...] = ()
    device_connections: tuple[tuple[str, str], ...] = ()
    if device is not None:
        device_name = device.name_by_user or device.name
        device_identifiers = tuple(sorted(device.identifiers))
        device_connections = tuple(sorted(device.connections))

    entries = [
        entry
        for entry in er.async_entries_for_device(entity_registry, device_id)
        if entry.domain == "sensor" and entry.disabled_by is None
    ]

    energy_entries = [
        entry
        for entry in entries
        if _has_device_class(hass, entry.entity_id, SensorDeviceClass.ENERGY)
        or _state_unit(hass, entry.entity_id)
        in {
            UnitOfEnergy.WATT_HOUR,
            UnitOfEnergy.KILO_WATT_HOUR,
            UnitOfEnergy.MEGA_WATT_HOUR,
        }
    ]
    power_entries = [
        entry
        for entry in entries
        if _has_device_class(hass, entry.entity_id, SensorDeviceClass.POWER)
        or _state_unit(hass, entry.entity_id)
        in {
            UnitOfPower.WATT,
            UnitOfPower.KILO_WATT,
        }
    ]

    export_energy = [
        entry.entity_id for entry in energy_entries if _looks_like_export(entry)
    ]
    import_energy = [
        entry.entity_id for entry in energy_entries if not _looks_like_export(entry)
    ]

    import_energy = _prefer_phase_entities(import_energy)
    export_energy = _prefer_phase_entities(export_energy)
    power = _prefer_phase_entities([entry.entity_id for entry in power_entries])

    return DiscoveredSources(
        import_energy=tuple(sorted(import_energy, key=_natural_sort_key)),
        export_energy=tuple(sorted(export_energy, key=_natural_sort_key)),
        power=tuple(sorted(power, key=_natural_sort_key)),
        device_name=device_name,
        device_identifiers=device_identifiers,
        device_connections=device_connections,
    )


def _has_device_class(
    hass: HomeAssistant,
    entity_id: str,
    device_class: SensorDeviceClass,
) -> bool:
    return _state_device_class(hass, entity_id) in {device_class, device_class.value}


def _state_device_class(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    if state is None:
        return None
    return state.attributes.get("device_class")


def _state_unit(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    if state is None:
        return None
    return state.attributes.get("unit_of_measurement")


def _looks_like_export(entry: er.RegistryEntry) -> bool:
    label = _entry_label(entry)
    return any(
        token in label
        for token in (
            "return",
            "returned",
            "ruck",
            "rueck",
            "zuruck",
            "zurueck",
            "export",
            "feed",
            "einspeis",
        )
    )


def _prefer_phase_entities(entity_ids: list[str]) -> list[str]:
    phase_entities = [
        entity_id for entity_id in entity_ids if _looks_like_phase_entity(entity_id)
    ]
    if phase_entities:
        return phase_entities

    non_total_entities = [
        entity_id for entity_id in entity_ids if "total" not in _normalize(entity_id)
    ]
    if non_total_entities:
        return non_total_entities

    return entity_ids


def _looks_like_phase_entity(entity_id: str) -> bool:
    label = _normalize(entity_id)
    return bool(
        re.search(r"(^|_)(l[123]|phase_[abc123]|channel_[abc123]|[abc])($|_)", label)
    )


def _entry_label(entry: er.RegistryEntry) -> str:
    return _normalize(
        " ".join(
            value
            for value in (
                entry.entity_id,
                getattr(entry, "original_name", None),
                getattr(entry, "name", None),
                entry.unique_id,
                getattr(entry, "translation_key", None),
            )
            if value
        )
    )


def _normalize(value: str) -> str:
    return (
        value.lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("-", "_")
        .replace(" ", "_")
    )


def _natural_sort_key(value: str) -> tuple:
    return tuple(
        int(part) if part.isdigit() else part
        for part in re.split(r"(\d+)", _normalize(value))
    )
