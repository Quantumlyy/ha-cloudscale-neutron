"""Weight sensors for the CloudScale Neutron integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfElectricPotential, UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import NeutronClient
from .const import DOMAIN, SMOOTHED_KEYS
from .entity import NeutronEntity
from .parser import Reading
from .smoothing import SMOOTHING_NONE

# Units the scale can report that Home Assistant knows as a weight.
WEIGHT_UNITS = {
    "kg": UnitOfMass.KILOGRAMS,
    "g": UnitOfMass.GRAMS,
    "mg": UnitOfMass.MILLIGRAMS,
    "lb": UnitOfMass.POUNDS,
    "oz": UnitOfMass.OUNCES,
}

# The module sends millivolts with four decimals and ADC counts as whole
# numbers. Smoothed values average several readings, so they carry more.
MILLIVOLT_DECIMALS = 4
HIGH_RES_EXTRA_DECIMALS = 2
SMOOTHED_EXTRA_DECIMALS = 1


@dataclass(frozen=True, kw_only=True)
class NeutronSensorDescription(SensorEntityDescription):
    """Describes a Neutron sensor."""

    value_fn: Callable[[Reading], float | int | None]
    is_weight: bool = False
    # Decimals shown beyond what the scale prints for a weight.
    extra_decimals: int = 0
    # Key of the smoothed value to show instead of the latest reading.
    smoothed_key: str | None = None


SENSORS: tuple[NeutronSensorDescription, ...] = (
    NeutronSensorDescription(
        key="net",
        translation_key="net",
        is_weight=True,
        value_fn=lambda r: r.net,
    ),
    NeutronSensorDescription(
        key="gross",
        translation_key="gross",
        is_weight=True,
        value_fn=lambda r: r.gross,
    ),
    NeutronSensorDescription(
        key="tare",
        translation_key="tare",
        is_weight=True,
        value_fn=lambda r: r.tare,
    ),
    NeutronSensorDescription(
        key="high_res",
        translation_key="high_res",
        is_weight=True,
        extra_decimals=HIGH_RES_EXTRA_DECIMALS,
        entity_registry_enabled_default=False,
        value_fn=lambda r: r.high_res,
    ),
    NeutronSensorDescription(
        key="adc",
        translation_key="adc",
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda r: r.adc,
    ),
    NeutronSensorDescription(
        key="millivolts",
        translation_key="millivolts",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        suggested_display_precision=MILLIVOLT_DECIMALS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda r: r.millivolts,
    ),
)

SMOOTHED_SENSORS: tuple[NeutronSensorDescription, ...] = (
    NeutronSensorDescription(
        key="net_smoothed",
        translation_key="net_smoothed",
        is_weight=True,
        extra_decimals=SMOOTHED_EXTRA_DECIMALS,
        smoothed_key="net",
        value_fn=lambda r: r.net,
    ),
    NeutronSensorDescription(
        key="gross_smoothed",
        translation_key="gross_smoothed",
        is_weight=True,
        extra_decimals=SMOOTHED_EXTRA_DECIMALS,
        smoothed_key="gross",
        value_fn=lambda r: r.gross,
    ),
    NeutronSensorDescription(
        key="adc_smoothed",
        translation_key="adc_smoothed",
        suggested_display_precision=SMOOTHED_EXTRA_DECIMALS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        smoothed_key="adc",
        value_fn=lambda r: r.adc,
    ),
    NeutronSensorDescription(
        key="millivolts_smoothed",
        translation_key="millivolts_smoothed",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        suggested_display_precision=MILLIVOLT_DECIMALS + SMOOTHED_EXTRA_DECIMALS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        smoothed_key="millivolts",
        value_fn=lambda r: r.millivolts,
    ),
)

# Decimals kept in the stored state of a smoothed value, so that averaging
# noise in the last float digits does not write a new state on every poll.
STATE_ROUNDING = 6


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    client: NeutronClient = entry.runtime_data
    descriptions = list(SENSORS)
    if client.smoothing != SMOOTHING_NONE:
        descriptions.extend(SMOOTHED_SENSORS)
    else:
        # Smoothing was switched off: drop the smoothed sensors it created.
        registry = er.async_get(hass)
        for description in SMOOTHED_SENSORS:
            unique_id = f"{client.module_id}_{description.key}"
            if entity_id := registry.async_get_entity_id("sensor", DOMAIN, unique_id):
                registry.async_remove(entity_id)
    async_add_entities(NeutronSensor(client, description) for description in descriptions)


class NeutronSensor(NeutronEntity, SensorEntity):
    """A value from the scale's reading."""

    entity_description: NeutronSensorDescription
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, client: NeutronClient, description: NeutronSensorDescription
    ) -> None:
        super().__init__(client, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | None:
        description = self.entity_description
        if description.smoothed_key is not None:
            value = self._client.smoothed(description.smoothed_key)
            return None if value is None else round(value, STATE_ROUNDING)
        if (reading := self._client.reading) is None:
            return None
        return description.value_fn(reading)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if not self.entity_description.is_weight:
            return self.entity_description.native_unit_of_measurement
        if (reading := self._client.reading) is None or reading.unit is None:
            return None
        # Fall back to the scale's own unit text (for example "t") when Home
        # Assistant has no matching weight unit.
        return WEIGHT_UNITS.get(reading.unit, reading.unit)

    @property
    def device_class(self) -> SensorDeviceClass | None:
        if not self.entity_description.is_weight:
            return self.entity_description.device_class
        reading = self._client.reading
        if reading is not None and reading.unit in WEIGHT_UNITS:
            return SensorDeviceClass.WEIGHT
        return None

    @property
    def suggested_display_precision(self) -> int | None:
        description = self.entity_description
        if not description.is_weight:
            return description.suggested_display_precision
        # Show weights with as many decimals as the scale itself prints.
        reading = self._client.reading
        if reading is None or reading.decimals is None:
            return None
        return reading.decimals + description.extra_decimals
