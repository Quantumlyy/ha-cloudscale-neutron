"""Every translation file must cover exactly the keys of the English one."""

import json
from pathlib import Path

import pytest

from custom_components.cloudscale_neutron.const import DOMAIN

TRANSLATIONS = (
    Path(__file__).parent.parent / "custom_components" / DOMAIN / "translations"
)


def _keys(node, prefix=""):
    if isinstance(node, dict):
        return {key for name, value in node.items() for key in _keys(value, f"{prefix}{name}.")}
    return {prefix.rstrip(".")}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "path", sorted(p for p in TRANSLATIONS.glob("*.json") if p.name != "en.json"), ids=lambda p: p.name
)
def test_translation_matches_english(path: Path) -> None:
    english = _keys(_load(TRANSLATIONS / "en.json"))
    translated = _load(path)
    assert _keys(translated) == english

    def texts(node):
        if isinstance(node, dict):
            for value in node.values():
                yield from texts(value)
        else:
            yield node

    assert all(isinstance(text, str) and text.strip() for text in texts(translated))


async def test_slovenian_loads_in_home_assistant(hass) -> None:
    from homeassistant.helpers import translation

    strings = await translation.async_get_translations(hass, "sl", "entity", [DOMAIN])
    assert strings[f"component.{DOMAIN}.entity.sensor.net.name"] == "Neto teža"
    assert strings[f"component.{DOMAIN}.entity.button.tare.name"] == "Tariraj"
