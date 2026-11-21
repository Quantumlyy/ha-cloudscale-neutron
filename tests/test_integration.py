"""End-to-end tests against the local broker and fake module."""

import asyncio
import time
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cloudscale_neutron.const import DOMAIN

from .conftest import MID, PIN

NET = "sensor.neutron_test01_net_weight"
GROSS = "sensor.neutron_test01_gross_weight"
TARE = "sensor.neutron_test01_tare"
STABLE = "binary_sensor.neutron_test01_stable"


def _data(port, pin=PIN, interval=1):
    return {
        "module_id": MID,
        "pin": pin,
        "host": "127.0.0.1",
        "port": port,
        "path": "/sm",
        "tls": False,
        "scan_interval": interval,
    }


async def _wait_for(hass, predicate, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        await hass.async_block_till_done()
        if predicate():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("condition not reached; states: %s" % [
        (s.entity_id, s.state) for s in hass.states.async_all()
    ])


def _state(hass, entity_id):
    state = hass.states.get(entity_id)
    return state.state if state else None


async def test_flow_success(hass: HomeAssistant, broker) -> None:
    port, _ = broker
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with (
        patch("custom_components.cloudscale_neutron.async_setup_entry", return_value=True),
        patch("custom_components.cloudscale_neutron.async_unload_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _data(port))
        await hass.config_entries.async_remove(result["result"].entry_id)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Neutron TEST01"
    assert result["data"]["pin"] == PIN


async def test_flow_wrong_pin(hass: HomeAssistant, broker) -> None:
    port, _ = broker
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], _data(port, pin="0000"))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_wrong_path_or_port(hass: HomeAssistant, broker) -> None:
    port, _ = broker
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    bad_path = {**_data(port), "path": "/nope"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], bad_path)
    assert result["errors"] == {"base": "cannot_connect"}
    bad_port = {**_data(port), "port": 1}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], bad_port)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_readings_buttons_and_availability(hass: HomeAssistant, broker) -> None:
    port, control = broker
    await hass.async_add_executor_job(lambda: control(gross=1.5))
    entry = MockConfigEntry(domain=DOMAIN, data=_data(port), unique_id=MID)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    await _wait_for(hass, lambda: _state(hass, NET) == "1.5")
    net = hass.states.get(NET)
    assert net.attributes["unit_of_measurement"] == "kg"
    assert net.attributes["device_class"] == "weight"
    assert _state(hass, GROSS) == "1.5"
    assert _state(hass, TARE) == "0.0"
    assert _state(hass, STABLE) == "on"

    # weight changes and is moving
    await hass.async_add_executor_job(lambda: control(gross=12.346, status="D"))
    await _wait_for(hass, lambda: _state(hass, NET) == "12.346")
    assert _state(hass, STABLE) == "off"

    # tare
    await hass.services.async_call("button", "press", {"entity_id": "button.neutron_test01_tare"}, blocking=True)
    await _wait_for(hass, lambda: _state(hass, TARE) == "12.346")
    assert _state(hass, NET) == "0.0"
    assert _state(hass, GROSS) == "12.346"

    # clear tare
    await hass.services.async_call("button", "press", {"entity_id": "button.neutron_test01_clear_tare"}, blocking=True)
    await _wait_for(hass, lambda: _state(hass, TARE) == "0.0")
    assert _state(hass, NET) == "12.346"

    # zero
    await hass.services.async_call("button", "press", {"entity_id": "button.neutron_test01_zero"}, blocking=True)
    await _wait_for(hass, lambda: _state(hass, GROSS) == "0.0")

    # module stops answering -> unavailable, then recovers
    await hass.async_add_executor_job(lambda: control(mute=1))
    await _wait_for(hass, lambda: _state(hass, NET) == "unavailable", timeout=25)
    assert _state(hass, STABLE) == "unavailable"
    await hass.async_add_executor_job(lambda: control(mute=0, gross=3.2, status="S"))
    await _wait_for(hass, lambda: _state(hass, NET) == "3.2")

    # options change reloads with the new interval
    polls_before = (await hass.async_add_executor_job(control))["polls"]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"scan_interval": 30, "smoothing": "none", "smoothing_window": 30, "stable_only": True},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["scan_interval"] == 30.0
    await _wait_for(hass, lambda: _state(hass, NET) == "3.2")
    await asyncio.sleep(3)
    polls_after = (await hass.async_add_executor_job(control))["polls"]
    assert polls_after - polls_before <= 2  # one poll on connect, not one per second

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_broker_down_then_up_is_quiet(hass: HomeAssistant, socket_enabled) -> None:
    """Setup succeeds with no broker; entities stay unavailable."""
    entry = MockConfigEntry(domain=DOMAIN, data=_data(1), unique_id=MID)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _state(hass, NET) == "unavailable"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


