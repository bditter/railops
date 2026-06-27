"""Config flow for RailOps."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import selector

from .client import DccExClient, DccExConnectionError
from .const import (
    ACCESSORY_MODE_DCC,
    ACCESSORY_MODE_FUNCTION,
    CONTROL_TYPE_BUTTON,
    CONTROL_TYPE_SWITCH,
    ATTR_ACCESSORY_ID,
    ATTR_ADDRESS,
    ATTR_CONTROL_TYPE,
    ATTR_DISABLED_FUNCTIONS,
    ATTR_FUNCTION_NAME,
    ATTR_FUNCTION_NUMBER,
    ATTR_FUNCTION_CONTROLS,
    ATTR_FUNCTIONS,
    ATTR_INVERTED,
    ATTR_MODE,
    ATTR_NAME,
    ATTR_OUTPUT,
    ATTR_PULSE_DURATION,
    ATTR_RPM_DECREASE_FUNCTION,
    ATTR_RPM_ENABLED,
    ATTR_RPM_INCREASE_FUNCTION,
    ATTR_RPM_MAX,
    ATTR_RPM_MIN,
    ATTR_SUBADDRESS,
    ATTR_TRAIN_ID,
    DEFAULT_PORT,
    DOMAIN,
    OPT_ACCESSORIES,
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
        self._selected_accessory_id: str | None = None
        self._selected_train_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the RailOps management form."""
        actions = {
            "edit_controller": "Edit controller connection",
            "add_train": "Add locomotive",
            "add_accessory": "Add accessory",
        }
        if self._trains_by_id:
            actions.update(
                {
                    "edit_train": "Edit locomotive",
                    "remove_train": "Remove locomotive",
                    "set_function_mapping": "Set function mapping",
                    "set_function_control": "Set function control type",
                    "set_function_enabled": "Enable or disable function",
                    "remove_function_mapping": "Remove function mapping",
                }
            )
        if self._accessories_by_id:
            actions.update(
                {
                    "edit_accessory": "Edit accessory",
                    "remove_accessory": "Remove accessory",
                }
            )
        if user_input is not None:
            return await getattr(self, f"async_step_{user_input['action']}")()
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required("action"): vol.In(actions)}),
        )

    async def async_step_edit_controller(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit the DCC-EX controller connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = {**user_input, CONF_PORT: int(user_input[CONF_PORT])}
            client = DccExClient(user_input[CONF_HOST], user_input[CONF_PORT])
            try:
                await client.async_test_connection()
            except DccExConnectionError:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    title=f"RailOps {user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                    data={**self._config_entry.data, **user_input},
                )
                return self.async_create_entry(
                    title="", data=dict(self._config_entry.options)
                )
        return self.async_show_form(
            step_id="edit_controller",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=self._config_entry.data.get(CONF_HOST, "")
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=self._config_entry.data.get(CONF_PORT, DEFAULT_PORT),
                    ): _whole_number_selector(1, 65535),
                }
            ),
            errors=errors,
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
                return self._create_entry(trains, self._accessories_by_id)
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
            return self._create_entry(trains, self._accessories_by_id)
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
            return self._create_entry(trains, self._accessories_by_id)
        return self.async_show_form(
            step_id="remove_train",
            data_schema=vol.Schema(
                {vol.Required(ATTR_TRAIN_ID): vol.In(self._train_names)}
            ),
        )

    async def async_step_add_accessory(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add an accessory decoder output."""
        errors: dict[str, str] = {}
        if user_input is not None:
            accessories = self._accessories_by_id
            accessory_id = user_input[ATTR_ACCESSORY_ID]
            if accessory_id in accessories:
                errors["base"] = "accessory_exists"
            else:
                accessories[accessory_id] = _normalize_accessory(user_input)
                return self._create_entry(self._trains_by_id, accessories)
        return self.async_show_form(
            step_id="add_accessory",
            data_schema=_accessory_schema(),
            errors=errors,
        )

    async def async_step_edit_accessory(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Pick an accessory to edit."""
        if user_input is not None:
            self._selected_accessory_id = user_input[ATTR_ACCESSORY_ID]
            return await self.async_step_edit_accessory_details()
        return self.async_show_form(
            step_id="edit_accessory",
            data_schema=vol.Schema(
                {vol.Required(ATTR_ACCESSORY_ID): vol.In(self._accessory_names)}
            ),
        )

    async def async_step_edit_accessory_details(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit selected accessory details."""
        accessory = self._accessories_by_id[self._selected_accessory_id]
        if user_input is not None:
            accessories = self._accessories_by_id
            accessories[self._selected_accessory_id] = _normalize_accessory(
                {
                    **accessory,
                    **user_input,
                    ATTR_ACCESSORY_ID: self._selected_accessory_id,
                }
            )
            return self._create_entry(self._trains_by_id, accessories)
        return self.async_show_form(
            step_id="edit_accessory_details",
            data_schema=_accessory_schema(accessory),
        )

    async def async_step_remove_accessory(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remove an accessory."""
        if user_input is not None:
            accessories = self._accessories_by_id
            accessories.pop(user_input[ATTR_ACCESSORY_ID], None)
            return self._create_entry(self._trains_by_id, accessories)
        return self.async_show_form(
            step_id="remove_accessory",
            data_schema=vol.Schema(
                {vol.Required(ATTR_ACCESSORY_ID): vol.In(self._accessory_names)}
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
            function_number = int(user_input[ATTR_FUNCTION_NUMBER])
            functions = {
                function_name: number
                for function_name, number in functions.items()
                if _function_number_value(number) != function_number
            }
            functions[name] = function_number
            train[ATTR_FUNCTIONS] = functions
            _set_function_control_data(train, user_input)
            return self._create_entry(trains, self._accessories_by_id)
        return self.async_show_form(
            step_id="set_function_mapping",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_TRAIN_ID): vol.In(self._train_names),
                    vol.Required(ATTR_FUNCTION_NAME): str,
                    vol.Required(ATTR_FUNCTION_NUMBER): _whole_number_selector(0, 28),
                    vol.Required(
                        ATTR_CONTROL_TYPE, default=CONTROL_TYPE_SWITCH
                    ): vol.In(
                        {
                            CONTROL_TYPE_SWITCH: "Switch",
                            CONTROL_TYPE_BUTTON: "Button",
                        }
                    ),
                    vol.Optional(ATTR_PULSE_DURATION, default=0.35): vol.All(
                        vol.Coerce(float), vol.Range(min=0.05, max=10)
                    ),
                    vol.Optional("enabled", default=True): bool,
                }
            ),
        )

    async def async_step_set_function_control(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Set function control type."""
        if user_input is not None:
            trains = self._trains_by_id
            train = trains[user_input[ATTR_TRAIN_ID]]
            _set_function_control_data(train, user_input)
            return self._create_entry(trains, self._accessories_by_id)
        return self.async_show_form(
            step_id="set_function_control",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_TRAIN_ID): vol.In(self._train_names),
                    vol.Required(ATTR_FUNCTION_NUMBER): _whole_number_selector(0, 28),
                    vol.Required(
                        ATTR_CONTROL_TYPE, default=CONTROL_TYPE_SWITCH
                    ): vol.In(
                        {
                            CONTROL_TYPE_SWITCH: "Switch",
                            CONTROL_TYPE_BUTTON: "Button",
                        }
                    ),
                    vol.Optional(ATTR_PULSE_DURATION, default=0.35): vol.All(
                        vol.Coerce(float), vol.Range(min=0.05, max=10)
                    ),
                    vol.Optional("enabled", default=True): bool,
                }
            ),
        )

    async def async_step_set_function_enabled(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Enable or disable a function entity."""
        if user_input is not None:
            trains = self._trains_by_id
            train = trains[user_input[ATTR_TRAIN_ID]]
            disabled = set(train.get(ATTR_DISABLED_FUNCTIONS, []))
            function_number = int(user_input[ATTR_FUNCTION_NUMBER])
            if user_input["enabled"]:
                disabled.discard(function_number)
            else:
                disabled.add(function_number)
            train[ATTR_DISABLED_FUNCTIONS] = sorted(disabled)
            return self._create_entry(trains, self._accessories_by_id)
        return self.async_show_form(
            step_id="set_function_enabled",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_TRAIN_ID): vol.In(self._train_names),
                    vol.Required(ATTR_FUNCTION_NUMBER): _whole_number_selector(0, 28),
                    vol.Required("enabled", default=True): bool,
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
            return self._create_entry(trains, self._accessories_by_id)
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

    @property
    def _accessories_by_id(self) -> dict[str, dict[str, Any]]:
        """Return configured accessories keyed by id."""
        return {
            accessory[ATTR_ACCESSORY_ID]: dict(accessory)
            for accessory in self._config_entry.options.get(OPT_ACCESSORIES, [])
        }

    @property
    def _accessory_names(self) -> dict[str, str]:
        """Return accessory options for selectors."""
        return {
            accessory_id: f"{item.get(ATTR_NAME, accessory_id)} ({item[ATTR_ADDRESS]})"
            for accessory_id, item in self._accessories_by_id.items()
        }

    def _create_entry(
        self,
        trains: dict[str, dict[str, Any]],
        accessories: dict[str, dict[str, Any]],
    ) -> config_entries.ConfigFlowResult:
        """Create the updated options entry."""
        options = {
            **self._config_entry.options,
            OPT_TRAINS: list(trains.values()),
            OPT_ACCESSORIES: list(accessories.values()),
        }
        return self.async_create_entry(title="", data=options)


def _train_schema(train: dict[str, Any] | None = None) -> vol.Schema:
    """Return the train form schema."""
    train = train or {}
    schema: dict[Any, Any] = {}
    if ATTR_TRAIN_ID not in train:
        schema[vol.Required(ATTR_TRAIN_ID)] = str
    schema[vol.Optional(ATTR_NAME, default=train.get(ATTR_NAME, ""))] = str
    schema[vol.Required(ATTR_ADDRESS, default=train.get(ATTR_ADDRESS, 3))] = (
        _whole_number_selector(1, 10239)
    )
    schema[vol.Optional(ATTR_RPM_ENABLED, default=train.get(ATTR_RPM_ENABLED, True))] = (
        bool
    )
    schema[vol.Optional(ATTR_RPM_MIN, default=train.get(ATTR_RPM_MIN, 0))] = (
        _whole_number_selector(0, 20)
    )
    schema[vol.Optional(ATTR_RPM_MAX, default=train.get(ATTR_RPM_MAX, 7))] = (
        _whole_number_selector(1, 20)
    )
    schema[
        vol.Optional(
            ATTR_RPM_INCREASE_FUNCTION,
            default=train.get(ATTR_RPM_INCREASE_FUNCTION, 5),
        )
    ] = _whole_number_selector(0, 28)
    schema[
        vol.Optional(
            ATTR_RPM_DECREASE_FUNCTION,
            default=train.get(ATTR_RPM_DECREASE_FUNCTION, 6),
        )
    ] = _whole_number_selector(0, 28)
    return vol.Schema(schema)


def _normalize_train(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize train options data."""
    train = {
        ATTR_TRAIN_ID: data[ATTR_TRAIN_ID],
        ATTR_NAME: data.get(ATTR_NAME) or data[ATTR_TRAIN_ID],
        ATTR_ADDRESS: int(data[ATTR_ADDRESS]),
        ATTR_RPM_ENABLED: bool(data.get(ATTR_RPM_ENABLED, True)),
        ATTR_RPM_MIN: int(data.get(ATTR_RPM_MIN, 0)),
        ATTR_RPM_MAX: max(
            int(data.get(ATTR_RPM_MIN, 0)) + 1, int(data.get(ATTR_RPM_MAX, 7))
        ),
        ATTR_RPM_INCREASE_FUNCTION: int(data.get(ATTR_RPM_INCREASE_FUNCTION, 5)),
        ATTR_RPM_DECREASE_FUNCTION: int(data.get(ATTR_RPM_DECREASE_FUNCTION, 6)),
    }
    if ATTR_FUNCTIONS in data:
        train[ATTR_FUNCTIONS] = data[ATTR_FUNCTIONS]
    if ATTR_FUNCTION_CONTROLS in data:
        train[ATTR_FUNCTION_CONTROLS] = data[ATTR_FUNCTION_CONTROLS]
    if "function_pulse_durations" in data:
        train["function_pulse_durations"] = data["function_pulse_durations"]
    if ATTR_DISABLED_FUNCTIONS in data:
        train[ATTR_DISABLED_FUNCTIONS] = list(data[ATTR_DISABLED_FUNCTIONS])
    return train


def _set_function_control_data(train: dict[str, Any], data: dict[str, Any]) -> None:
    """Set function control type and pulse duration on train options."""
    function_number = int(data[ATTR_FUNCTION_NUMBER])
    controls = dict(train.get(ATTR_FUNCTION_CONTROLS, {}))
    controls[str(function_number)] = data[ATTR_CONTROL_TYPE]
    train[ATTR_FUNCTION_CONTROLS] = controls

    if data[ATTR_CONTROL_TYPE] == CONTROL_TYPE_BUTTON:
        durations = dict(train.get("function_pulse_durations", {}))
        durations[str(function_number)] = float(data.get(ATTR_PULSE_DURATION, 0.35))
        train["function_pulse_durations"] = durations

    if "enabled" in data:
        disabled = set(train.get(ATTR_DISABLED_FUNCTIONS, []))
        if data["enabled"]:
            disabled.discard(function_number)
        else:
            disabled.add(function_number)
        train[ATTR_DISABLED_FUNCTIONS] = sorted(disabled)


def _accessory_schema(accessory: dict[str, Any] | None = None) -> vol.Schema:
    """Return the accessory form schema."""
    accessory = accessory or {}
    schema: dict[Any, Any] = {}
    if ATTR_ACCESSORY_ID not in accessory:
        schema[vol.Required(ATTR_ACCESSORY_ID)] = str
    schema[vol.Optional(ATTR_NAME, default=accessory.get(ATTR_NAME, ""))] = str
    schema[
        vol.Required(ATTR_MODE, default=accessory.get(ATTR_MODE, ACCESSORY_MODE_DCC))
    ] = vol.In(
        {
            ACCESSORY_MODE_DCC: "DCC accessory decoder",
            ACCESSORY_MODE_FUNCTION: "Function decoder output",
        }
    )
    schema[vol.Required(ATTR_ADDRESS, default=accessory.get(ATTR_ADDRESS, 1))] = (
        _whole_number_selector(1, 10239)
    )
    schema[
        vol.Optional(ATTR_SUBADDRESS, default=accessory.get(ATTR_SUBADDRESS, 0))
    ] = _whole_number_selector(0, 3)
    schema[vol.Optional(ATTR_OUTPUT, default=accessory.get(ATTR_OUTPUT, 0))] = (
        _whole_number_selector(0, 28)
    )
    schema[
        vol.Optional(ATTR_INVERTED, default=accessory.get(ATTR_INVERTED, False))
    ] = bool
    return vol.Schema(schema)


def _normalize_accessory(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize accessory options data."""
    return {
        ATTR_ACCESSORY_ID: data[ATTR_ACCESSORY_ID],
        ATTR_NAME: data.get(ATTR_NAME) or data[ATTR_ACCESSORY_ID],
        ATTR_MODE: data[ATTR_MODE],
        ATTR_ADDRESS: int(data[ATTR_ADDRESS]),
        ATTR_SUBADDRESS: int(data.get(ATTR_SUBADDRESS, 0)),
        ATTR_OUTPUT: int(data.get(ATTR_OUTPUT, 0)),
        ATTR_INVERTED: data.get(ATTR_INVERTED, False),
    }


def _whole_number_selector(min_value: int, max_value: int) -> selector.NumberSelector:
    """Return a whole-number box selector."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_value,
            max=max_value,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _normalize_function_name(name: str) -> str:
    """Normalize a friendly function name."""
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def _function_number_value(value: Any) -> int | None:
    """Return a function number from stored data."""
    number = str(value).strip().upper().removeprefix("F")
    if number.isdigit() and 0 <= int(number) <= 28:
        return int(number)
    return None
