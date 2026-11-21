"""Parser for the Neutron's QASI1C reply line.

Example reply (fields are padded with spaces):

    QASI1C,1,1,1,S,     1.250,     1.000,     0.250,   1.25012,   1234567,    0.1234,kg

Index  Meaning
0      command echo ("QASI1C")
1-3    scale / channel / range identifiers
4      status: S = stable, D = moving (dynamic), + = overload, - = underload
5      gross weight
6      net weight
7      tare
8      high-resolution weight
9      raw ADC counts
10     load cell signal in millivolts
11     unit
"""

from __future__ import annotations

from dataclasses import dataclass

REPLY_PREFIX = "QASI1C"
STATUS_STABLE = "S"


@dataclass(frozen=True, slots=True)
class Reading:
    """One reading from the scale."""

    status: str
    gross: float | None
    net: float | None
    tare: float | None
    high_res: float | None
    adc: int | None
    millivolts: float | None
    unit: str | None
    decimals: int | None = None

    @property
    def stable(self) -> bool:
        """Return True when the scale reports a stable weight."""
        return self.status == STATUS_STABLE


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _decimals(value: str) -> int | None:
    """Return how many decimals the scale printed, e.g. 3 for "0.000"."""
    if _to_float(value) is None:
        return None
    return len(value.partition(".")[2])


def parse_reading(payload: str) -> Reading | None:
    """Parse a QASI1C reply. Return None for anything else."""
    parts = [part.strip() for part in payload.strip().split(",")]
    if len(parts) < 12 or parts[0] != REPLY_PREFIX:
        return None
    return Reading(
        status=parts[4],
        gross=_to_float(parts[5]),
        net=_to_float(parts[6]),
        tare=_to_float(parts[7]),
        high_res=_to_float(parts[8]),
        adc=_to_int(parts[9]),
        millivolts=_to_float(parts[10]),
        unit=parts[11] or None,
        decimals=_decimals(parts[6]),
    )
