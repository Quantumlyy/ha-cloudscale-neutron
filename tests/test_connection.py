"""Connection behaviour: TLS, dropouts, refusals and traffic from other clients."""

import asyncio
import logging
import ssl
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cloudscale_neutron import client as client_module
from custom_components.cloudscale_neutron.const import DOMAIN

from .common import GROSS, NET, STABLE, _data, _state, _wait_for
from .conftest import MID

CLIENT_LOGGER = "custom_components.cloudscale_neutron.client"


async def _submit(hass, data):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    return await hass.config_entries.flow.async_configure(result["flow_id"], data)


async def _setup(hass, data, **kwargs):
    entry = MockConfigEntry(domain=DOMAIN, data=data, unique_id=MID, **kwargs)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    return entry


async def _unload(hass, entry):
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


# ----- TLS ------------------------------------------------------------------


async def test_tls_refuses_untrusted_certificate(hass: HomeAssistant, tls_broker) -> None:
    """A broker whose certificate is not trusted must not be accepted."""
    result = await _submit(hass, {**_data(tls_broker.port), "tls": True})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_tls_connects_when_certificate_is_trusted(
    hass: HomeAssistant, tls_broker, tls_certificate
) -> None:
    cert_file, _ = tls_certificate
    real_context = ssl.create_default_context

    def trusting_context():
        return real_context(cafile=str(cert_file))

    await hass.async_add_executor_job(lambda: tls_broker.control(gross=4.2))
    with patch.object(client_module.ssl, "create_default_context", trusting_context):
        result = await _submit(hass, {**_data(tls_broker.port), "tls": True})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await _wait_for(hass, lambda: _state(hass, NET) == "4.2")
        await _unload(hass, result["result"])


async def test_plain_connection_to_tls_broker_fails(hass: HomeAssistant, tls_broker) -> None:
    result = await _submit(hass, {**_data(tls_broker.port), "tls": False})
    assert result["errors"] == {"base": "cannot_connect"}


# ----- refusals and timeouts -------------------------------------------------


async def test_flow_times_out_when_broker_never_answers(
    hass: HomeAssistant, broker, monkeypatch
) -> None:
    """The WebSocket opens but no MQTT reply ever comes."""
    monkeypatch.setattr(client_module, "CONNECT_TEST_TIMEOUT", 1)
    result = await _submit(hass, {**_data(broker.port), "path": "/silent"})
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_reports_other_refusals_as_cannot_connect(
    hass: HomeAssistant, broker
) -> None:
    """A refusal that is not about credentials is not blamed on the PIN."""
    result = await _submit(hass, _data(broker.port, pin="busy"))
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_rejects_duplicate_and_trims_input(hass: HomeAssistant, broker) -> None:
    padded = {**_data(broker.port), "module_id": f"  {MID} ", "host": " 127.0.0.1 "}
    with (
        patch("custom_components.cloudscale_neutron.async_setup_entry", return_value=True),
        patch("custom_components.cloudscale_neutron.async_unload_entry", return_value=True),
    ):
        result = await _submit(hass, padded)
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["module_id"] == MID
        assert result["data"]["host"] == "127.0.0.1"
        assert result["result"].unique_id == MID

        again = await _submit(hass, _data(broker.port))
        assert again["type"] is FlowResultType.ABORT
        assert again["reason"] == "already_configured"
        await hass.config_entries.async_remove(result["result"].entry_id)


async def test_wrong_pin_after_setup_logs_a_hint(hass: HomeAssistant, broker, caplog) -> None:
    """For example the PIN was changed on the module after setup."""
    caplog.set_level(logging.WARNING, logger=CLIENT_LOGGER)
    entry = await _setup(hass, _data(broker.port, pin="0000"))
    await _wait_for(hass, lambda: "check the module ID and PIN" in caplog.text)
    assert _state(hass, NET) == "unavailable"
    assert "0000" not in caplog.text  # the PIN itself is never logged
    await _unload(hass, entry)


# ----- dropouts -------------------------------------------------------------


