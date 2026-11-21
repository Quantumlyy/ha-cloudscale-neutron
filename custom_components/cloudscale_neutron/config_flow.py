"""Config flow for the CloudScale Neutron integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .client import test_connection
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
    DEFAULT_PATH,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SMOOTHING,
    DEFAULT_SMOOTHING_WINDOW,
    DEFAULT_STABLE_ONLY,
    DEFAULT_TLS,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MAX_SMOOTHING_WINDOW,
    MIN_SCAN_INTERVAL,
    MIN_SMOOTHING_WINDOW,
)
from .smoothing import SMOOTHING_METHODS


def _seconds(minimum: float, maximum: float) -> selector.NumberSelector:
    """Number box for a duration in seconds, in steps of 0.1."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=0.1,
            unit_of_measurement="s",
            mode=selector.NumberSelectorMode.BOX,
        )
    )


_INTERVAL = _seconds(MIN_SCAN_INTERVAL, MAX_SCAN_INTERVAL)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODULE_ID): str,
        vol.Required(CONF_PIN): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Required(CONF_PATH, default=DEFAULT_PATH): str,
        vol.Required(CONF_TLS, default=DEFAULT_TLS): bool,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): _INTERVAL,
    }
)


class NeutronConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup form."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_MODULE_ID] = user_input[CONF_MODULE_ID].strip()
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            module_id = user_input[CONF_MODULE_ID]
            await self.async_set_unique_id(module_id)
            self._abort_if_unique_id_configured()
            error = await self.hass.async_add_executor_job(
                test_connection,
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_PATH],
                user_input[CONF_TLS],
                module_id,
                user_input[CONF_PIN],
            )
            if error is None:
                return self.async_create_entry(
                    title=f"Neutron {module_id}", data=user_input
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NeutronOptionsFlow()


class NeutronOptionsFlow(OptionsFlow):
    """Change the poll interval and smoothing."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        entry = self.config_entry
        current = {
            CONF_SCAN_INTERVAL: entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            CONF_SMOOTHING: DEFAULT_SMOOTHING,
            CONF_SMOOTHING_WINDOW: DEFAULT_SMOOTHING_WINDOW,
            CONF_STABLE_ONLY: DEFAULT_STABLE_ONLY,
            **entry.options,
        }
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL): _INTERVAL,
                vol.Required(CONF_SMOOTHING): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=SMOOTHING_METHODS,
                        translation_key=CONF_SMOOTHING,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_SMOOTHING_WINDOW): _seconds(
                    MIN_SMOOTHING_WINDOW, MAX_SMOOTHING_WINDOW
                ),
                vol.Required(CONF_STABLE_ONLY): bool,
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )
