"""Async client for JMRI's JSON WebSocket API."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from aiohttp import ClientError, ClientSession, WSMsgType

from .const import (
    ATTR_ADDRESS,
    ATTR_FORWARD,
    ATTR_PREFIX,
    ATTR_SPEED,
)

_LOGGER = logging.getLogger(__name__)

JMRI_IS_LONG_ADDRESS = "isLongAddress"
JMRI_ROSTER_ENTRY = "rosterEntry"


class JmriConnectionError(Exception):
    """Raised when JMRI cannot be reached."""


class JmriCommandError(Exception):
    """Raised when a JMRI command cannot be sent."""


@dataclass(slots=True)
class TrainConfig:
    """Stored train configuration."""

    train_id: str
    name: str
    address: int | None = None
    roster_entry: str | None = None
    is_long_address: bool | None = None
    prefix: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrainConfig":
        """Create config from persisted data."""
        return cls(
            train_id=data["train_id"],
            name=data.get("name") or data["train_id"],
            address=data.get("address"),
            roster_entry=data.get("roster_entry"),
            is_long_address=data.get("is_long_address"),
            prefix=data.get("prefix"),
        )

    def to_request_data(self) -> dict[str, Any]:
        """Return JMRI throttle request data."""
        data: dict[str, Any] = {"name": self.train_id}
        if self.address is not None:
            data[ATTR_ADDRESS] = self.address
        if self.roster_entry:
            data[JMRI_ROSTER_ENTRY] = self.roster_entry
        if self.is_long_address is not None:
            data[JMRI_IS_LONG_ADDRESS] = self.is_long_address
        if self.prefix:
            data[ATTR_PREFIX] = self.prefix
        return data


TrainUpdateCallback = Callable[[dict[str, Any]], None]
ConnectionCallback = Callable[[bool], None]


class JmriClient:
    """Small JMRI JSON WebSocket client."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        port: int,
        use_ssl: bool,
        verify_ssl: bool,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._host = host
        self._port = port
        self._use_ssl = use_ssl
        self._verify_ssl = verify_ssl
        self._ws = None
        self._reader_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._train_callbacks: dict[str, set[TrainUpdateCallback]] = {}
        self._connection_callbacks: set[ConnectionCallback] = set()
        self.connected = False

    @property
    def base_url(self) -> str:
        """Return the HTTP base URL."""
        scheme = "https" if self._use_ssl else "http"
        return f"{scheme}://{self._host}:{self._port}"

    @property
    def websocket_url(self) -> str:
        """Return the WebSocket JSON endpoint URL."""
        scheme = "wss" if self._use_ssl else "ws"
        return f"{scheme}://{self._host}:{self._port}/json"

    async def async_test_connection(self) -> None:
        """Check that the JMRI JSON servlet is reachable."""
        try:
            async with self._session.get(
                f"{self.base_url}/json/version",
                ssl=self._verify_ssl if self._use_ssl else None,
                timeout=10,
            ) as response:
                if response.status >= 400:
                    raise JmriConnectionError(f"JMRI returned HTTP {response.status}")
                await response.text()
        except (TimeoutError, ClientError) as err:
            raise JmriConnectionError(str(err)) from err

    def subscribe_train(
        self, train_id: str, callback: TrainUpdateCallback
    ) -> Callable[[], None]:
        """Subscribe to throttle updates for a train."""
        callbacks = self._train_callbacks.setdefault(train_id, set())
        callbacks.add(callback)

        def _unsubscribe() -> None:
            callbacks.discard(callback)
            if not callbacks:
                self._train_callbacks.pop(train_id, None)

        return _unsubscribe

    def subscribe_connection(self, callback: ConnectionCallback) -> Callable[[], None]:
        """Subscribe to connection state changes."""
        self._connection_callbacks.add(callback)

        def _unsubscribe() -> None:
            self._connection_callbacks.discard(callback)

        return _unsubscribe

    async def async_close(self) -> None:
        """Close the WebSocket connection."""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        if self._ws and not self._ws.closed:
            await self._ws.send_json({"type": "goodbye"})
            await self._ws.close()
        self._ws = None
        self._set_connected(False)

    async def async_connect(self) -> None:
        """Open the WebSocket connection."""
        await self._send({"type": "ping"})

    async def async_acquire_throttle(self, train: TrainConfig) -> None:
        """Acquire a JMRI throttle and request its current status."""
        await self._send_throttle(train, {"status": True})

    async def async_release_throttle(self, train: TrainConfig) -> None:
        """Release a train throttle."""
        await self._send_throttle(train, {"release": True})

    async def async_set_speed(self, train: TrainConfig, speed: float) -> None:
        """Set throttle speed from 0.0 to 1.0."""
        await self._send_throttle(train, {ATTR_SPEED: max(0.0, min(1.0, speed))})

    async def async_set_direction(self, train: TrainConfig, forward: bool) -> None:
        """Set train direction."""
        await self._send_throttle(train, {ATTR_FORWARD: forward})

    async def async_set_function(
        self, train: TrainConfig, function: int | str, enabled: bool
    ) -> None:
        """Set a DCC function output."""
        function_name = str(function).upper()
        if not function_name.startswith("F"):
            function_name = f"F{function_name}"
        await self._send_throttle(train, {function_name: enabled})

    async def async_stop(self, train: TrainConfig) -> None:
        """Set train speed to zero."""
        await self._send_throttle(train, {"idle": True})

    async def async_emergency_stop(self, train: TrainConfig) -> None:
        """Emergency stop a train."""
        await self._send_throttle(train, {"eStop": True})

    async def _send_throttle(self, train: TrainConfig, values: dict[str, Any]) -> None:
        """Send a throttle message."""
        data = train.to_request_data()
        data.update(values)
        await self._send({"type": "throttle", "method": "post", "data": data})

    async def _send(self, message: dict[str, Any]) -> None:
        """Send a JSON WebSocket message."""
        async with self._lock:
            await self._ensure_ws()
            try:
                await self._ws.send_json(message)
            except (RuntimeError, ClientError) as err:
                self._set_connected(False)
                raise JmriCommandError(str(err)) from err

    async def _ensure_ws(self) -> None:
        """Ensure the WebSocket is connected."""
        if self._ws and not self._ws.closed:
            return
        try:
            self._ws = await self._session.ws_connect(
                self.websocket_url,
                ssl=self._verify_ssl if self._use_ssl else None,
                heartbeat=30,
                timeout=10,
            )
        except (TimeoutError, ClientError) as err:
            self._set_connected(False)
            raise JmriConnectionError(str(err)) from err
        self._set_connected(True)
        self._reader_task = asyncio.create_task(self._reader())

    async def _reader(self) -> None:
        """Read WebSocket updates."""
        try:
            async for msg in self._ws:
                if msg.type == WSMsgType.TEXT:
                    self._handle_message(msg.json())
                elif msg.type in (WSMsgType.CLOSED, WSMsgType.ERROR):
                    break
        except asyncio.CancelledError:
            raise
        except ClientError as err:
            _LOGGER.debug("JMRI WebSocket reader stopped: %s", err)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("JMRI WebSocket reader stopped: %s", err)
        finally:
            self._set_connected(False)

    def _handle_message(self, message: Any) -> None:
        """Dispatch a JMRI message."""
        if isinstance(message, list):
            for item in message:
                self._handle_message(item)
            return
        if not isinstance(message, dict):
            return
        if message.get("type") == "pong":
            return
        if message.get("type") != "throttle":
            _LOGGER.debug("Unhandled JMRI message: %s", message)
            return
        data = message.get("data") or {}
        train_id = data.get("name") or data.get("throttle")
        if not train_id:
            return
        for callback in list(self._train_callbacks.get(train_id, ())):
            callback(data)

    def _set_connected(self, connected: bool) -> None:
        """Update connection state."""
        if self.connected == connected:
            return
        self.connected = connected
        for callback in list(self._connection_callbacks):
            callback(connected)
