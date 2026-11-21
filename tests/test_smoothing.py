"""Unit tests for the smoothing filters and the reply parser."""

import math

import pytest

from custom_components.cloudscale_neutron.parser import parse_reading
from custom_components.cloudscale_neutron.smoothing import Smoother

REPLY = "QASI1C,1,1,1,S,     1.250,     1.000,     0.250,   1.25012,   1234567,    0.1234,kg"


def test_parse_reply() -> None:
    reading = parse_reading(REPLY)
    assert reading.stable and reading.unit == "kg"
    assert (reading.gross, reading.net, reading.tare) == (1.25, 1.0, 0.25)
    assert (reading.high_res, reading.adc, reading.millivolts) == (1.25012, 1234567, 0.1234)
    assert reading.decimals == 3


def test_parse_ignores_other_replies() -> None:
    assert parse_reading("T S      1.000 kg") is None
    assert parse_reading("") is None
    assert parse_reading("QASI1 1 1 1 S 1.250 1.000 0.250 1.25012 1234567 0.1234 kg") is None


def test_parse_unreadable_weight() -> None:
    reading = parse_reading("QASI1C,1,1,1,+,,,,,,,kg")
    assert reading.status == "+" and not reading.stable
    assert reading.net is None and reading.decimals is None


def test_mean_window() -> None:
    smoother = Smoother("mean", 10)
    assert smoother.value is None
    for second, value in enumerate([1.0, 2.0, 3.0]):
        smoother.add(value, float(second))
    assert smoother.value == pytest.approx(2.0)
    smoother.add(9.0, 11.5)  # the first two readings are now older than 10 s
    assert smoother.value == pytest.approx(6.0)
    smoother.add(4.0, 100.0)  # everything else aged out
    assert smoother.value == pytest.approx(4.0)


def test_median_ignores_spike() -> None:
    smoother = Smoother("median", 60)
    for second, value in enumerate([5.0, 5.0, 40.0, 5.0, 5.002]):
        smoother.add(value, float(second))
    assert smoother.value == pytest.approx(5.0)


def test_exponential_time_constant() -> None:
    smoother = Smoother("exponential", 10)
    smoother.add(0.0, 0.0)
    smoother.add(1.0, 10.0)  # one time constant later
    assert smoother.value == pytest.approx(1 - math.exp(-1))
    # two half-steps land in the same place as one full step
    halves = Smoother("exponential", 10)
    halves.add(0.0, 0.0)
    halves.add(1.0, 5.0)
    halves.add(1.0, 10.0)
    assert halves.value == pytest.approx(1 - math.exp(-1))


def test_mean_gains_resolution() -> None:
    """Averaging whole ADC counts gives fractions of a count."""
    smoother = Smoother("mean", 60)
    for second, value in enumerate([1234567, 1234568, 1234567, 1234569]):
        smoother.add(value, float(second))
    assert smoother.value == pytest.approx(1234567.75)
