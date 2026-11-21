"""MQTT-over-WebSocket client for a CloudScale Neutron module.

The Scale Monitor cloud is strictly request/reply: a command published to
``$CSL/<module id>/RX/SC`` is answered by the module on ``$CSL/<module id>/TX/SC``.
Nothing is sent unprompted, so this client polls on a fixed interval.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
import secrets
import ssl
import threading
import time
from typing import Any

import paho.mqtt.client as mqtt

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .const import POLL_COMMAND, SMOOTHED_KEYS
from .parser import Reading, parse_reading
from .smoothing import SMOOTHING_NONE, Smoother

_LOGGER = logging.getLogger(__name__)

KEEPALIVE = 60
CONNECT_TEST_TIMEOUT = 10
# CONNACK codes for bad credentials: MQTT 3.1.1 (4, 5) and their MQTT 5
# equivalents (134, 135), which paho 2.x reports.
AUTH_FAILURE_CODES = {4, 5, 134, 135}


def _rc_value(reason_code: Any) -> int:
    """Return a CONNACK result as an int for both paho 1.x and 2.x."""
    return int(getattr(reason_code, "value", reason_code))


def _build_client(path: str, tls: bool, module_id: str, pin: str) -> mqtt.Client:
    """Create a paho client. Blocking (loads CA certificates)."""
    client_id = f"ha-{module_id}-{secrets.token_hex(4)}"
    try:
        from paho.mqtt.enums import CallbackAPIVersion  # paho-mqtt >= 2.0

        client = mqtt.Client(
            CallbackAPIVersion.VERSION2, client_id=client_id, transport="websockets"
        )
    except ImportError:  # paho-mqtt 1.x
        client = mqtt.Client(client_id=client_id, transport="websockets")
    client.ws_set_options(path=path or "/")
    client.username_pw_set(f"CSL-{module_id}", pin)
    if tls:
        client.tls_set_context(ssl.create_default_context())
    client.reconnect_delay_set(min_delay=1, max_delay=120)
    return client


def test_connection(
    host: str, port: int, path: str, tls: bool, module_id: str, pin: str
) -> str | None:
    """Try to log in to the broker. Blocking.

    Return None on success, otherwise an error key for the config flow.
    """
    result: dict[str, Any] = {}
    done = threading.Event()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        result["rc"] = _rc_value(reason_code)
        done.set()

    try:
        client = _build_client(path, tls, module_id, pin)
        client.on_connect = on_connect
        client.connect(host, port, keepalive=KEEPALIVE)
    except Exception as err:  # noqa: BLE001 - network, TLS and handshake errors
        _LOGGER.debug("Connection test failed: %s", err)
        return "cannot_connect"

    client.loop_start()
    try:
        if not done.wait(CONNECT_TEST_TIMEOUT):
            return "cannot_connect"
    finally:
        client.disconnect()
        client.loop_stop()

    if result["rc"] == 0:
        return None
    if result["rc"] in AUTH_FAILURE_CODES:
        return "invalid_auth"
    return "cannot_connect"


class NeutronClient:
    """Keeps the connection, polls the scale and holds the latest reading."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        path: str,
        tls: bool,
        module_id: str,
        pin: str,
        scan_interval: float,
        smoothing: str = SMOOTHING_NONE,
        smoothing_window: float = 30.0,
        stable_only: bool = True,
    ) -> None:
        self.hass = hass
        self.module_id = module_id
        self.reading: Reading | None = None
        self.smoothing = smoothing
        self._stable_only = stable_only
        self._smoothers: dict[str, Smoother] = (
            {}
            if smoothing == SMOOTHING_NONE
            else {key: Smoother(smoothing, smoothing_window) for key in SMOOTHED_KEYS}
        )
        self._host = host
        self._port = port
        self._path = path
        self._tls = tls
        self._pin = pin
        self._scan_interval = scan_interval
        self._stale_after = max(3 * scan_interval, 15)
        self._topic_command = f"$CSL/{module_id}/RX/SC"
        self._topic_reply = f"$CSL/{module_id}/TX/SC"
        self._mqtt: mqtt.Client | None = None
        self._connected = False
        self._last_reply: float | None = None
        self._was_available = False
        self._listeners: set[Callable[[], None]] = set()
        self._unsub_timer: CALLBACK_TYPE | None = None

    # ----- lifecycle -------------------------------------------------------

    async def async_start(self) -> None:
        """Connect in the background and start polling."""
        await self.hass.async_add_executor_job(self._start)
        self._unsub_timer = async_track_time_interval(
            self.hass, self._async_tick, timedelta(seconds=self._scan_interval)
        )

    def _start(self) -> None:
        client = _build_client(self._path, self._tls, self.module_id, self._pin)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.connect_async(self._host, self._port, keepalive=KEEPALIVE)
        client.loop_start()
        self._mqtt = client

    async def async_stop(self) -> None:
        """Stop polling and disconnect."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None
        await self.hass.async_add_executor_job(self._stop)

    def _stop(self) -> None:
        if self._mqtt is None:
            return
        self._mqtt.disconnect()
        self._mqtt.loop_stop()
        self._mqtt = None

    # ----- state -----------------------------------------------------------

    @property
    def available(self) -> bool:
        """True while connected and the scale has answered recently."""
        return (
            self._connected
            and self._last_reply is not None
            and time.monotonic() - self._last_reply < self._stale_after
        )

    def smoothed(self, key: str) -> float | None:
        """Return the smoothed value for ``key``, or None if there is none yet."""
        if (smoother := self._smoothers.get(key)) is None:
            return None
        return smoother.value

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> CALLBACK_TYPE:
        """Register a callback for new readings and availability changes."""
        self._listeners.add(update)

        @callback
        def remove() -> None:
            self._listeners.discard(update)

        return remove

    @callback
    def _async_notify(self) -> None:
        self._was_available = self.available
        for update in list(self._listeners):
            update()

    # ----- commands --------------------------------------------------------

    @callback
    def async_send(self, command: str, qos: int = 1) -> bool:
        """Publish a command to the scale. Return False when not connected."""
        if self._mqtt is None or not self._connected:
            return False
        self._mqtt.publish(self._topic_command, command, qos=qos)
        return True

    @callback
    def _async_tick(self, now: datetime | None = None) -> None:
        self.async_send(POLL_COMMAND, qos=0)
        if self.available != self._was_available:
            self._async_notify()

    # ----- paho callbacks (run in paho's network thread) -------------------

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        code = _rc_value(reason_code)
        if code != 0:
            _LOGGER.warning(
                "Broker refused the connection for module %s (code %s)%s",
                self.module_id,
                code,
                ": check the module ID and PIN" if code in AUTH_FAILURE_CODES else "",
            )
            return
        client.subscribe(self._topic_reply, qos=0)
        self.hass.loop.call_soon_threadsafe(self._async_set_connected, True)

    def _on_disconnect(self, client, userdata, *args):
        self.hass.loop.call_soon_threadsafe(self._async_set_connected, False)

    def _on_message(self, client, userdata, message):
        payload = message.payload.decode("utf-8", errors="replace")
        self.hass.loop.call_soon_threadsafe(self._async_handle_payload, payload)

    # ----- handlers (run in the event loop) --------------------------------

    @callback
    def _async_set_connected(self, connected: bool) -> None:
        if connected == self._connected:
            return
        self._connected = connected
        _LOGGER.debug(
            "Module %s %s", self.module_id, "connected" if connected else "disconnected"
        )
        if connected:
            self.async_send(POLL_COMMAND, qos=0)
        self._async_notify()

    @callback
    def _async_handle_payload(self, payload: str) -> None:
        reading = parse_reading(payload)
        if reading is None:
            return  # reply to some other command (tare, zero, another client)
        changed = reading != self.reading
        self.reading = reading
        now = time.monotonic()
        self._last_reply = now
        if self._smoothers and (reading.stable or not self._stable_only):
            for key, smoother in self._smoothers.items():
                if (value := getattr(reading, key)) is not None:
                    smoother.add(float(value), now)
            changed = True
        if changed or not self._was_available:
            self._async_notify()
