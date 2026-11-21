"""Unit tests for the client's logic, without a broker."""

from unittest.mock import MagicMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.cloudscale_neutron import client as client_module
from custom_components.cloudscale_neutron.binary_sensor import (
    BINARY_SENSORS,
    NeutronBinarySensor,
)
from custom_components.cloudscale_neutron.button import NeutronCommandButton
from custom_components.cloudscale_neutron.client import NeutronClient
from custom_components.cloudscale_neutron.sensor import (
    SENSORS,
    SMOOTHED_SENSORS,
    NeutronSensor,
    _load_percent,
)

from .conftest import MID, PIN


def _line(status="S", gross=1.0, tare=0.0, unit="kg"):
    return (
        f"QASI1C,1,1,1,{status},{gross:10.3f},{gross - tare:10.3f},{tare:10.3f},"
        f"{gross:10.5f},   1234567,    0.1234,{unit}"
    )


def _client(hass, **kwargs) -> NeutronClient:
    """A client that is never started, so nothing touches the network."""
    options = {"scan_interval": 5.0, **kwargs}
    return NeutronClient(
        hass, host="broker.invalid", port=443, path="/sm", tls=True,
        module_id=MID, pin=PIN, **options,
    )


def _connected(client: NeutronClient) -> MagicMock:
    """Pretend the broker connection is up; return the fake MQTT object."""
    client._mqtt = MagicMock()
    client._connected = True
    return client._mqtt


class _Clock:
    """A monotonic clock the test moves by hand."""

    def __init__(self, monkeypatch) -> None:
        self.now = 1000.0
        monkeypatch.setattr(client_module, "monotonic", lambda: self.now)

    def advance(self, seconds: float) -> None:
        self.now += seconds


async def test_nothing_is_sent_while_disconnected(hass: HomeAssistant) -> None:
    client = _client(hass)
    assert client.async_send("QASI1C") is False
    client._mqtt = MagicMock()  # connecting, but not connected yet
    assert client.async_send("QASI1C") is False
    client._async_tick()
    client._mqtt.publish.assert_not_called()
    assert client.available is False


async def test_commands_go_to_the_module_command_topic(hass: HomeAssistant) -> None:
    client = _client(hass)
    mqtt = _connected(client)
    assert client.async_send("T") is True
    mqtt.publish.assert_called_once_with(f"$CSL/{MID}/RX/SC", "T", qos=1)


async def test_listeners_hear_readings_until_removed(hass: HomeAssistant) -> None:
    client = _client(hass)
    _connected(client)
    calls = []
    remove = client.async_add_listener(lambda: calls.append(client.reading.net))
    client._async_handle_payload(_line(gross=1.0))
    client._async_handle_payload(_line(gross=1.0))  # identical: no second call
    client._async_handle_payload(_line(gross=2.0))
    assert calls == [1.0, 2.0]
    remove()
    client._async_handle_payload(_line(gross=3.0))
    assert calls == [1.0, 2.0]


async def test_availability_follows_recent_replies(hass: HomeAssistant, monkeypatch) -> None:
    clock = _Clock(monkeypatch)
    client = _client(hass, scan_interval=5.0)
    _connected(client)
    assert client.available is False  # connected, but the module has not answered
    client._async_handle_payload(_line())
    assert client.available is True
    clock.advance(14)
    assert client.available is True
    clock.advance(2)  # three missed 5-second polls
    assert client.available is False
    client._async_handle_payload(_line())
    assert client.available is True
    client._async_set_connected(False)
    assert client.available is False


async def test_stale_window_scales_with_long_intervals(hass: HomeAssistant, monkeypatch) -> None:
    clock = _Clock(monkeypatch)
    client = _client(hass, scan_interval=60.0)
    _connected(client)
    client._async_handle_payload(_line())
    clock.advance(170)
    assert client.available is True
    clock.advance(20)
    assert client.available is False


async def test_reply_time_is_measured_from_the_poll(hass: HomeAssistant, monkeypatch) -> None:
    clock = _Clock(monkeypatch)
    client = _client(hass)
    _connected(client)
    client._async_tick()
    clock.advance(0.25)
    client._async_handle_payload(_line())
    assert client.reply_time == pytest.approx(0.25)

    # a reading nobody here asked for does not change the measurement
    clock.advance(3)
    client._async_handle_payload(_line(gross=2.0))
    assert client.reply_time == pytest.approx(0.25)


async def test_reply_time_is_not_inflated_by_a_dropout(hass: HomeAssistant, monkeypatch) -> None:
    clock = _Clock(monkeypatch)
    client = _client(hass, scan_interval=5.0)
    _connected(client)
    client._async_tick()  # this poll is never answered
    clock.advance(5)
    client._async_tick()  # still waiting on the first one
    clock.advance(600)
    client._async_tick()  # the old poll is given up on; timing restarts here
    clock.advance(0.4)
    client._async_handle_payload(_line())
    assert client.reply_time == pytest.approx(0.4)


