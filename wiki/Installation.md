# Installation

## With HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Quantumlyy&repository=ha-cloudscale-neutron&category=integration)

1. Press the button and confirm adding the repository.
2. Press **Download** on the CloudScale Neutron page.
3. Restart Home Assistant: **Settings → System**, power icon at the top right,
   **Restart Home Assistant**.

Without the button:

1. In HACS, open the menu at the top right and choose **Custom repositories**.
2. Add `https://github.com/Quantumlyy/ha-cloudscale-neutron` with type
   **Integration**.
3. Find **CloudScale Neutron** in HACS, press **Download**, and restart Home
   Assistant.

## By hand

1. Download the repository as a zip and unpack it.
2. Copy the `custom_components/cloudscale_neutron` folder into the
   `custom_components` folder of your Home Assistant configuration directory.
   Create `custom_components` if it does not exist.
3. Check the path. This file must exist:
   `config/custom_components/cloudscale_neutron/manifest.json`
4. Restart Home Assistant.

Ways to reach the configuration directory on Home Assistant OS: the **Samba
share**, **Studio Code Server** or **File editor** add-ons.

## Updating

- **HACS**: updates show up in HACS and under **Settings → System → Updates**.
- **By hand**: replace the `cloudscale_neutron` folder and restart.

If you move from a hand-copied install to HACS, delete the hand-copied folder
first. Your configured device stays.

Next: **[[Setup]]**
