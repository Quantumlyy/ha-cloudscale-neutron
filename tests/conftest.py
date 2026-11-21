"""Fixtures: a local broker with a fake Neutron module behind it."""

from __future__ import annotations

import datetime
import ipaddress
import json
from pathlib import Path
import socket
import ssl
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


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Broker:
    """The Node test broker as a subprocess that can be stopped and restarted."""

    def __init__(self, cert: Path | None = None, key: Path | None = None) -> None:
        self.port = _free_port()
        self._cert, self._key = cert, key
        self._proc: subprocess.Popen | None = None

    def start(self) -> None:
        args = ["node", str(BROKER_DIR / "broker.js"), str(self.port), MID, PIN]
        if self._cert:
            args += [str(self._cert), str(self._key)]
        self._proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        assert self._proc.stdout.readline().strip() == b"ready"

    def stop(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait()
            self._proc = None

    def _get(self, path: str, params: dict) -> dict:
        scheme = "https" if self._cert else "http"
        context = ssl._create_unverified_context() if self._cert else None
        url = f"{scheme}://127.0.0.1:{self.port}{path}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, context=context) as resp:
            return json.load(resp)

    def control(self, **params) -> dict:
        """Change the fake module's state and return it."""
        return self._get("/set", params)

    def inject(self, payload: str) -> dict:
        """Publish a raw line on the module's reply topic."""
        return self._get("/inject", {"payload": payload})

    def __iter__(self):
        # Lets tests write ``port, control = broker``.
        return iter((self.port, self.control))


def _require_broker() -> None:
    if not (BROKER_DIR / "node_modules").exists():
        pytest.skip("run `npm install` in tests/broker first")


@pytest.fixture
def broker(socket_enabled):
    _require_broker()
    server = Broker()
    server.start()
    yield server
    server.stop()


@pytest.fixture(scope="session")
def tls_certificate(tmp_path_factory) -> tuple[Path, Path]:
    """A self-signed certificate for 127.0.0.1, made fresh for the test run."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test broker")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    folder = tmp_path_factory.mktemp("tls")
    cert_file, key_file = folder / "cert.pem", folder / "key.pem"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_file, key_file


@pytest.fixture
def tls_broker(socket_enabled, tls_certificate):
    _require_broker()
    server = Broker(*tls_certificate)
    server.start()
    yield server
    server.stop()
