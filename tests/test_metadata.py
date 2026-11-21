"""Checks that the files describing the integration agree with each other."""

import json
from pathlib import Path
import re

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cloudscale_neutron import PLATFORMS
from custom_components.cloudscale_neutron.binary_sensor import BINARY_SENSORS
from custom_components.cloudscale_neutron.button import BUTTONS
from custom_components.cloudscale_neutron.const import DOMAIN, SMOOTHED_KEYS
from custom_components.cloudscale_neutron.sensor import (
    SENSORS,
    SETTINGS_SENSORS,
    SMOOTHED_SENSORS,
)

from .common import _data
from .conftest import MID

ROOT = Path(__file__).parent.parent
COMPONENT = ROOT / "custom_components" / DOMAIN


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_matches_the_code() -> None:
    manifest = _json(COMPONENT / "manifest.json")
    assert manifest["domain"] == DOMAIN
    assert manifest["config_flow"] is True
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"])
    # hassfest wants domain and name first, then the rest in alphabetical order
    rest = list(manifest)[2:]
    assert list(manifest)[:2] == ["domain", "name"] and rest == sorted(rest)


def test_every_platform_has_a_module() -> None:
    for platform in PLATFORMS:
        assert (COMPONENT / f"{platform.value}.py").is_file()


def test_hacs_file_is_present_and_named() -> None:
    assert _json(ROOT / "hacs.json")["name"] == _json(COMPONENT / "manifest.json")["name"]


def test_every_entity_has_an_english_name() -> None:
    names = _json(COMPONENT / "translations" / "en.json")["entity"]
    sensors = [*SENSORS, *SETTINGS_SENSORS, *SMOOTHED_SENSORS]
    assert {d.translation_key for d in sensors} == set(names["sensor"])
    assert {d.translation_key for d in BINARY_SENSORS} == set(names["binary_sensor"])
    assert set(BUTTONS) == set(names["button"])


def test_entity_keys_are_unique() -> None:
    sensors = [d.key for d in (*SENSORS, *SETTINGS_SENSORS, *SMOOTHED_SENSORS)]
    assert len(sensors) == len(set(sensors))
    binary = [d.key for d in BINARY_SENSORS]
    assert len(binary) == len(set(binary))


def test_every_smoothed_value_has_a_sensor() -> None:
    assert {d.smoothed_key for d in SMOOTHED_SENSORS} == set(SMOOTHED_KEYS)


async def test_entity_ids_and_defaults(hass: HomeAssistant, socket_enabled) -> None:
    """Entity ids are what users build automations on; renames must be deliberate."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_data(1),  # nothing listens on port 1; entities are created anyway
        options={"smoothing": "mean"},
        unique_id=MID,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    enabled = {e.entity_id for e in entities if not e.disabled}
    disabled = {e.entity_id for e in entities if e.disabled}

    prefix = "neutron_test01_"
    assert enabled == {
        f"sensor.{prefix}net_weight",
        f"sensor.{prefix}gross_weight",
        f"sensor.{prefix}tare",
        f"sensor.{prefix}load",
        f"sensor.{prefix}capacity",
        f"sensor.{prefix}division",
        f"sensor.{prefix}net_weight_smoothed",
        f"sensor.{prefix}gross_weight_smoothed",
        f"binary_sensor.{prefix}stable",
        f"binary_sensor.{prefix}at_zero",
        f"binary_sensor.{prefix}tare_active",
        f"binary_sensor.{prefix}overload",
        f"binary_sensor.{prefix}underload",
        f"button.{prefix}tare",
        f"button.{prefix}zero",
        f"button.{prefix}clear_tare",
    }
    assert disabled == {
        f"sensor.{prefix}high_resolution_weight",
        f"sensor.{prefix}adc_counts",
        f"sensor.{prefix}load_cell_signal",
        f"sensor.{prefix}adc_counts_smoothed",
        f"sensor.{prefix}load_cell_signal_smoothed",
        f"sensor.{prefix}reply_time",
        f"sensor.{prefix}last_reading",
    }
    # unique ids are built from the module id, so they survive renames
    assert all(e.unique_id.startswith(f"{MID}_") for e in entities)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
