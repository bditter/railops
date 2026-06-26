"""JMRI Trains integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .client import JmriClient, TrainConfig
from .const import (
    ATTR_ADDRESS,
    ATTR_ENABLED,
    ATTR_ENTRY_ID,
    ATTR_FORWARD,
    ATTR_FUNCTION,
    ATTR_IS_LONG_ADDRESS,
    ATTR_NAME,
    ATTR_PREFIX,
    ATTR_ROSTER_ENTRY,
    ATTR_SPEED,
    ATTR_TRAIN_ID,
    DATA_CLIENT,
    DOMAIN,
    OPT_TRAINS,
    PLATFORMS,
    SERVICE_ADD_TRAIN,
    SERVICE_ESTOP,
    SERVICE_RELEASE,
    SERVICE_REMOVE_TRAIN,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_FUNCTION,
    SERVICE_SET_SPEED,
    SERVICE_STOP,
    SERVICE_UPDATE_TRAIN,
)

TRAIN_SCHEMA = {
    vol.Required(ATTR_TRAIN_ID): cv.string,
    vol.Optional(ATTR_NAME): cv.string,
    vol.Optional(ATTR_ADDRESS): vol.Coerce(int),
    vol.Optional(ATTR_ROSTER_ENTRY): cv.string,
    vol.Optional(ATTR_IS_LONG_ADDRESS): cv.boolean,
    vol.Optional(ATTR_PREFIX): cv.string,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up JMRI Trains from a config entry."""
    session = async_get_clientsession(hass)
    client = JmriClient(
        session,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_SSL],
        entry.data[CONF_VERIFY_SSL],
    )
    try:
        await client.async_connect()
    except Exception as err:
        raise ConfigEntryNotReady(f"Unable to connect to JMRI: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_CLIENT: client}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a JMRI Trains config entry."""
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
            hass.services.async_remove(DOMAIN, SERVICE_STOP)
            hass.services.async_remove(DOMAIN, SERVICE_ESTOP)
            hass.services.async_remove(DOMAIN, SERVICE_RELEASE)
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

    async def stop(call: ServiceCall) -> None:
        client, train = _client_and_train_from_entity(hass, call)
        await client.async_stop(train)

    async def emergency_stop(call: ServiceCall) -> None:
        client, train = _client_and_train_from_entity(hass, call)
        await client.async_emergency_stop(train)

    async def release_train(call: ServiceCall) -> None:
        client, train = _client_and_train_from_entity(hass, call)
        await client.async_release_throttle(train)

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
        SERVICE_SET_SPEED,
        set_speed,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): cv.entity_id,
                vol.Required(ATTR_SPEED): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=1)
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
        SERVICE_STOP,
        stop,
        schema=vol.Schema({vol.Required("entity_id"): cv.entity_id}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ESTOP,
        emergency_stop,
        schema=vol.Schema({vol.Required("entity_id"): cv.entity_id}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RELEASE,
        release_train,
        schema=vol.Schema({vol.Required("entity_id"): cv.entity_id}),
    )


def _normalize_train(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize train service data for storage."""
    if not data.get(ATTR_ADDRESS) and not data.get(ATTR_ROSTER_ENTRY):
        raise ServiceValidationError("Provide either address or roster_entry")
    train = {
        ATTR_TRAIN_ID: data[ATTR_TRAIN_ID],
        ATTR_NAME: data.get(ATTR_NAME) or data[ATTR_TRAIN_ID],
    }
    for key in (ATTR_ADDRESS, ATTR_ROSTER_ENTRY, ATTR_IS_LONG_ADDRESS, ATTR_PREFIX):
        if key in data and data[key] not in (None, ""):
            train[key] = data[key]
    return train


def _get_entry(hass: HomeAssistant, entry_id: str | None) -> ConfigEntry:
    """Resolve a config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if entry_id:
        for entry in entries:
            if entry.entry_id == entry_id:
                return entry
        raise ServiceValidationError("Unknown JMRI Trains entry_id")
    if len(entries) != 1:
        raise ServiceValidationError(
            "entry_id is required when multiple JMRI controllers exist"
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
    """Persist trains and reload the entry so entities reflect the roster."""
    options = {**entry.options, OPT_TRAINS: list(trains.values())}
    hass.config_entries.async_update_entry(entry, options=options)
    await hass.config_entries.async_reload(entry.entry_id)


def _client_and_train_from_entity(
    hass: HomeAssistant, call: ServiceCall
) -> tuple[JmriClient, TrainConfig]:
    """Resolve service target entity into a client and train config."""
    registry = er.async_get(hass)
    entity = registry.async_get(call.data["entity_id"])
    if not entity or entity.platform != DOMAIN:
        raise ServiceValidationError("Target must be a JMRI train entity")
    if not entity.unique_id.startswith("train_"):
        raise ServiceValidationError("Target must be a JMRI train entity")
    entry_id = entity.config_entry_id
    train_id = entity.unique_id.removeprefix(f"train_{entry_id}_")
    entry = _get_entry(hass, entry_id)
    trains = _trains_by_id(entry)
    if train_id not in trains:
        raise ServiceValidationError("Train is no longer configured")
    try:
        client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
        return client, TrainConfig.from_dict(trains[train_id])
    except KeyError as err:
        raise HomeAssistantError("JMRI controller is not loaded") from err
