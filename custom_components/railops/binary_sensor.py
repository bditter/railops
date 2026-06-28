"""Binary sensor entities for RailOps."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import DccExClient, TrainConfig
from .const import DATA_CLIENT, DOMAIN, OPT_TRAINS
from .entity import RailOpsControllerEntity, RailOpsTrainEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RailOps binary sensor entities."""
    client: DccExClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    entities: list[BinarySensorEntity] = [
        RailOpsControllerConnectivityBinarySensor(entry, client)
    ]
    entities.extend(
        RailOpsTrainAcquiredBinarySensor(entry, client, TrainConfig.from_dict(train))
        for train in entry.options.get(OPT_TRAINS, [])
    )
    async_add_entities(entities)


class RailOpsControllerConnectivityBinarySensor(
    RailOpsControllerEntity, BinarySensorEntity
):
    """Controller connectivity state."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, client: DccExClient) -> None:
        """Initialize the controller connectivity sensor."""
        super().__init__(entry, client)
        self._entry = entry
        self._client = client
        self._attr_unique_id = f"controller_{entry.entry_id}_connectivity"
        self._attr_name = "Connection"
        self._unsub: Callable[[], None] | None = None

    @property
    def is_on(self) -> bool:
        """Return whether the controller is connected."""
        return self._client.connected

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
        self.async_write_ha_state()


class RailOpsTrainAcquiredBinarySensor(RailOpsTrainEntity, BinarySensorEntity):
    """Whether RailOps has marked a train as acquired."""

    _attr_icon = "mdi:train"

    def __init__(
        self, entry: ConfigEntry, client: DccExClient, train: TrainConfig
    ) -> None:
        """Initialize the acquired binary sensor."""
        super().__init__(entry, client, train)
        self._attr_unique_id = f"train_{entry.entry_id}_{train.train_id}_acquired"
        self._attr_name = "Acquired"
        self._unsub: Callable[[], None] | None = None

    @property
    def is_on(self) -> bool:
        """Return acquired state."""
        return self._client.is_train_acquired(self._train)

    async def async_added_to_hass(self) -> None:
        """Subscribe to train updates."""
        self._unsub = self._client.subscribe_train(
            self._train.address, self._train_updated
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from train updates."""
        if self._unsub:
            self._unsub()

    @callback
    def _train_updated(self, data: dict) -> None:
        """Refresh state after local or DCC-EX train updates."""
        self.async_write_ha_state()
