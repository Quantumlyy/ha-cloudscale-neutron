# CloudScale Neutron for Home Assistant

Reads a CloudScale Neutron scale through the Scale Monitor cloud broker
(MQTT over WebSocket) and exposes it in Home Assistant. Nothing changes on the
module, and Scale Monitor keeps working alongside it.

This uses the same channel the Scale Monitor web app uses. It is not a
documented vendor API, so it may change without notice.

Step-by-step setup instructions are in the
[wiki](https://github.com/Quantumlyy/ha-cloudscale-neutron/wiki).

## Install with HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Quantumlyy&repository=ha-cloudscale-neutron&category=integration)

Press the button, confirm adding the repository, download **CloudScale
Neutron**, and restart Home Assistant.

Without the button:

1. In HACS, open the menu at the top right and choose **Custom repositories**.
2. Add `https://github.com/Quantumlyy/ha-cloudscale-neutron` with type
   **Integration**.
3. Find **CloudScale Neutron** in HACS, download it, and restart Home Assistant.

## Install by hand

Copy `custom_components/cloudscale_neutron` into the `custom_components`
folder of your Home Assistant configuration directory and restart.

## Set up

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=cloudscale_neutron)

Press the button, or go to **Settings → Devices & services → Add
integration** and search for **CloudScale Neutron**. Then enter:

- **Module ID and PIN** from the module's label.
- **Broker host**: the host your Scale Monitor account uses for its MQTT
  WebSocket. Open Scale Monitor with the browser's developer tools on the
  Network tab, filter for WS, and copy the host of the `wss://` request.
- **Port, path and TLS**: leave at 443, `/sm` and on unless that request shows
  something else.

The form logs in to the broker before saving, so a wrong PIN or address is
reported straight away.

## Entities

| Entity | Notes |
|---|---|
| Net weight, Gross weight, Tare | Live values, shown with the decimals the scale prints |
| Stable | On while the scale reports a stable weight |
| Tare, Zero, Clear tare | Buttons that send `T`, `Z` and `TAC` to the scale |
| Net weight smoothed, Gross weight smoothed | Only when smoothing is on |
| High-resolution weight, ADC counts, Load cell signal | Disabled by default |
| ADC counts smoothed, Load cell signal smoothed | Only when smoothing is on; disabled by default |

Entities turn unavailable when the broker connection drops or the module
stops answering (after three missed polls, 15 seconds minimum).

## Options

Open the integration and press **Configure**.

| Option | Default | What it does |
|---|---|---|
| Poll interval | 5 s | How often the scale is asked for a reading. 0.2 s to 1 hour, in steps of 0.1 s |
| Smoothing | Off | Adds the smoothed sensors. Average, Median or Exponential |
| Smoothing window | 30 s | How far back the smoothing looks (the time constant for Exponential) |
| Smooth stable readings only | On | Leaves readings out while the scale reports the weight as moving |

The window is in seconds, not samples, so the result does not depend on the
poll interval.

- **Average** is the mean of the window. It is the steadiest, and it lags a
  step change by about the window length.
- **Median** is the middle reading of the window. It ignores short spikes,
  such as a hand resting on the scale.
- **Exponential** weights recent readings more and settles gradually.

The module sends ADC counts as whole numbers and millivolts with four
decimals. The smoothed versions average several readings, which is the only
way to get finer resolution out of them.

## How it works

Every poll publishes `QASI1C` to `$CSL/<module id>/RX/SC`. The module replies
on `$CSL/<module id>/TX/SC` with one comma-separated line:

    QASI1C,1,1,1,S,     1.250,     1.000,     0.250,   1.25012,   1234567,    0.1234,kg

Fields after the three IDs: status (`S` stable, `D` moving), gross, net, tare,
high-resolution weight, ADC counts, millivolts, unit.

The broker login is `CSL-<module id>` with the module PIN as the password.

## Tests

    pip install -r requirements_test.txt
    npm install --prefix tests/broker
    pytest

The tests start a local broker with a fake module behind it (`tests/broker`),
so they need Node.js and never touch the real cloud.

See [DEVELOPMENT.md](DEVELOPMENT.md) for the code layout, what is not yet
verified against a real module, and the rule about keeping account values out
of the repository.

## Languages

English and Slovenian.

## Licence

[MIT](LICENSE)
