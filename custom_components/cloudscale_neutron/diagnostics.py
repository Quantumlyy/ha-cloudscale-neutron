"""Diagnostics download for the CloudScale Neutron integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .client import NeutronClient
from .const import CONF_HOST, CONF_MODULE_ID, CONF_PIN

TO_REDACT = {CONF_MODULE_ID, CONF_PIN, CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return what the integration currently knows, without account values."""
    client: NeutronClient = entry.runtime_data
    return {
        "config": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "available": client.available,
        "reply_time_seconds": client.reply_time,
        "reading": asdict(client.reading) if client.reading else None,
        # Every field of the scale's settings reply, as the module sent it.
        "scale_settings": dict(client.settings.raw) if client.settings else None,
    }
