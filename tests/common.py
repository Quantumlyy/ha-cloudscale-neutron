"""Entity ids and helpers shared by the tests."""

import asyncio
import time

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
