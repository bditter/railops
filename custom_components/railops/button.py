"""Button entities for RailOps."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import DccExClient, TrainConfig
from .const import DATA_CLIENT, DOMAIN, OPT_TRAINS
from .entity import RailOpsControllerEntity, RailOpsTrainEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RailOps button entities."""
    client: DccExClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    entities: list[ButtonEntity] = [
        RailOpsControllerEmergencyStopButton(entry, client)
    ]
    for train_data in entry.options.get(OPT_TRAINS, []):
        train = TrainConfig.from_dict(train_data)
        entities.extend(
            [
                RailOpsTrainAcquireButton(entry, client, train),
                RailOpsTrainReleaseButton(entry, client, train),
                RailOpsTrainStopButton(entry, client, train),
                RailOpsTrainEmergencyStopButton(entry, client, train),
            ]
        )
        entities.extend(
            RailOpsFunctionButton(entry, client, train, function_number)
            for function_number in range(29)
            if train.function_enabled(function_number)
            and train.function_control_type(function_number) == "button"
        )
    async_add_entities(entities)


class RailOpsControllerEmergencyStopButton(RailOpsControllerEntity, ButtonEntity):
    """Global DCC-EX emergency stop button."""

    _attr_icon = "mdi:alert-octagon"

    def __init__(self, entry: ConfigEntry, client: DccExClient) -> None:
        """Initialize the global emergency stop button."""
        super().__init__(entry, client)
        self._attr_unique_id = f"controller_{entry.entry_id}_emergency_stop"
        self._attr_name = "Emergency Stop"

    async def async_press(self) -> None:
        """Send global emergency stop."""
        await self._client.async_emergency_stop()


class RailOpsTrainStopButton(RailOpsTrainEntity, ButtonEntity):
    """Train stop button."""

    _attr_icon = "mdi:stop"

    def __init__(
        self, entry: ConfigEntry, client: DccExClient, train: TrainConfig
    ) -> None:
        """Initialize the stop button."""
        super().__init__(entry, client, train)
        self._attr_unique_id = f"train_{entry.entry_id}_{train.train_id}_stop"
        self._attr_name = "Stop"

    async def async_press(self) -> None:
        """Stop the train."""
        await self._client.async_stop(self._train)


class RailOpsTrainAcquireButton(RailOpsTrainEntity, ButtonEntity):
    """Train acquire button."""

    _attr_icon = "mdi:train"

    def __init__(
        self, entry: ConfigEntry, client: DccExClient, train: TrainConfig
    ) -> None:
        """Initialize the acquire button."""
        super().__init__(entry, client, train)
        self._attr_unique_id = f"train_{entry.entry_id}_{train.train_id}_acquire"
        self._attr_name = "Acquire"

    async def async_press(self) -> None:
        """Acquire the train for RailOps control."""
        await self._client.async_acquire_train(self._train)


class RailOpsTrainReleaseButton(RailOpsTrainEntity, ButtonEntity):
    """Train release button."""

    _attr_icon = "mdi:train"

    def __init__(
        self, entry: ConfigEntry, client: DccExClient, train: TrainConfig
    ) -> None:
        """Initialize the release button."""
        super().__init__(entry, client, train)
        self._attr_unique_id = f"train_{entry.entry_id}_{train.train_id}_release"
        self._attr_name = "Release"

    async def async_press(self) -> None:
        """Release the train from active RailOps control."""
        await self._client.async_release_train(self._train)


class RailOpsTrainEmergencyStopButton(RailOpsTrainEntity, ButtonEntity):
    """Train emergency stop button."""

    _attr_icon = "mdi:alert-octagon"

    def __init__(
        self, entry: ConfigEntry, client: DccExClient, train: TrainConfig
    ) -> None:
        """Initialize the emergency stop button."""
        super().__init__(entry, client, train)
        self._attr_unique_id = f"train_{entry.entry_id}_{train.train_id}_emergency_stop"
        self._attr_name = "Emergency Stop"

    async def async_press(self) -> None:
        """Emergency stop the train."""
        await self._client.async_emergency_stop(self._train)


class RailOpsFunctionButton(RailOpsTrainEntity, ButtonEntity):
    """Momentary DCC function button."""

    _attr_icon = "mdi:gesture-tap-button"

    def __init__(
        self,
        entry: ConfigEntry,
        client: DccExClient,
        train: TrainConfig,
        function_number: int,
    ) -> None:
        """Initialize the function button."""
        super().__init__(entry, client, train)
        self._function_number = function_number
        self._attr_unique_id = (
            f"train_{entry.entry_id}_{train.train_id}_function_{function_number}_button"
        )
        self._attr_name = train.function_label(function_number)

    async def async_press(self) -> None:
        """Pulse the function."""
        await self._client.async_pulse_function(
            self._train,
            self._function_number,
            self._train.function_pulse_duration(self._function_number),
        )
