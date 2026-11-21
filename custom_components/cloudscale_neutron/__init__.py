"""CloudScale Neutron scale, read through the Scale Monitor cloud."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .client import NeutronClient
from .const import (
    CONF_HOST,
    CONF_MODULE_ID,
    CONF_PATH,
    CONF_PIN,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SMOOTHING,
    CONF_SMOOTHING_WINDOW,
    CONF_STABLE_ONLY,
    CONF_TLS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SMOOTHING,
    DEFAULT_SMOOTHING_WINDOW,
    DEFAULT_STABLE_ONLY,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Neutron module from a config entry."""
    data = entry.data
    options = entry.options
    client = NeutronClient(
        hass,
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        path=data[CONF_PATH],
        tls=data[CONF_TLS],
        module_id=data[CONF_MODULE_ID],
        pin=data[CONF_PIN],
        scan_interval=float(
            options.get(
                CONF_SCAN_INTERVAL, data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            )
        ),
        smoothing=options.get(CONF_SMOOTHING, DEFAULT_SMOOTHING),
        smoothing_window=float(
            options.get(CONF_SMOOTHING_WINDOW, DEFAULT_SMOOTHING_WINDOW)
        ),
        stable_only=options.get(CONF_STABLE_ONLY, DEFAULT_STABLE_ONLY),
    )
    await client.async_start()
    entry.runtime_data = client
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)
