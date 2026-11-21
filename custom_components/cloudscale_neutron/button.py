"""Tare and zero buttons for the CloudScale Neutron integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import NeutronClient
from .const import COMMAND_CLEAR_TARE, COMMAND_TARE, COMMAND_ZERO, POLL_COMMAND
from .entity import NeutronEntity

BUTTONS = {
    "tare": COMMAND_TARE,
    "zero": COMMAND_ZERO,
    "clear_tare": COMMAND_CLEAR_TARE,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the buttons."""
    client: NeutronClient = entry.runtime_data
    async_add_entities(
        NeutronCommandButton(client, key, command) for key, command in BUTTONS.items()
    )


class NeutronCommandButton(NeutronEntity, ButtonEntity):
    """Sends one command to the scale."""

    def __init__(self, client: NeutronClient, key: str, command: str) -> None:
        super().__init__(client, key)
        self._attr_translation_key = key
        self._command = command

    async def async_press(self) -> None:
        if not self._client.async_send(self._command):
            raise HomeAssistantError("The scale is not connected")
        # Read back straight away so the new tare or zero shows without
        # waiting for the next poll.
        self._client.async_send(POLL_COMMAND, qos=0)
