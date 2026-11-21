# Development notes

Home Assistant custom integration (`custom_components/cloudscale_neutron`) for
the CloudScale Neutron scale. It talks to the vendor's Scale Monitor cloud
broker: MQTT over WebSocket, strictly request/reply. See README.md for the
protocol summary and the options.

## Never commit account values

Keep these out of code, tests, docs, commit messages and issues:

- real module IDs (MID) and PINs
- account-specific hostnames (broker, API endpoint, web app)
- readings or captures taken from a real scale (HAR files, raw frames)

Tests use the fake module `TEST01` / PIN `4321` and made-up readings. The
broker host has no default on purpose; the user types it in the setup form.

## Layout

- `client.py`: paho-mqtt client (WebSocket transport), polling timer, latest
  reading, smoothing. paho callbacks run in its own thread and hand over to the
  event loop with `call_soon_threadsafe`.
- `parser.py`: parses the `QASI1C` reply line.
- `smoothing.py`: time-windowed mean / median / exponential filters.
- `config_flow.py`: setup form (logs in before saving) and options form.
- `sensor.py`, `binary_sensor.py`, `button.py`, `entity.py`: entities.
- `tests/broker/`: Node broker (aedes + ws) with a fake module behind it.

## Tests

    pip install -r requirements_test.txt
    npm install --prefix tests/broker
    pytest

Developed against Home Assistant 2026.2 on Python 3.13 and Node 22.

## Not yet verified against a real module

- The Tare, Zero and Clear tare commands (`T`, `Z`, `TAC`) come from the
  vendor's protocol manual; they were not seen in captured traffic.
- The order of gross / net / tare in the reply follows the manual; the scale
  was empty in the only capture, so all three read zero.
- TLS and login against the real broker are not covered by the tests, which
  use a local broker without TLS.
- The GitHub Actions workflow has not run yet.

## Conventions

- Bump `version` in `manifest.json` for every release; HACS picks up GitHub
  releases.
- This is the vendor's internal channel, not a documented API. Keep polling
  modest by default and do not add features that touch other modules' topics.
