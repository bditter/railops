"""Config flow for RailOps."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .client import DccExClient, DccExConnectionError
from .const import (
    ATTR_ADDRESS,
    ATTR_FUNCTION_NAME,
    ATTR_FUNCTION_NUMBER,
    ATTR_FUNCTIONS,
    ATTR_NAME,
    ATTR_TRAIN_ID,
    DEFAULT_PORT,
    DOMAIN,
    OPT_TRAINS,
)


class RailOpsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a RailOps config flow."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return RailOpsOptionsFlow(config_entry)

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


class RailOpsOptionsFlow(config_entries.OptionsFlow):
    """Handle RailOps options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._selected_train_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the RailOps management form."""
        actions = {
            "add_train": "Add locomotive",
        }
        if self._trains_by_id:
            actions.update(
                {
                    "edit_train": "Edit locomotive",
                    "remove_train": "Remove locomotive",
                    "set_function_mapping": "Set function mapping",
                    "remove_function_mapping": "Remove function mapping",
                }
            )
        if user_input is not None:
            return await getattr(self, f"async_step_{user_input['action']}")()
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required("action"): vol.In(actions)}),
        )

    async def async_step_add_train(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a train."""
        errors: dict[str, str] = {}
        if user_input is not None:
            trains = self._trains_by_id
            train_id = user_input[ATTR_TRAIN_ID]
            if train_id in trains:
                errors["base"] = "train_exists"
            else:
                trains[train_id] = _normalize_train(user_input)
                return self._create_entry(trains)
        return self.async_show_form(
            step_id="add_train",
            data_schema=_train_schema(),
            errors=errors,
        )

    async def async_step_edit_train(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Pick a train to edit."""
        if user_input is not None:
            self._selected_train_id = user_input[ATTR_TRAIN_ID]
            return await self.async_step_edit_train_details()
        return self.async_show_form(
            step_id="edit_train",
            data_schema=vol.Schema(
                {vol.Required(ATTR_TRAIN_ID): vol.In(self._train_names)}
            ),
        )

    async def async_step_edit_train_details(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit selected train details."""
        train = self._trains_by_id[self._selected_train_id]
        if user_input is not None:
            trains = self._trains_by_id
            trains[self._selected_train_id] = _normalize_train(
                {**train, **user_input, ATTR_TRAIN_ID: self._selected_train_id}
            )
            return self._create_entry(trains)
        return self.async_show_form(
            step_id="edit_train_details",
            data_schema=_train_schema(train),
        )

    async def async_step_remove_train(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remove a train."""
        if user_input is not None:
            trains = self._trains_by_id
            trains.pop(user_input[ATTR_TRAIN_ID], None)
            return self._create_entry(trains)
        return self.async_show_form(
            step_id="remove_train",
            data_schema=vol.Schema(
                {vol.Required(ATTR_TRAIN_ID): vol.In(self._train_names)}
            ),
        )

    async def async_step_set_function_mapping(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Set a friendly function mapping."""
        if user_input is not None:
            trains = self._trains_by_id
            train = trains[user_input[ATTR_TRAIN_ID]]
            functions = dict(train.get(ATTR_FUNCTIONS, {}))
            name = _normalize_function_name(user_input[ATTR_FUNCTION_NAME])
            functions[name] = user_input[ATTR_FUNCTION_NUMBER]
            train[ATTR_FUNCTIONS] = functions
            return self._create_entry(trains)
        return self.async_show_form(
            step_id="set_function_mapping",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_TRAIN_ID): vol.In(self._train_names),
                    vol.Required(ATTR_FUNCTION_NAME): str,
                    vol.Required(ATTR_FUNCTION_NUMBER): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=28)
                    ),
                }
            ),
        )

    async def async_step_remove_function_mapping(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remove a friendly function mapping."""
        if user_input is not None:
            trains = self._trains_by_id
            train = trains[user_input[ATTR_TRAIN_ID]]
            functions = dict(train.get(ATTR_FUNCTIONS, {}))
            function_name = _normalize_function_name(user_input[ATTR_FUNCTION_NAME])
            functions.pop(function_name, None)
            train[ATTR_FUNCTIONS] = functions
            return self._create_entry(trains)
        return self.async_show_form(
            step_id="remove_function_mapping",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_TRAIN_ID): vol.In(self._train_names),
                    vol.Required(ATTR_FUNCTION_NAME): str,
                }
            ),
        )

    @property
    def _trains_by_id(self) -> dict[str, dict[str, Any]]:
        """Return configured trains keyed by id."""
        return {
            train[ATTR_TRAIN_ID]: dict(train)
            for train in self._config_entry.options.get(OPT_TRAINS, [])
        }

    @property
    def _train_names(self) -> dict[str, str]:
        """Return train options for selectors."""
        return {
            train_id: f"{train.get(ATTR_NAME, train_id)} ({train[ATTR_ADDRESS]})"
            for train_id, train in self._trains_by_id.items()
        }

    def _create_entry(
        self, trains: dict[str, dict[str, Any]]
    ) -> config_entries.ConfigFlowResult:
        """Create the updated options entry."""
        options = {**self._config_entry.options, OPT_TRAINS: list(trains.values())}
        return self.async_create_entry(title="", data=options)


def _train_schema(train: dict[str, Any] | None = None) -> vol.Schema:
    """Return the train form schema."""
    train = train or {}
    schema: dict[Any, Any] = {}
    if ATTR_TRAIN_ID not in train:
        schema[vol.Required(ATTR_TRAIN_ID)] = str
    schema[vol.Optional(ATTR_NAME, default=train.get(ATTR_NAME, ""))] = str
    schema[vol.Required(ATTR_ADDRESS, default=train.get(ATTR_ADDRESS, 3))] = vol.All(
        vol.Coerce(int), vol.Range(min=1, max=10239)
    )
    return vol.Schema(schema)


def _normalize_train(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize train options data."""
    train = {
        ATTR_TRAIN_ID: data[ATTR_TRAIN_ID],
        ATTR_NAME: data.get(ATTR_NAME) or data[ATTR_TRAIN_ID],
        ATTR_ADDRESS: data[ATTR_ADDRESS],
    }
    if ATTR_FUNCTIONS in data:
        train[ATTR_FUNCTIONS] = data[ATTR_FUNCTIONS]
    return train


def _normalize_function_name(name: str) -> str:
    """Normalize a friendly function name."""
    return name.strip().lower().replace(" ", "_").replace("-", "_")
