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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrainConfig":
        """Create config from persisted data."""
        return cls(
            train_id=data["train_id"],
            name=data.get("name") or data["train_id"],
            address=int(data["address"]),
            functions=normalize_function_map(data.get("functions")),
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


def normalize_function_map(functions: Any) -> dict[str, int]:
    """Normalize train function mappings."""
    normalized = dict(DEFAULT_FUNCTION_MAP)
    if not isinstance(functions, dict):
        return normalized
    for name, number in functions.items():
        key = str(name).strip().lower().replace(" ", "_").replace("-", "_")
        value = str(number).strip().upper().removeprefix("F")
        if not key or not value.isdigit():
            continue
        function_number = int(value)
        if 0 <= function_number <= 28:
            normalized[key] = function_number
    return normalized


TrainUpdateCallback = Callable[[dict[str, Any]], None]
ConnectionCallback = Callable[[bool], None]


class DccExClient:
    """Small persistent TCP client for DCC-EX."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize the client."""
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._train_callbacks: dict[int, set[TrainUpdateCallback]] = {}
        self._connection_callbacks: set[ConnectionCallback] = set()
        self._known_speed: dict[int, int] = {}
        self._known_forward: dict[int, bool] = {}
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

    def subscribe_connection(self, callback: ConnectionCallback) -> Callable[[], None]:
        """Subscribe to connection state changes."""
        self._connection_callbacks.add(callback)

        def _unsubscribe() -> None:
            self._connection_callbacks.discard(callback)

        return _unsubscribe

    async def async_close(self) -> None:
        """Close the TCP connection."""
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
        await self.async_send_raw(f"<{1 if on else 0} {track}>")

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
        await self.async_send_raw(
            f"<F {train.address} {function_number} {1 if enabled else 0}>"
        )

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
            _LOGGER.debug("Unhandled DCC-EX message: %s", message)
            return
        address = int(match.group("cab"))
        speed_byte = int(match.group("speed"))
        functions = int(match.group("functions"))
        forward = bool(speed_byte & 0x80)
        speed = speed_byte & 0x7F
        self._known_speed[address] = speed
        self._known_forward[address] = forward
        data = {
            "address": address,
            "speed": speed,
            "forward": forward,
            "functions": functions,
        }
        for callback in list(self._train_callbacks.get(address, ())):
            callback(data)

    def _set_connected(self, connected: bool) -> None:
        """Update connection state."""
        if self.connected == connected:
            return
        self.connected = connected
        for callback in list(self._connection_callbacks):
            callback(connected)
