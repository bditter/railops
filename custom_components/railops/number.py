"""Number entities for RailOps."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.number import NumberEntity
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
    """Set up RailOps number entities."""
    client: DccExClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    entities: list[NumberEntity] = []
    for train_data in entry.options.get(OPT_TRAINS, []):
        train = TrainConfig.from_dict(train_data)
        entities.append(RailOpsSpeedNumber(entry, client, train))
        if train.rpm_enabled:
            entities.append(RailOpsRpmNumber(entry, client, train))
    async_add_entities(entities)


class RailOpsSpeedNumber(RailOpsTrainEntity, NumberEntity):
    """Train speed control."""

    _attr_icon = "mdi:speedometer"
    _attr_native_min_value = 0
    _attr_native_max_value = 126
    _attr_native_step = 1
    _attr_mode = "slider"

    def __init__(
        self, entry: ConfigEntry, client: DccExClient, train: TrainConfig
    ) -> None:
        """Initialize the speed number."""
        super().__init__(entry, client, train)
        self._attr_unique_id = f"train_{entry.entry_id}_{train.train_id}_speed"
        self._attr_name = "Speed"
        self._unsub: Callable[[], None] | None = None

    @property
    def native_value(self) -> int:
        """Return current speed."""
        return self._client.get_speed(self._train.address)

    async def async_set_native_value(self, value: float) -> None:
        """Set train speed."""
        await self._client.async_set_speed(self._train, int(value))
        self.async_write_ha_state()

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
        """Refresh state after a train broadcast."""
        self.async_write_ha_state()


class RailOpsRpmNumber(RailOpsTrainEntity, NumberEntity):
    """Train sound RPM notch control."""

    _attr_icon = "mdi:gauge"
    _attr_native_step = 1
    _attr_mode = "box"

    def __init__(
        self, entry: ConfigEntry, client: DccExClient, train: TrainConfig
    ) -> None:
        """Initialize the RPM number."""
        super().__init__(entry, client, train)
        self._attr_unique_id = f"train_{entry.entry_id}_{train.train_id}_rpm"
        self._attr_name = "RPM"
        self._attr_native_min_value = -1
        self._attr_native_max_value = train.rpm_max
        self._unsub: Callable[[], None] | None = None

    @property
    def native_value(self) -> int:
        """Return current RPM notch."""
        return self._client.get_sound_level(self._train)

    async def async_set_native_value(self, value: float) -> None:
        """Set train RPM notch."""
        await self._client.async_set_sound_level(self._train, int(value))
        self.async_write_ha_state()

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
        """Refresh state after a train broadcast."""
        self.async_write_ha_state()
