"""Sensor entities for RailOps."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import DccExClient, TrainConfig
from .const import DATA_CLIENT, DOMAIN, OPT_TRAINS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RailOps sensor entities."""
    client: DccExClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    entities: list[SensorEntity] = [RailOpsControllerSensor(entry, client)]
    entities.extend(
        RailOpsTrainSensor(entry, client, TrainConfig.from_dict(train))
        for train in entry.options.get(OPT_TRAINS, [])
    )
    async_add_entities(entities)


class RailOpsControllerSensor(SensorEntity):
    """Controller entity representing the DCC-EX command station."""

    _attr_icon = "mdi:train"
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, client: DccExClient) -> None:
        """Initialize the controller sensor."""
        self._entry = entry
        self._client = client
        self._attr_unique_id = f"controller_{entry.entry_id}"
        self._attr_name = "Controller"
        self._attr_native_value = "connected" if client.connected else "disconnected"
        self._unsub: Callable[[], None] | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="DCC-EX",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return controller attributes."""
        return {
            "host": self._entry.data[CONF_HOST],
            "port": self._entry.data[CONF_PORT],
            "configured_trains": len(self._entry.options.get(OPT_TRAINS, [])),
            "dcc_ex_address": self._client.address,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to connection changes."""
        self._unsub = self._client.subscribe_connection(self._connection_changed)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from connection changes."""
        if self._unsub:
            self._unsub()

    @callback
    def _connection_changed(self, connected: bool) -> None:
        """Handle connection updates."""
        self._attr_native_value = "connected" if connected else "disconnected"
        self.async_write_ha_state()


class RailOpsTrainSensor(SensorEntity):
    """Train entity backed by a DCC-EX cab address."""

    _attr_icon = "mdi:train-car"
    _attr_has_entity_name = True

    def __init__(
        self, entry: ConfigEntry, client: DccExClient, train: TrainConfig
    ) -> None:
        """Initialize the train sensor."""
        self._entry = entry
        self._client = client
        self._train = train
        self._state: dict[str, Any] = {}
        self._attr_unique_id = f"train_{entry.entry_id}_{train.train_id}"
        self._attr_name = train.name
        self._attr_native_value = "unknown"
        self._unsub: Callable[[], None] | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="DCC-EX",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return train attributes."""
        attrs = {
            "train_id": self._train.train_id,
            "address": self._train.address,
            "function_map": self._train.functions,
        }
        attrs.update(self._state)
        return attrs

    async def async_added_to_hass(self) -> None:
        """Subscribe to DCC-EX cab broadcasts."""
        self._unsub = self._client.subscribe_train(self._train.address, self._update)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from train updates."""
        if self._unsub:
            self._unsub()

    @callback
    def _update(self, data: dict[str, Any]) -> None:
        """Handle train state update."""
        self._state.update(data)
        speed = data.get("speed", self._state.get("speed"))
        direction = data.get("forward", self._state.get("forward"))
        if speed is None:
            self._attr_native_value = "available"
        else:
            label = "forward" if direction else "reverse"
            self._attr_native_value = f"{speed} {label}"
        self.async_write_ha_state()
