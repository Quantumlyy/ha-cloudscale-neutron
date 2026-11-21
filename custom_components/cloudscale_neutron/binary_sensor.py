"""Stability sensor for the CloudScale Neutron integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import NeutronClient
from .entity import NeutronEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the binary sensor."""
    async_add_entities([NeutronStableSensor(entry.runtime_data)])


class NeutronStableSensor(NeutronEntity, BinarySensorEntity):
    """On while the scale reports a stable weight."""

    _attr_translation_key = "stable"

    def __init__(self, client: NeutronClient) -> None:
        super().__init__(client, "stable")

    @property
    def is_on(self) -> bool | None:
        if (reading := self._client.reading) is None:
            return None
        return reading.stable
