"""Switch entities for RailOps."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import AccessoryConfig, DccExClient, TrainConfig
from .const import DATA_CLIENT, DOMAIN, OPT_ACCESSORIES, OPT_TRAINS
from .entity import RailOpsControllerEntity, RailOpsTrainEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RailOps switch entities."""
    client: DccExClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    entities: list[SwitchEntity] = [RailOpsPowerSwitch(entry, client)]
    for train_data in entry.options.get(OPT_TRAINS, []):
        train = TrainConfig.from_dict(train_data)
        entities.extend(
            RailOpsFunctionSwitch(entry, client, train, function_number)
            for function_number in range(29)
        )
    entities.extend(
        RailOpsAccessorySwitch(entry, client, AccessoryConfig.from_dict(accessory))
        for accessory in entry.options.get(OPT_ACCESSORIES, [])
    )
    async_add_entities(entities)


class RailOpsPowerSwitch(RailOpsControllerEntity, SwitchEntity):
    """Track power switch."""

    _attr_icon = "mdi:power"

    def __init__(self, entry: ConfigEntry, client: DccExClient) -> None:
        """Initialize the power switch."""
        super().__init__(entry, client)
        self._attr_unique_id = f"controller_{entry.entry_id}_track_power"
        self._attr_name = "Track Power"

    @property
    def is_on(self) -> bool | None:
        """Return the last commanded power state."""
        return self._client.get_power_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn track power on."""
        await self._client.async_set_power(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn track power off."""
        await self._client.async_set_power(False)
        self.async_write_ha_state()


class RailOpsFunctionSwitch(RailOpsTrainEntity, SwitchEntity):
    """DCC function switch."""

    _attr_icon = "mdi:tune-variant"

    def __init__(
        self,
        entry: ConfigEntry,
        client: DccExClient,
        train: TrainConfig,
        function_number: int,
    ) -> None:
        """Initialize the function switch."""
        super().__init__(entry, client, train)
        self._function_number = function_number
        self._attr_unique_id = (
            f"train_{entry.entry_id}_{train.train_id}_function_{function_number}"
        )
        self._attr_name = self._function_name()
        self._unsub: Callable[[], None] | None = None

    @property
    def is_on(self) -> bool | None:
        """Return function state."""
        return self._client.get_function_state(
            self._train.address, self._function_number
        )

    def _function_name(self) -> str:
        """Return a display name for the function."""
        aliases = [
            name.replace("_", " ").title()
            for name, number in self._train.functions.items()
            if number == self._function_number
        ]
        if aliases:
            return f"F{self._function_number} {aliases[0]}"
        return f"F{self._function_number}"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the function on."""
        await self._client.async_set_function(self._train, self._function_number, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the function off."""
        await self._client.async_set_function(self._train, self._function_number, False)
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


class RailOpsAccessorySwitch(SwitchEntity):
    """Accessory decoder output switch."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:electric-switch"

    def __init__(
        self, entry: ConfigEntry, client: DccExClient, accessory: AccessoryConfig
    ) -> None:
        """Initialize the accessory switch."""
        self._entry = entry
        self._client = client
        self._accessory = accessory
        self._attr_unique_id = (
            f"accessory_{entry.entry_id}_{accessory.accessory_id}_output"
        )
        self._attr_name = accessory.name
        self._unsub: Callable[[], None] | None = None

    @property
    def device_info(self):
        """Return accessory device info."""
        return {
            "identifiers": {
                (DOMAIN, self._entry.entry_id, self._accessory.accessory_id)
            },
            "name": self._accessory.name,
            "manufacturer": "DCC-EX",
            "via_device": (DOMAIN, self._entry.entry_id),
        }

    @property
    def is_on(self) -> bool | None:
        """Return accessory state."""
        return self._client.get_accessory_state(self._accessory.accessory_id)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn accessory output on."""
        await self._client.async_set_accessory(self._accessory, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn accessory output off."""
        await self._client.async_set_accessory(self._accessory, False)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to accessory updates."""
        self._unsub = self._client.subscribe_accessory(
            self._accessory.accessory_id, self._accessory_updated
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from accessory updates."""
        if self._unsub:
            self._unsub()

    @callback
    def _accessory_updated(self, accessory_id: str, enabled: bool) -> None:
        """Refresh state after accessory command."""
        self.async_write_ha_state()
