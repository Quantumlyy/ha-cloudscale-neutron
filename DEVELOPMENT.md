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

## Only send what the vendor's own app sends

Left alone, the integration may send exactly two commands, both reads that the
Scale Monitor web app sends itself: `QASI1C` (poll) and `RSD` (scale settings,
once per connection). The buttons send `T`, `Z` and `TAC`, only on a press.

- Do not add commands that write settings or calibration to the module.
- Do not publish or subscribe outside `$CSL/<module id>/RX/SC` and
  `$CSL/<module id>/TX/SC`.
- A test (`test_settings_flags_and_commands_sent`) fails if anything else is
  sent.

## Layout

- `client.py`: paho-mqtt client (WebSocket transport), polling timer, latest
  reading, smoothing. paho callbacks run in its own thread and hand over to the
  event loop with `call_soon_threadsafe`.
- `parser.py`: parses the `QASI1C` reply line and the `RSD` settings reply.
- `diagnostics.py`: diagnostics download, with account values redacted.
- `smoothing.py`: time-windowed mean / median / exponential filters.
- `config_flow.py`: setup form (logs in before saving) and options form.
- `sensor.py`, `binary_sensor.py`, `button.py`, `entity.py`: entities.
- `tests/broker/`: Node broker (aedes + ws) with a fake module behind it.
- `wiki/`: source of the GitHub wiki. The "Publish wiki" workflow copies it to
  the wiki on every push to `main`; edit the pages here, not in the web UI.
- `translations/`: `en.json` is the source; `tests/test_translations.py` checks
  that every other language covers the same keys.

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
- The Overload and Underload sensors expect status `+` and `-`. The protocol
  manual lists those for a sibling command; only `S` and `D` have been seen.
- Of the `RSD` keys, only unit (`1U`), capacity (`1M1`..`1M3`) and division
  (`1D1`..`1D3`) are interpreted. The meaning of the others is not confirmed,
  so they are only passed through to the diagnostics download.

## Conventions

- Bump `version` in `manifest.json` for every release; HACS picks up GitHub
  releases.
- This is the vendor's internal channel, not a documented API. Keep polling
  modest by default and do not add features that touch other modules' topics.