async def test_reconnects_after_broker_restart(hass: HomeAssistant, broker) -> None:
    await hass.async_add_executor_job(lambda: broker.control(gross=2.5))
    entry = await _setup(hass, _data(broker.port, interval=0.5))
    await _wait_for(hass, lambda: _state(hass, NET) == "2.5")

    await hass.async_add_executor_job(broker.stop)
    await _wait_for(hass, lambda: _state(hass, NET) == "unavailable")
    assert _state(hass, STABLE) == "unavailable"

    # the broker comes back with a different weight on the scale
    await hass.async_add_executor_job(broker.start)
    await hass.async_add_executor_job(lambda: broker.control(gross=9.0))
    await _wait_for(hass, lambda: _state(hass, NET) == "9.0", timeout=30)

    # the settings were read again on the new connection
    sent = (await hass.async_add_executor_job(broker.control))["commands"]
    assert set(sent) == {"QASI1C", "RSD"}
    await _unload(hass, entry)


# ----- traffic that is not ours ---------------------------------------------


async def test_ignores_replies_meant_for_other_commands(
    hass: HomeAssistant, broker, caplog
) -> None:
    """The reply topic also carries answers to other clients' commands."""
    caplog.set_level(logging.WARNING)
    await hass.async_add_executor_job(lambda: broker.control(gross=3.0))
    entry = await _setup(hass, _data(broker.port, interval=60))
    await _wait_for(hass, lambda: _state(hass, NET) == "3.0")

    for junk in (
        "T S      1.000 kg",
        "Z A",
        "QASI1C,too,short",
        "QASI1 1 1 1 S 5.000 5.000 0.000 5.00000 1234567 0.1234 kg",
        "",
        "\x00\xff not text",
        "RSD",
    ):
        await hass.async_add_executor_job(broker.inject, junk)
    await asyncio.sleep(0.5)
    await hass.async_block_till_done()
    assert _state(hass, NET) == "3.0"
    assert not [r for r in caplog.records if r.name.startswith("custom_components")]
    await _unload(hass, entry)


async def test_uses_readings_triggered_by_other_clients(hass: HomeAssistant, broker) -> None:
    """With Scale Monitor open, readings arrive that we did not ask for."""
    entry = await _setup(hass, _data(broker.port, interval=60))
    await _wait_for(hass, lambda: _state(hass, NET) == "0.0")
    line = "QASI1C,1,1,1,D,     8.125,     7.125,     1.000,   8.12512,   1234567,    0.1234,kg"
    await hass.async_add_executor_job(broker.inject, line)
    await _wait_for(hass, lambda: _state(hass, NET) == "7.125")
    assert (_state(hass, GROSS), _state(hass, STABLE)) == ("8.125", "off")
    await _unload(hass, entry)


async def test_unknown_unit_is_shown_as_the_scale_sends_it(hass: HomeAssistant, broker) -> None:
    entry = await _setup(hass, _data(broker.port, interval=60))
    await _wait_for(hass, lambda: _state(hass, NET) == "0.0")
    line = "QASI1C,1,1,1,S,      1.20,      1.20,      0.00,   1.2000,   1234567,    0.1234,t"
    await hass.async_add_executor_job(broker.inject, line)
    await _wait_for(hass, lambda: _state(hass, NET) == "1.2")
    attributes = hass.states.get(NET).attributes
    assert attributes["unit_of_measurement"] == "t"
    assert "device_class" not in attributes  # not a weight unit Home Assistant knows
    await _unload(hass, entry)


async def test_unreadable_weights_become_unknown(hass: HomeAssistant, broker) -> None:
    """Out of range, the scale may send no numbers at all."""
    entry = await _setup(hass, _data(broker.port, interval=60))
    await _wait_for(hass, lambda: _state(hass, NET) == "0.0")
    await hass.async_add_executor_job(broker.inject, "QASI1C,1,1,1,+,,,,,,,kg")
    await _wait_for(hass, lambda: _state(hass, "binary_sensor.neutron_test01_overload") == "on")
    assert _state(hass, NET) == "unknown"
    assert _state(hass, "sensor.neutron_test01_load") == "unknown"
    assert _state(hass, "binary_sensor.neutron_test01_at_zero") == "unknown"
    await _unload(hass, entry)
