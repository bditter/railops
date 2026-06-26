"""Sensor entities for JMRI Trains."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import JmriClient, TrainConfig
from .const import DATA_CLIENT, DOMAIN, OPT_TRAINS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up JMRI sensor entities."""
    client: JmriClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    entities: list[SensorEntity] = [JmriControllerSensor(entry, client)]
    entities.extend(
        JmriTrainSensor(entry, client, TrainConfig.from_dict(train))
        for train in entry.options.get(OPT_TRAINS, [])
    )
    async_add_entities(entities)


class JmriControllerSensor(SensorEntity):
    """Controller entity representing the JMRI server."""

    _attr_icon = "mdi:train"
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, client: JmriClient) -> None:
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
            manufacturer="JMRI",
            configuration_url=self._client.base_url,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return controller attributes."""
        return {
            "host": self._entry.data[CONF_HOST],
            "port": self._entry.data[CONF_PORT],
            "configured_trains": len(self._entry.options.get(OPT_TRAINS, [])),
            "websocket_url": self._client.websocket_url,
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


class JmriTrainSensor(SensorEntity):
    """Train entity backed by a JMRI throttle."""

    _attr_icon = "mdi:train-car"
    _attr_has_entity_name = True

    def __init__(
        self, entry: ConfigEntry, client: JmriClient, train: TrainConfig
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
            manufacturer="JMRI",
            configuration_url=self._client.base_url,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return train attributes."""
        attrs = {
            "train_id": self._train.train_id,
            "address": self._train.address,
            "roster_entry": self._train.roster_entry,
            "prefix": self._train.prefix,
        }
        attrs.update(self._state)
        return attrs

    async def async_added_to_hass(self) -> None:
        """Subscribe to JMRI throttle updates."""
        self._unsub = self._client.subscribe_train(self._train.train_id, self._update)
        await self._client.async_acquire_throttle(self._train)

    async def async_will_remove_from_hass(self) -> None:
        """Release the train throttle when removed."""
        if self._unsub:
            self._unsub()
        await self._client.async_release_throttle(self._train)

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
            self._attr_native_value = f"{speed:.2f} {label}"
        self.async_write_ha_state()