NET_SMOOTHED = "sensor.neutron_test01_net_weight_smoothed"
GROSS_SMOOTHED = "sensor.neutron_test01_gross_weight_smoothed"


async def test_precision_and_decimal_interval(hass: HomeAssistant, broker) -> None:
    from homeassistant.helpers import entity_registry as er

    port, control = broker
    await hass.async_add_executor_job(lambda: control(gross=2.0))
    entry = MockConfigEntry(domain=DOMAIN, data=_data(port, interval=0.5), unique_id=MID)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await _wait_for(hass, lambda: _state(hass, NET) == "2.0")

    registry = er.async_get(hass)
    precision = lambda entity_id: registry.async_get(entity_id).options["sensor"]["suggested_display_precision"]
    assert precision(NET) == 3  # the scale prints 0.000
    assert hass.states.get(NET_SMOOTHED) is None  # smoothing is off by default

    # switch on the sensors that are disabled by default, then reload
    hidden = {
        "sensor.neutron_test01_high_resolution_weight": 5,
        "sensor.neutron_test01_load_cell_signal": 4,
        "sensor.neutron_test01_adc_counts": 0,
    }
    for entity_id in hidden:
        assert registry.async_get(entity_id).disabled
        registry.async_update_entity(entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await _wait_for(hass, lambda: _state(hass, "sensor.neutron_test01_load_cell_signal") == "0.1234")
    assert _state(hass, "sensor.neutron_test01_adc_counts") == "1234567"
    assert _state(hass, "sensor.neutron_test01_high_resolution_weight") == "2.0"
    for entity_id, decimals in hidden.items():
        assert precision(entity_id) == decimals

    # 0.5 s interval: roughly two polls a second
    before = (await hass.async_add_executor_job(control))["polls"]
    await asyncio.sleep(3)
    after = (await hass.async_add_executor_job(control))["polls"]
    assert 4 <= after - before <= 8

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_smoothing(hass: HomeAssistant, broker) -> None:
    from homeassistant.helpers import entity_registry as er

    port, control = broker
    await hass.async_add_executor_job(lambda: control(gross=10.0))
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_data(port, interval=0.5),
        options={"scan_interval": 0.5, "smoothing": "mean", "smoothing_window": 60, "stable_only": True},
        unique_id=MID,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await _wait_for(hass, lambda: _state(hass, NET_SMOOTHED) == "10.0")
    registry = er.async_get(hass)
    assert registry.async_get(NET_SMOOTHED).options["sensor"]["suggested_display_precision"] == 4
    assert registry.async_get("sensor.neutron_test01_adc_counts_smoothed").disabled

    # a moving reading is left out of the average, the live sensor still follows it
    await hass.async_add_executor_job(lambda: control(gross=50.0, status="D"))
    await _wait_for(hass, lambda: _state(hass, NET) == "50.0")
    await asyncio.sleep(1.5)
    await hass.async_block_till_done()
    assert _state(hass, NET_SMOOTHED) == "10.0"

    # stable at a new weight: the average moves towards it but lags behind
    await hass.async_add_executor_job(lambda: control(gross=20.0, status="S"))
    await _wait_for(hass, lambda: _state(hass, NET) == "20.0")
    await _wait_for(hass, lambda: 10.0 < float(_state(hass, NET_SMOOTHED)) < 20.0)
    assert 10.0 < float(_state(hass, GROSS_SMOOTHED)) < 20.0

    # switching smoothing off removes the smoothed sensors
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"scan_interval": 0.5, "smoothing": "none", "smoothing_window": 60, "stable_only": True},
    )
    await _wait_for(hass, lambda: _state(hass, NET) == "20.0")
    assert hass.states.get(NET_SMOOTHED) is None
    assert registry.async_get(NET_SMOOTHED) is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
