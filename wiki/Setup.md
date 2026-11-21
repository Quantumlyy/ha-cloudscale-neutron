# Setup

## 1. Collect three values

| Value | Where to find it |
|---|---|
| Module ID (MID) | Printed on the module's label |
| Module PIN (CSL) | Printed on the module's label |
| Broker host | In your browser, as described below |

### Finding the broker host

The broker host is the address Scale Monitor uses for live data. It differs
between accounts, so the integration cannot fill it in for you.

1. Open Scale Monitor in Chrome or Edge and sign in.
2. Press **F12** to open the developer tools and go to the **Network** tab.
3. Click the **WS** filter, then reload the page.
4. One request appears whose address starts with `wss://`. Click it.
5. Copy the host from its **Request URL**: the part between `wss://` and the
   next `/`.

The rest of that address gives you the other two fields. In
`wss://HOST/sm` the port is 443 (the default for `wss://`) and the path is
`/sm`.

## 2. Add the integration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=cloudscale_neutron)

1. Press the button, or go to **Settings → Devices & services → Add
   integration** and search for **CloudScale Neutron**.
2. Fill in the form:

   | Field | Value |
   |---|---|
   | Module ID (MID) | From the label |
   | Module PIN (CSL) | From the label |
   | Broker host | The host you copied |
   | Broker port | 443 |
   | WebSocket path | `/sm` |
   | Use TLS | On |
   | Poll interval | 5 seconds is a good start |

3. Press **Submit**. The form logs in to the broker before saving, so a wrong
   value is reported straight away.

## 3. Check the device

Open the new device, named **Neutron** followed by your module ID. You should
see:

- **Net weight**, **Gross weight** and **Tare**
- **Stable**, which is on while the weight is steady
- **At zero** and **Tare active**
- **Overload** and **Underload**, which turn on when the load is outside the
  scale's range
- **Load**, the gross weight as a percentage of the scale's capacity
- **Capacity** and **Division**, read from the scale's own settings
- **Tare**, **Zero** and **Clear tare** buttons

Put a known weight on the scale and check that the three weights show what you
expect.

Five more sensors are switched off by default: **High-resolution weight**,
**ADC counts**, **Load cell signal**, **Reply time** and **Last reading**. To switch one on, open the device,
click the line about entities that are not shown, open the entity, press the
cog icon and turn on **Enabled**.

Next: **[[Options]]**
