"""Config flow for RailOps."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .client import DccExClient, DccExConnectionError
from .const import DEFAULT_PORT, DOMAIN


class RailOpsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a RailOps config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client = DccExClient(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
            )
            try:
                await client.async_test_connection()
            except DccExConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"RailOps {user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                    data=user_input,
                    options={"trains": []},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
        )
