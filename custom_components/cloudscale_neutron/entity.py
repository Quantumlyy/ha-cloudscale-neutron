"""Base entity for the CloudScale Neutron integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .client import NeutronClient
from .const import DOMAIN


class NeutronEntity(Entity):
    """Entity that updates when the client receives a reading."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, client: NeutronClient, key: str) -> None:
        self._client = client
        self._attr_unique_id = f"{client.module_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client.module_id)},
            name=f"Neutron {client.module_id}",
            manufacturer="Cloud Scales",
            model="CS-NEUTRON",
        )

    @property
    def available(self) -> bool:
        return self._client.available

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._client.async_add_listener(self.async_write_ha_state))
