# Troubleshooting

## The integration is not in the "Add integration" list

- Restart Home Assistant fully. Custom integrations are only found at startup.
- Check that this file exists:
  `config/custom_components/cloudscale_neutron/manifest.json`. A common slip is
  a doubled folder, such as `cloudscale_neutron/cloudscale_neutron/`.
- Reload the browser page with **Ctrl+F5**. The list is cached.
- Look in **Settings → System → Logs** for `cloudscale_neutron`. A warning
  that a custom integration was found means Home Assistant did load it.

## "Could not reach the broker"

- Check the broker host for typos. Enter the host only, without `wss://` and
  without a path.
- Check the port (443), the path (`/sm`) and that **Use TLS** is on.
- Check that Home Assistant has internet access.

## "The broker rejected the module ID or PIN"

- Check both against the module's label. They are case sensitive.
- If the PIN was changed on the module, use the new one.

## Entities are unavailable

Entities turn unavailable when the broker connection drops or the module
stops answering.

- Check that the module shows as online in Scale Monitor.
- Check the module's own network connection.
- Wait a minute. The integration reconnects by itself.

## The weight does not update

- Check the poll interval under **Configure**. A long interval means few
  updates.
- If you watch a smoothed sensor with **Smooth stable readings only** on, it
  holds its value while the scale reports the weight as moving.

## The tare or zero button does nothing

The scale refuses these commands while the weight is moving. Wait until
**Stable** is on and press again.

## Reporting a problem

Open an issue at
https://github.com/Quantumlyy/ha-cloudscale-neutron/issues and include the
Home Assistant version and the relevant log lines. Do not post your module ID,
PIN or broker host.
