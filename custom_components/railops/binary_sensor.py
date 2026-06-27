"""Binary sensor entities for RailOps."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import DccExClient, TrainConfig
from .const import DATA_CLIENT, DOMAIN, OPT_TRAINS
from .entity import RailOpsTrainEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RailOps binary sensor entities."""
    client: DccExClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    async_add_entities(
        RailOpsTrainAcquiredBinarySensor(entry, client, TrainConfig.from_dict(train))
        for train in entry.options.get(OPT_TRAINS, [])
    )


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
