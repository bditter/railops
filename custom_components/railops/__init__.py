"""RailOps integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .client import DccExClient, TrainConfig
from .const import (
    ATTR_ADDRESS,
    ATTR_DURATION,
    ATTR_ENABLED,
    ATTR_ENTRY_ID,
    ATTR_FORWARD,
    ATTR_FUNCTION,
    ATTR_FUNCTION_NAME,
    ATTR_FUNCTION_NUMBER,
    ATTR_FUNCTIONS,
    ATTR_NAME,
    ATTR_SPEED,
    ATTR_TRACK,
    ATTR_TRAIN_ID,
    DATA_CLIENT,
    DOMAIN,
    OPT_TRAINS,
    PLATFORMS,
    SERVICE_ADD_TRAIN,
    SERVICE_ESTOP,
    SERVICE_REMOVE_TRAIN,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_FUNCTION,
    SERVICE_REMOVE_FUNCTION_MAPPING,
    SERVICE_SET_FUNCTION_MOMENTARY,
    SERVICE_SET_FUNCTION_MAPPING,
    SERVICE_SET_POWER,
    SERVICE_SET_SPEED,
    SERVICE_STOP,
    SERVICE_UPDATE_TRAIN,
)

TRAIN_SCHEMA = {
    vol.Required(ATTR_TRAIN_ID): cv.string,
    vol.Optional(ATTR_NAME): cv.string,
    vol.Required(ATTR_ADDRESS): vol.All(vol.Coerce(int), vol.Range(min=1, max=10239)),
    vol.Optional(ATTR_FUNCTIONS): dict,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RailOps from a config entry."""
    client = DccExClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
    )
    try:
        await client.async_connect()
    except Exception as err:
        raise ConfigEntryNotReady(f"Unable to connect to DCC-EX: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_CLIENT: client}
    _async_remove_legacy_train_entities(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await client.async_start_polling(
        [TrainConfig.from_dict(train) for train in entry.options.get(OPT_TRAINS, [])]
    )
    await _async_register_services(hass)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload RailOps when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_remove_legacy_train_entities(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove entities from earlier RailOps train telemetry/function designs."""
    registry = er.async_get(hass)
    for train in entry.options.get(OPT_TRAINS, []):
        train_id = train[ATTR_TRAIN_ID]
        train_config = TrainConfig.from_dict(train)
        legacy_unique_ids = [f"train_{entry.entry_id}_{train_id}"]
        legacy_unique_ids.extend(
            f"train_{entry.entry_id}_{train_id}_function_{name}"
            for name in train_config.functions
        )
        for unique_id in legacy_unique_ids:
            entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            if entity_id:
                registry.async_remove(entity_id)
            entity_id = registry.async_get_entity_id("switch", DOMAIN, unique_id)
            if entity_id:
                registry.async_remove(entity_id)
        for function_number in range(29):
            switch_unique_id = (
                f"train_{entry.entry_id}_{train_id}_function_{function_number}"
            )
            button_unique_id = (
                f"train_{entry.entry_id}_{train_id}_function_{function_number}_button"
            )
            if train_config.function_control_type(function_number) == "button":
                entity_id = registry.async_get_entity_id(
                    "switch", DOMAIN, switch_unique_id
                )
            else:
                entity_id = registry.async_get_entity_id(
                    "button", DOMAIN, button_unique_id
                )
            if entity_id:
                registry.async_remove(entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a RailOps config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data[DATA_CLIENT].async_close()
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_ADD_TRAIN)
            hass.services.async_remove(DOMAIN, SERVICE_UPDATE_TRAIN)
            hass.services.async_remove(DOMAIN, SERVICE_REMOVE_TRAIN)
            hass.services.async_remove(DOMAIN, SERVICE_SET_SPEED)
            hass.services.async_remove(DOMAIN, SERVICE_SET_DIRECTION)
            hass.services.async_remove(DOMAIN, SERVICE_SET_FUNCTION)
            hass.services.async_remove(DOMAIN, SERVICE_SET_FUNCTION_MOMENTARY)
            hass.services.async_remove(DOMAIN, SERVICE_SET_FUNCTION_MAPPING)
            hass.services.async_remove(DOMAIN, SERVICE_REMOVE_FUNCTION_MAPPING)
            hass.services.async_remove(DOMAIN, SERVICE_SET_POWER)
            hass.services.async_remove(DOMAIN, SERVICE_STOP)
            hass.services.async_remove(DOMAIN, SERVICE_ESTOP)
    return unload_ok


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_SPEED):
        return

    async def add_train(call: ServiceCall) -> None:
        entry = _get_entry(hass, call.data.get(ATTR_ENTRY_ID))
        train = _normalize_train(call.data)
        trains = _trains_by_id(entry)
        if train[ATTR_TRAIN_ID] in trains:
            raise ServiceValidationError("Train already exists")
        trains[train[ATTR_TRAIN_ID]] = train
        await _save_trains(hass, entry, trains)

    async def update_train(call: ServiceCall) -> None:
        entry = _get_entry(hass, call.data.get(ATTR_ENTRY_ID))
        train_id = call.data[ATTR_TRAIN_ID]
        trains = _trains_by_id(entry)
        if train_id not in trains:
            raise ServiceValidationError("Train does not exist")
        updated = {**trains[train_id], **dict(call.data)}
        trains[train_id] = _normalize_train(updated)
        await _save_trains(hass, entry, trains)

    async def remove_train(call: ServiceCall) -> None:
        entry = _get_entry(hass, call.data.get(ATTR_ENTRY_ID))
        train_id = call.data[ATTR_TRAIN_ID]
        trains = _trains_by_id(entry)
        if train_id not in trains:
            raise ServiceValidationError("Train does not exist")
        trains.pop(train_id)
        await _save_trains(hass, entry, trains)

    async def set_function_mapping(call: ServiceCall) -> None:
        entry, train_id, trains = _entry_train_and_trains_from_entity(hass, call)
        functions = dict(trains[train_id].get(ATTR_FUNCTIONS, {}))
        name = _normalize_function_name(call.data[ATTR_FUNCTION_NAME])
        functions[name] = call.data[ATTR_FUNCTION_NUMBER]
        trains[train_id][ATTR_FUNCTIONS] = functions
        await _save_trains(hass, entry, trains)

    async def remove_function_mapping(call: ServiceCall) -> None:
        entry, train_id, trains = _entry_train_and_trains_from_entity(hass, call)
        functions = dict(trains[train_id].get(ATTR_FUNCTIONS, {}))
        functions.pop(_normalize_function_name(call.data[ATTR_FUNCTION_NAME]), None)
        trains[train_id][ATTR_FUNCTIONS] = functions
        await _save_trains(hass, entry, trains)

    async def set_power(call: ServiceCall) -> None:
        entry = _get_entry(hass, call.data.get(ATTR_ENTRY_ID))
        client: DccExClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
        await client.async_set_power(call.data[ATTR_ENABLED], call.data[ATTR_TRACK])

    async def set_speed(call: ServiceCall) -> None:
        client, train = _client_and_train_from_entity(hass, call)
        await client.async_set_speed(train, call.data[ATTR_SPEED])

    async def set_direction(call: ServiceCall) -> None:
        client, train = _client_and_train_from_entity(hass, call)
        await client.async_set_direction(train, call.data[ATTR_FORWARD])

    async def set_function(call: ServiceCall) -> None:
        client, train = _client_and_train_from_entity(hass, call)
        await client.async_set_function(
            train, call.data[ATTR_FUNCTION], call.data[ATTR_ENABLED]
        )

    async def pulse_function(call: ServiceCall) -> None:
        client, train = _client_and_train_from_entity(hass, call)
        await client.async_pulse_function(
            train, call.data[ATTR_FUNCTION], call.data[ATTR_DURATION]
        )

    async def stop(call: ServiceCall) -> None:
        client, train = _client_and_train_from_entity(hass, call)
        await client.async_stop(train)

    async def emergency_stop(call: ServiceCall) -> None:
        if "entity_id" in call.data:
            client, train = _client_and_train_from_entity(hass, call)
            await client.async_emergency_stop(train)
            return
        entry = _get_entry(hass, call.data.get(ATTR_ENTRY_ID))
        client: DccExClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
        await client.async_emergency_stop()

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_TRAIN,
        add_train,
        schema=vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string, **TRAIN_SCHEMA}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_TRAIN,
        update_train,
        schema=vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string, **TRAIN_SCHEMA}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_TRAIN,
        remove_train,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_ENTRY_ID): cv.string,
                vol.Required(ATTR_TRAIN_ID): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_FUNCTION_MAPPING,
        set_function_mapping,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): cv.entity_id,
                vol.Required(ATTR_FUNCTION_NAME): cv.string,
                vol.Required(ATTR_FUNCTION_NUMBER): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=28)
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_FUNCTION_MAPPING,
        remove_function_mapping,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): cv.entity_id,
                vol.Required(ATTR_FUNCTION_NAME): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SPEED,
        set_speed,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): cv.entity_id,
                vol.Required(ATTR_SPEED): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=126)
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DIRECTION,
        set_direction,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): cv.entity_id,
                vol.Required(ATTR_FORWARD): cv.boolean,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_FUNCTION,
        set_function,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): cv.entity_id,
                vol.Required(ATTR_FUNCTION): vol.Any(vol.Coerce(int), cv.string),
                vol.Required(ATTR_ENABLED): cv.boolean,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_FUNCTION_MOMENTARY,
        pulse_function,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): cv.entity_id,
                vol.Required(ATTR_FUNCTION): vol.Any(vol.Coerce(int), cv.string),
                vol.Optional(ATTR_DURATION, default=0.5): vol.All(
                    vol.Coerce(float), vol.Range(min=0.05, max=10)
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_POWER,
        set_power,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_ENTRY_ID): cv.string,
                vol.Required(ATTR_ENABLED): cv.boolean,
                vol.Optional(ATTR_TRACK, default="MAIN"): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP,
        stop,
        schema=vol.Schema({vol.Required("entity_id"): cv.entity_id}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ESTOP,
        emergency_stop,
        schema=vol.Schema(
            {
                vol.Optional("entity_id"): cv.entity_id,
                vol.Optional(ATTR_ENTRY_ID): cv.string,
            }
        ),
    )


def _normalize_train(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize train service data for storage."""
    train = {
        ATTR_TRAIN_ID: data[ATTR_TRAIN_ID],
        ATTR_NAME: data.get(ATTR_NAME) or data[ATTR_TRAIN_ID],
        ATTR_ADDRESS: data[ATTR_ADDRESS],
    }
    if ATTR_FUNCTIONS in data:
        train[ATTR_FUNCTIONS] = _normalize_function_map(data[ATTR_FUNCTIONS])
    return train


def _normalize_function_name(name: str) -> str:
    """Normalize a friendly function name."""
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_function_map(functions: dict[str, Any]) -> dict[str, int]:
    """Normalize service-provided function mappings."""
    return {
        _normalize_function_name(name): int(str(number).upper().removeprefix("F"))
        for name, number in functions.items()
        if str(number).upper().removeprefix("F").isdigit()
        and 0 <= int(str(number).upper().removeprefix("F")) <= 28
    }


def _get_entry(hass: HomeAssistant, entry_id: str | None) -> ConfigEntry:
    """Resolve a config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if entry_id:
        for entry in entries:
            if entry.entry_id == entry_id:
                return entry
        raise ServiceValidationError("Unknown RailOps entry_id")
    if len(entries) != 1:
        raise ServiceValidationError(
            "entry_id is required when multiple RailOps controllers exist"
        )
    return entries[0]


def _trains_by_id(entry: ConfigEntry) -> dict[str, dict[str, Any]]:
    """Return configured trains keyed by train id."""
    return {
        train[ATTR_TRAIN_ID]: dict(train)
        for train in entry.options.get(OPT_TRAINS, [])
    }


async def _save_trains(
    hass: HomeAssistant, entry: ConfigEntry, trains: dict[str, dict[str, Any]]
) -> None:
    """Persist trains and reload the entry so entities reflect the train list."""
    options = {**entry.options, OPT_TRAINS: list(trains.values())}
    hass.config_entries.async_update_entry(entry, options=options)
    await hass.config_entries.async_reload(entry.entry_id)


def _client_and_train_from_entity(
    hass: HomeAssistant, call: ServiceCall
) -> tuple[DccExClient, TrainConfig]:
    """Resolve service target entity into a client and train config."""
    entry, train_id, trains = _entry_train_and_trains_from_entity(hass, call)
    try:
        client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
        return client, TrainConfig.from_dict(trains[train_id])
    except KeyError as err:
        raise HomeAssistantError("DCC-EX controller is not loaded") from err


def _entry_train_and_trains_from_entity(
    hass: HomeAssistant, call: ServiceCall
) -> tuple[ConfigEntry, str, dict[str, dict[str, Any]]]:
    """Resolve service target entity into entry, train id, and stored trains."""
    registry = er.async_get(hass)
    entity = registry.async_get(call.data["entity_id"])
    if not entity or entity.platform != DOMAIN:
        raise ServiceValidationError("Target must be a RailOps train entity")
    if not entity.unique_id.startswith("train_"):
        raise ServiceValidationError("Target must be a RailOps train entity")
    entry_id = entity.config_entry_id
    train_id = entity.unique_id.removeprefix(f"train_{entry_id}_")
    entry = _get_entry(hass, entry_id)
    trains = _trains_by_id(entry)
    if train_id not in trains:
        raise ServiceValidationError("Train is no longer configured")
    return entry, train_id, trains
