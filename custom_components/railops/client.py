"""Async client for DCC-EX native commands."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)

DEFAULT_READ_LIMIT = 65536
HEARTBEAT_INTERVAL = 10
DEFAULT_FUNCTION_MAP: dict[str, int] = {
    "headlight": 0,
    "bell": 1,
    "horn": 2,
    "whistle": 2,
    "short_horn": 3,
    "short_whistle": 3,
    "dynamic_brake": 4,
    "ditch_lights": 5,
    "mars_light": 6,
    "dim_headlight": 7,
    "mute": 8,
}
DEFAULT_FUNCTION_CONTROL = "switch"
FUNCTION_CONTROL_TYPES = {"switch", "button"}
DEFAULT_FUNCTION_PULSE_DURATION = 0.35
DEFAULT_RPM_MIN = 0
DEFAULT_RPM_MAX = 7
DEFAULT_RPM_INCREASE_FUNCTION = 5
DEFAULT_RPM_DECREASE_FUNCTION = 6
LOCO_BROADCAST = re.compile(
    r"^<l\s+(?P<cab>\d+)\s+\d+\s+(?P<speed>\d+)\s+(?P<functions>\d+)>$"
)


class DccExConnectionError(Exception):
    """Raised when DCC-EX cannot be reached."""


class DccExCommandError(Exception):
    """Raised when a DCC-EX command cannot be sent."""


@dataclass(slots=True)
class TrainConfig:
    """Stored train configuration."""

    train_id: str
    name: str
    address: int
    functions: dict[str, int]
    function_controls: dict[int, str]
    function_pulse_durations: dict[int, float]
    disabled_functions: set[int]
    rpm_enabled: bool
    rpm_min: int
    rpm_max: int
    rpm_increase_function: int
    rpm_decrease_function: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrainConfig":
        """Create config from persisted data."""
        rpm_min = int(data.get("rpm_min", DEFAULT_RPM_MIN))
        rpm_max = max(rpm_min + 1, int(data.get("rpm_max", DEFAULT_RPM_MAX)))
        return cls(
            train_id=data["train_id"],
            name=data.get("name") or data["train_id"],
            address=int(data["address"]),
            functions=normalize_function_map(data.get("functions")),
            function_controls=normalize_function_controls(
                data.get("function_controls")
            ),
            function_pulse_durations=normalize_function_pulse_durations(
                data.get("function_pulse_durations")
            ),
            disabled_functions=normalize_disabled_functions(
                data.get("disabled_functions")
            ),
            rpm_enabled=bool(data.get("rpm_enabled", True)),
            rpm_min=rpm_min,
            rpm_max=rpm_max,
            rpm_increase_function=normalize_function_number(
                data.get("rpm_increase_function"), DEFAULT_RPM_INCREASE_FUNCTION
            ),
            rpm_decrease_function=normalize_function_number(
                data.get("rpm_decrease_function"), DEFAULT_RPM_DECREASE_FUNCTION
            ),
        )

    def resolve_function(self, function: int | str) -> int:
        """Resolve a function number or friendly function name."""
        if isinstance(function, int):
            return function
        function_name = str(function).strip().lower()
        if function_name.startswith("f") and function_name[1:].isdigit():
            return int(function_name[1:])
        if function_name.isdigit():
            return int(function_name)
        key = function_name.replace(" ", "_").replace("-", "_")
        if key not in self.functions:
            raise ValueError(f"Unknown function mapping: {function}")
        return self.functions[key]

    def function_control_type(self, function_number: int) -> str:
        """Return switch or button for a function."""
        return self.function_controls.get(function_number, DEFAULT_FUNCTION_CONTROL)

    def function_enabled(self, function_number: int) -> bool:
        """Return whether a function should create Home Assistant entities."""
        return function_number not in self.disabled_functions

    def function_label(self, function_number: int) -> str:
        """Return the preferred Home Assistant label for a function."""
        aliases = [
            name.replace("_", " ").title()
            for name, number in self.functions.items()
            if number == function_number
        ]
        if aliases:
            return f"F{function_number} {aliases[0]}"
        return f"F{function_number}"

    def function_pulse_duration(self, function_number: int) -> float:
        """Return pulse duration for a function button."""
        return self.function_pulse_durations.get(
            function_number, DEFAULT_FUNCTION_PULSE_DURATION
        )


def normalize_function_map(functions: Any) -> dict[str, int]:
    """Normalize train function mappings."""
    normalized: dict[str, int] = {}
    provided = functions if isinstance(functions, dict) else {}
    for name, number in provided.items():
        key = str(name).strip().lower().replace(" ", "_").replace("-", "_")
        value = str(number).strip().upper().removeprefix("F")
        if not key or not value.isdigit():
            continue
        function_number = int(value)
        if 0 <= function_number <= 28:
            normalized[key] = function_number
    for name, number in DEFAULT_FUNCTION_MAP.items():
        normalized.setdefault(name, number)
    return normalized


def normalize_function_number(value: Any, default: int) -> int:
    """Normalize one F0-F28 function number."""
    number = str(value).strip().upper().removeprefix("F")
    if number.isdigit() and 0 <= int(number) <= 28:
        return int(number)
    return default


def normalize_disabled_functions(functions: Any) -> set[int]:
    """Normalize disabled F-key numbers."""
    if not isinstance(functions, list | tuple | set):
        return set()
    disabled: set[int] = set()
    for function in functions:
        value = str(function).strip().upper().removeprefix("F")
        if value.isdigit() and 0 <= int(value) <= 28:
            disabled.add(int(value))
    return disabled


def normalize_function_controls(function_controls: Any) -> dict[int, str]:
    """Normalize function control type mappings."""
    normalized: dict[int, str] = {}
    if not isinstance(function_controls, dict):
        return normalized
    for number, control_type in function_controls.items():
        value = str(number).strip().upper().removeprefix("F")
        if not value.isdigit():
            continue
        function_number = int(value)
        control_value = str(control_type).strip().lower()
        if 0 <= function_number <= 28 and control_value in FUNCTION_CONTROL_TYPES:
            normalized[function_number] = control_value
    return normalized


def normalize_function_pulse_durations(durations: Any) -> dict[int, float]:
    """Normalize function button pulse durations."""
    normalized: dict[int, float] = {}
    if not isinstance(durations, dict):
        return normalized
    for number, duration in durations.items():
        value = str(number).strip().upper().removeprefix("F")
        if not value.isdigit():
            continue
        function_number = int(value)
        try:
            duration_value = float(duration)
        except (TypeError, ValueError):
            continue
        if 0 <= function_number <= 28:
            normalized[function_number] = max(0.05, min(10.0, duration_value))
    return normalized


TrainUpdateCallback = Callable[[dict[str, Any]], None]
ConnectionCallback = Callable[[bool], None]
AccessoryUpdateCallback = Callable[[str, bool], None]


@dataclass(slots=True)
class AccessoryConfig:
    """Stored accessory configuration."""

    accessory_id: str
    name: str
    mode: str
    address: int
    subaddress: int | None = None
    output: int | None = None
    inverted: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AccessoryConfig":
        """Create config from persisted data."""
        return cls(
            accessory_id=data["accessory_id"],
            name=data.get("name") or data["accessory_id"],
            mode=data.get("mode", "dcc_accessory"),
            address=int(data["address"]),
            subaddress=data.get("subaddress"),
            output=data.get("output"),
            inverted=bool(data.get("inverted", False)),
        )


class DccExClient:
    """Small persistent TCP client for DCC-EX."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize the client."""
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._train_callbacks: dict[int, set[TrainUpdateCallback]] = {}
        self._accessory_callbacks: dict[str, set[AccessoryUpdateCallback]] = {}
        self._connection_callbacks: set[ConnectionCallback] = set()
        self._known_speed: dict[int, int] = {}
        self._known_forward: dict[int, bool] = {}
        self._known_functions: dict[int, dict[int, bool]] = {}
        self._configured_trains: dict[int, TrainConfig] = {}
        self._sound_levels: dict[int, int] = {}
        self._accessory_states: dict[str, bool] = {}
        self._acquired_trains: set[int] = set()
        self._power_on = False
        self.connected = False

    @property
    def address(self) -> str:
        """Return the host and port."""
        return f"{self._host}:{self._port}"

    async def async_test_connection(self) -> None:
        """Check that DCC-EX is reachable."""
        reader = writer = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), timeout=10
            )
            writer.write(b"<s>")
            await writer.drain()
            await asyncio.wait_for(reader.read(1), timeout=10)
        except (TimeoutError, OSError) as err:
            raise DccExConnectionError(str(err)) from err
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()

    def subscribe_train(
        self, address: int, callback: TrainUpdateCallback
    ) -> Callable[[], None]:
        """Subscribe to locomotive broadcast updates."""
        callbacks = self._train_callbacks.setdefault(address, set())
        callbacks.add(callback)

        def _unsubscribe() -> None:
            callbacks.discard(callback)
            if not callbacks:
                self._train_callbacks.pop(address, None)

        return _unsubscribe

    def subscribe_accessory(
        self, accessory_id: str, callback: AccessoryUpdateCallback
    ) -> Callable[[], None]:
        """Subscribe to accessory state updates."""
        callbacks = self._accessory_callbacks.setdefault(accessory_id, set())
        callbacks.add(callback)

        def _unsubscribe() -> None:
            callbacks.discard(callback)
            if not callbacks:
                self._accessory_callbacks.pop(accessory_id, None)

        return _unsubscribe

    def subscribe_connection(self, callback: ConnectionCallback) -> Callable[[], None]:
        """Subscribe to connection state changes."""
        self._connection_callbacks.add(callback)
        callback(self.connected)

        def _unsubscribe() -> None:
            self._connection_callbacks.discard(callback)

        return _unsubscribe

    async def async_start_polling(self, trains: list[TrainConfig]) -> None:
        """Start polling command station and configured trains."""
        self._configured_trains = {train.address: train for train in trains}
        if self._heartbeat_task and not self._heartbeat_task.done():
            return
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(trains))

    async def async_close(self) -> None:
        """Close the TCP connection."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None
        self._set_connected(False)

    async def async_connect(self) -> None:
        """Open the TCP connection."""
        await self._ensure_connected()
        await self.async_send_raw("<s>")

    async def async_set_power(self, on: bool, track: str = "MAIN") -> None:
        """Set DCC-EX track power."""
        self._power_on = on
        self._mark_power_state(on)
        await self.async_send_raw(f"<{1 if on else 0} {track}>")

    def get_power_state(self) -> bool:
        """Return the last commanded power state."""
        return self._power_on

    def get_speed(self, address: int) -> int:
        """Return the last known speed for an address."""
        return self._known_speed.get(address, 0)

    def get_forward(self, address: int) -> bool:
        """Return the last known direction for an address."""
        return self._known_forward.get(address, True)

    def get_function_state(self, address: int, function_number: int) -> bool:
        """Return the last known function state for an address."""
        return self._known_functions.get(address, {}).get(function_number, False)

    def get_accessory_state(self, accessory_id: str) -> bool:
        """Return the last known accessory state."""
        return self._accessory_states.get(accessory_id, False)

    def is_train_acquired(self, train: TrainConfig) -> bool:
        """Return whether RailOps has marked a train active."""
        return train.address in self._acquired_trains

    def get_sound_level(self, train: TrainConfig) -> int:
        """Return the current sound RPM notch."""
        return self._sound_levels.get(train.address, -1)

    async def async_query_train(self, train: TrainConfig) -> None:
        """Query current locomotive state."""
        await self.async_send_raw(f"<t {train.address}>")

    async def async_acquire_train(self, train: TrainConfig) -> None:
        """Acquire a train for active control in RailOps."""
        self._acquired_trains.add(train.address)
        self._sound_levels[train.address] = max(
            self._sound_levels.get(train.address, train.rpm_min), train.rpm_min
        )
        self._notify_train(train.address)
        await self.async_query_train(train)

    async def async_release_train(self, train: TrainConfig) -> None:
        """Release a train from active RailOps control."""
        self._acquired_trains.discard(train.address)
        self._sound_levels[train.address] = -1
        self._notify_train(train.address)
        await self.async_send_raw(f"<- {train.address}>")

    async def async_set_sound_level(self, train: TrainConfig, level: int) -> None:
        """Move the sound RPM notch with the configured increase/decrease functions."""
        target = max(-1, min(train.rpm_max, int(level)))
        current = self._sound_levels.get(train.address, -1)
        if current == -1 and target >= train.rpm_min:
            self._acquired_trains.add(train.address)
            await self.async_query_train(train)
        current = max(-1, min(train.rpm_max, current))
        if target > current:
            for _ in range(target - current):
                await self.async_pulse_function(
                    train,
                    train.rpm_increase_function,
                    train.function_pulse_duration(train.rpm_increase_function),
                )
        elif target < current:
            for _ in range(current - target):
                await self.async_pulse_function(
                    train,
                    train.rpm_decrease_function,
                    train.function_pulse_duration(train.rpm_decrease_function),
                )
        self._sound_levels[train.address] = target
        self._notify_train(train.address)

    async def async_set_speed(self, train: TrainConfig, speed: int) -> None:
        """Set throttle speed from 0 to 126."""
        speed = max(0, min(126, speed))
        forward = self._known_forward.get(train.address, True)
        await self._send_throttle(train.address, speed, forward)

    async def async_set_direction(self, train: TrainConfig, forward: bool) -> None:
        """Set train direction while leaving speed unchanged."""
        speed = self._known_speed.get(train.address, 0)
        await self._send_throttle(train.address, speed, forward)

    async def async_set_function(
        self, train: TrainConfig, function: int | str, enabled: bool
    ) -> None:
        """Set a DCC function output."""
        function_number = train.resolve_function(function)
        self._known_functions.setdefault(train.address, {})[function_number] = enabled
        await self.async_send_raw(
            f"<F {train.address} {function_number} {1 if enabled else 0}>"
        )
        if enabled and function_number == train.rpm_increase_function:
            self._adjust_sound_level(train, 1)
        elif enabled and function_number == train.rpm_decrease_function:
            self._adjust_sound_level(train, -1)

    async def async_set_accessory(
        self, accessory: AccessoryConfig, enabled: bool
    ) -> None:
        """Set accessory or function-decoder output state."""
        state = not enabled if accessory.inverted else enabled
        self._accessory_states[accessory.accessory_id] = enabled
        if accessory.mode == "function_decoder":
            await self.async_send_raw(
                f"<F {accessory.address} {accessory.output or 0} {1 if state else 0}>"
            )
        else:
            await self.async_send_raw(
                (
                    f"<a {accessory.address} {accessory.subaddress or 0} "
                    f"{1 if state else 0}>"
                )
            )
        self._notify_accessory(accessory.accessory_id, enabled)

    async def async_pulse_function(
        self, train: TrainConfig, function: int | str, duration: float
    ) -> None:
        """Momentarily turn a DCC function on, then off."""
        await self.async_set_function(train, function, True)
        await asyncio.sleep(max(0.05, duration))
        await self.async_set_function(train, function, False)

    async def async_stop(self, train: TrainConfig) -> None:
        """Set train speed to zero."""
        await self._send_throttle(
            train.address, 0, self._known_forward.get(train.address, True)
        )

    async def async_emergency_stop(self, train: TrainConfig | None = None) -> None:
        """Emergency stop a train or the whole command station."""
        if train:
            await self._send_throttle(
                train.address, 1, self._known_forward.get(train.address, True)
            )
        else:
            await self.async_send_raw("<!>")

    async def _send_throttle(self, address: int, speed: int, forward: bool) -> None:
        """Send DCC-EX throttle command and keep local state."""
        speed = max(0, min(126, speed))
        self._known_speed[address] = speed
        self._known_forward[address] = forward
        await self.async_send_raw(f"<t {address} {speed} {1 if forward else 0}>")

    async def async_send_raw(self, command: str) -> None:
        """Send a raw DCC-EX command."""
        if not command.startswith("<"):
            command = f"<{command}>"
        async with self._lock:
            await self._ensure_connected()
            try:
                self._writer.write(command.encode("ascii"))
                await self._writer.drain()
            except (RuntimeError, OSError) as err:
                self._set_connected(False)
                raise DccExCommandError(str(err)) from err

    async def _ensure_connected(self) -> None:
        """Ensure the TCP connection is open."""
        if self._writer and not self._writer.is_closing():
            return
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self._host, self._port, limit=DEFAULT_READ_LIMIT
                ),
                timeout=10,
            )
        except (TimeoutError, OSError) as err:
            self._set_connected(False)
            raise DccExConnectionError(str(err)) from err
        self._set_connected(True)
        self._reader_task = asyncio.create_task(self._read_loop())

    async def _heartbeat_loop(self, trains: list[TrainConfig]) -> None:
        """Poll command station status and configured locomotives."""
        while True:
            try:
                await self.async_send_raw("<s>")
                for train in trains:
                    if train.address in self._acquired_trains:
                        await self.async_query_train(train)
            except (DccExConnectionError, DccExCommandError, OSError) as err:
                _LOGGER.debug("DCC-EX heartbeat failed: %s", err)
                self._set_connected(False)
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    async def _read_loop(self) -> None:
        """Read and dispatch DCC-EX replies."""
        buffer = ""
        try:
            while self._reader:
                chunk = await self._reader.read(1024)
                if not chunk:
                    break
                buffer += chunk.decode("ascii", errors="ignore")
                while ">" in buffer:
                    message, buffer = buffer.split(">", 1)
                    self._handle_message(f"{message}>")
        except asyncio.CancelledError:
            raise
        except OSError as err:
            _LOGGER.debug("DCC-EX reader stopped: %s", err)
        finally:
            self._set_connected(False)

    def _handle_message(self, message: str) -> None:
        """Handle one DCC-EX response message."""
        match = LOCO_BROADCAST.match(message)
        if not match:
            if message.startswith("<p"):
                self._power_on = "0" not in message[:4]
                self._mark_power_state(self._power_on)
            elif message.startswith("<-"):
                _LOGGER.debug("DCC-EX released locomotive: %s", message)
                return
            _LOGGER.debug("Unhandled DCC-EX message: %s", message)
            return
        address = int(match.group("cab"))
        speed_byte = int(match.group("speed"))
        functions = int(match.group("functions"))
        forward = bool(speed_byte & 0x80)
        speed = speed_byte & 0x7F
        self._known_speed[address] = speed
        self._known_forward[address] = forward
        self._known_functions[address] = {
            function: bool(functions & (1 << function))
            for function in range(29)
        }
        data = {
            "address": address,
            "speed": speed,
            "forward": forward,
            "functions": functions,
            "acquired": address in self._acquired_trains,
            "sound_level": self._sound_levels.get(address, -1),
        }
        for callback in list(self._train_callbacks.get(address, ())):
            callback(data)

    def _adjust_sound_level(self, train: TrainConfig, delta: int) -> None:
        """Adjust tracked sound RPM after a mapped function press."""
        if not train.rpm_enabled:
            return
        current = self._sound_levels.get(train.address, -1)
        if delta > 0 and current == -1:
            self._acquired_trains.add(train.address)
            self._sound_levels[train.address] = train.rpm_min
        elif delta < 0 and current <= train.rpm_min:
            self._sound_levels[train.address] = -1
        else:
            self._sound_levels[train.address] = max(
                train.rpm_min, min(train.rpm_max, current + delta)
            )
        self._notify_train(train.address)

    def _mark_power_state(self, on: bool) -> None:
        """Update acquired and RPM state for configured trains after power changes."""
        if on:
            for address, train in self._configured_trains.items():
                self._acquired_trains.add(address)
                self._sound_levels[address] = max(
                    self._sound_levels.get(address, train.rpm_min), train.rpm_min
                )
                self._notify_train(address)
            return
        for address in self._configured_trains:
            self._acquired_trains.discard(address)
            self._sound_levels[address] = -1
            self._notify_train(address)

    def _notify_train(self, address: int) -> None:
        """Notify train listeners when local state changes."""
        data = {
            "address": address,
            "speed": self._known_speed.get(address, 0),
            "forward": self._known_forward.get(address, True),
            "functions": self._known_functions.get(address, {}),
            "acquired": address in self._acquired_trains,
            "sound_level": self._sound_levels.get(address, -1),
        }
        for callback in list(self._train_callbacks.get(address, ())):
            callback(data)

    def _notify_accessory(self, accessory_id: str, enabled: bool) -> None:
        """Notify accessory subscribers."""
        for callback in list(self._accessory_callbacks.get(accessory_id, ())):
            callback(accessory_id, enabled)

    def _set_connected(self, connected: bool) -> None:
        """Update connection state."""
        if self.connected == connected:
            return
        self.connected = connected
        for callback in list(self._connection_callbacks):
            callback(connected)
