# CloudScale Neutron for Home Assistant

A Home Assistant integration that reads a CloudScale Neutron scale through the
Scale Monitor cloud. Nothing changes on the module, and Scale Monitor keeps
working alongside it.

## Setup in three steps

1. **[[Installation]]**: add the integration to Home Assistant with HACS or by
   hand.
2. **[[Setup]]**: find your module ID, PIN and broker host, then add the
   device.
3. **[[Options]]**: set the poll interval and, if you want it, smoothing.

If something does not work, see **[[Troubleshooting]]**.

## What you need

- A CloudScale Neutron module that is online in Scale Monitor.
- The module ID and PIN from the module's label.
- Home Assistant 2026.2 or newer.

## Good to know

This integration uses the same channel the Scale Monitor web app uses. It is
not a documented vendor API, so it may change without notice.
