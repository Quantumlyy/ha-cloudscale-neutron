"""Binary sensors for the CloudScale Neutron integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import NeutronClient
from .entity import NeutronEntity
from .parser import STATUS_OVERLOAD, STATUS_UNDERLOAD, Reading


@dataclass(frozen=True, kw_only=True)
class NeutronBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a Neutron binary sensor."""

    is_on_fn: Callable[[Reading], bool | None]


BINARY_SENSORS: tuple[NeutronBinarySensorDescription, ...] = (
    NeutronBinarySensorDescription(
        key="stable",
        translation_key="stable",
        is_on_fn=lambda r: r.stable,
    ),
    NeutronBinarySensorDescription(
        key="at_zero",
        translation_key="at_zero",
        is_on_fn=lambda r: None if r.gross is None else r.gross == 0,
    ),
    NeutronBinarySensorDescription(
        key="tare_active",
        translation_key="tare_active",
        is_on_fn=lambda r: None if r.tare is None else r.tare != 0,
    ),
    NeutronBinarySensorDescription(
        key="overload",
        translation_key="overload",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda r: r.status == STATUS_OVERLOAD,
    ),
    NeutronBinarySensorDescription(
        key="underload",
        translation_key="underload",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda r: r.status == STATUS_UNDERLOAD,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the binary sensors."""
    client: NeutronClient = entry.runtime_data
    async_add_entities(
        NeutronBinarySensor(client, description) for description in BINARY_SENSORS
    )


class NeutronBinarySensor(NeutronEntity, BinarySensorEntity):
    """A yes/no fact from the scale's latest reading."""

    entity_description: NeutronBinarySensorDescription

    def __init__(
        self, client: NeutronClient, description: NeutronBinarySensorDescription
    ) -> None:
        super().__init__(client, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        if (reading := self._client.reading) is None:
            return None
        return self.entity_description.is_on_fn(reading)
