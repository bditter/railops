"""Sensor entities for RailOps."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import DccExClient
from .const import DATA_CLIENT, DOMAIN, OPT_TRAINS
from .entity import RailOpsControllerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RailOps sensor entities."""
    client: DccExClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    async_add_entities([RailOpsControllerSensor(entry, client)])


class RailOpsControllerSensor(RailOpsControllerEntity, SensorEntity):
    """Controller entity representing the DCC-EX command station."""

    _attr_icon = "mdi:train"
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, client: DccExClient) -> None:
        """Initialize the controller sensor."""
        self._entry = entry
        self._client = client
        RailOpsControllerEntity.__init__(self, entry, client)
        self._attr_unique_id = f"controller_{entry.entry_id}"
        self._attr_name = "Controller"
        self._attr_native_value = "connected" if client.connected else "disconnected"
        self._unsub: Callable[[], None] | None = None

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
