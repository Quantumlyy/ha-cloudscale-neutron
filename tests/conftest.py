"""Fixtures: a local broker with a fake Neutron module behind it."""

import json
from pathlib import Path
import socket
import subprocess
import urllib.parse
import urllib.request

import pytest

BROKER_DIR = Path(__file__).parent / "broker"
MID = "TEST01"
PIN = "4321"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def broker(socket_enabled):
    if not (BROKER_DIR / "node_modules").exists():
        pytest.skip("run `npm install` in tests/broker first")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    proc = subprocess.Popen(
        ["node", str(BROKER_DIR / "broker.js"), str(port), MID, PIN], stdout=subprocess.PIPE
    )
    assert proc.stdout.readline().strip() == b"ready"

    def control(**params):
        query = urllib.parse.urlencode(params)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/set?{query}") as resp:
            return json.load(resp)

    yield port, control
    proc.terminate()
    proc.wait()