async def test_disconnect_forgets_the_pending_poll(hass: HomeAssistant, monkeypatch) -> None:
    clock = _Clock(monkeypatch)
    client = _client(hass)
    _connected(client)
    client._async_tick()
    client._async_set_connected(False)
    client._async_set_connected(False)  # repeated notice changes nothing
    clock.advance(30)
    client._async_handle_payload(_line())
    assert client.reply_time is None


async def test_connecting_polls_and_reads_settings_once(hass: HomeAssistant) -> None:
    client = _client(hass)
    client._mqtt = MagicMock()
    client._async_set_connected(True)
    client._async_set_connected(True)  # a repeated notice must not resend
    sent = [call.args[1] for call in client._mqtt.publish.call_args_list]
    assert sent == ["QASI1C", "RSD"]


@pytest.mark.parametrize(("stable_only", "expected"), [(True, 10.0), (False, 30.0)])
async def test_smoothing_can_skip_moving_readings(
    hass: HomeAssistant, monkeypatch, stable_only, expected
) -> None:
    clock = _Clock(monkeypatch)
    client = _client(hass, smoothing="mean", smoothing_window=60, stable_only=stable_only)
    _connected(client)
    client._async_handle_payload(_line("S", gross=10.0))
    clock.advance(1)
    client._async_handle_payload(_line("D", gross=50.0))
    assert client.smoothed("net") == pytest.approx(expected)
    assert client.smoothed("gross") == pytest.approx(expected)
    assert client.smoothed("adc") == pytest.approx(1234567)


async def test_smoothing_skips_values_the_scale_did_not_send(hass: HomeAssistant) -> None:
    client = _client(hass, smoothing="median", smoothing_window=60)
    _connected(client)
    client._async_handle_payload(_line(gross=4.0))
    client._async_handle_payload("QASI1C,1,1,1,S,,,,,,,kg")
    assert client.smoothed("net") == pytest.approx(4.0)


async def test_no_smoothed_values_when_smoothing_is_off(hass: HomeAssistant) -> None:
    client = _client(hass)
    _connected(client)
    client._async_handle_payload(_line())
    assert client.smoothed("net") is None
    assert client.smoothed("no such key") is None


async def test_settings_are_stored_and_announced_once(hass: HomeAssistant) -> None:
    client = _client(hass)
    _connected(client)
    calls = []
    client.async_add_listener(lambda: calls.append(1))
    client._async_handle_payload("RSD;1D1=0.005;1M1=30;1U=kg")
    client._async_handle_payload("RSD;1D1=0.005;1M1=30;1U=kg")
    assert client.settings.capacity == 30.0
    assert len(calls) == 1
    assert client.reading is None  # a settings reply is not a reading


async def test_load_needs_both_a_reading_and_a_capacity(hass: HomeAssistant) -> None:
    client = _client(hass)
    _connected(client)
    assert _load_percent(client) is None
    client._async_handle_payload(_line(gross=15.0))
    assert _load_percent(client) is None  # no settings yet
    client._async_handle_payload("RSD;1U=kg")  # settings without a capacity
    assert _load_percent(client) is None
    client._async_handle_payload("RSD;1M1=60;1U=kg")
    assert _load_percent(client) == 25.0


async def test_button_press_fails_loudly_when_disconnected(hass: HomeAssistant) -> None:
    client = _client(hass)
    button = NeutronCommandButton(client, "tare", "T")
    with pytest.raises(HomeAssistantError):
        await button.async_press()

    mqtt = _connected(client)
    await button.async_press()
    assert [call.args[1] for call in mqtt.publish.call_args_list] == ["T", "QASI1C"]


async def test_stop_without_start_is_harmless(hass: HomeAssistant) -> None:
    await _client(hass).async_stop()


async def test_entities_have_no_value_before_the_first_reading(hass: HomeAssistant) -> None:
    client = _client(hass, smoothing="mean")
    for description in (*SENSORS, *SMOOTHED_SENSORS):
        sensor = NeutronSensor(client, description)
        assert sensor.native_value is None
        assert sensor.available is False
    for description in BINARY_SENSORS:
        assert NeutronBinarySensor(client, description).is_on is None


async def test_weight_unit_falls_back_to_the_scale_settings(hass: HomeAssistant) -> None:
    client = _client(hass)
    net = NeutronSensor(client, SENSORS[0])
    assert net.native_unit_of_measurement is None and net.device_class is None
    assert net.suggested_display_precision is None
    client._async_handle_payload("RSD;1M1=30;1U=g")
    assert net.native_unit_of_measurement == "g" and net.device_class == "weight"
    client._async_handle_payload(_line(unit="kg"))  # a reading's unit wins
    assert net.native_unit_of_measurement == "kg"
    assert net.suggested_display_precision == 3
