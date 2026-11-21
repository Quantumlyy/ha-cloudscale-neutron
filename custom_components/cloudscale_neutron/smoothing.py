"""Time-windowed smoothing for scale values.

Windows are in seconds, not samples, so the result does not depend on the poll
interval or on extra readings triggered by other clients (for example an open
Scale Monitor page polling several times a second).
"""

from __future__ import annotations

from collections import deque
import math
from statistics import fmean, median

SMOOTHING_NONE = "none"
SMOOTHING_MEAN = "mean"
SMOOTHING_MEDIAN = "median"
SMOOTHING_EXPONENTIAL = "exponential"
SMOOTHING_METHODS = [
    SMOOTHING_NONE,
    SMOOTHING_MEAN,
    SMOOTHING_MEDIAN,
    SMOOTHING_EXPONENTIAL,
]


class Smoother:
    """Smooths one value.

    mean         average of the readings from the last ``window`` seconds
    median       middle reading of the last ``window`` seconds; ignores short
                 spikes such as a hand resting on the bucket
    exponential  low-pass filter with time constant ``window`` seconds; recent
                 readings count more, and it needs no history
    """

    def __init__(self, method: str, window: float) -> None:
        self._method = method
        self._window = max(float(window), 0.0)
        self._samples: deque[tuple[float, float]] = deque()
        self._value: float | None = None
        self._last: float | None = None

    @property
    def value(self) -> float | None:
        """Return the smoothed value, or None before the first reading."""
        return self._value

    def add(self, value: float, now: float) -> None:
        """Add a reading taken at monotonic time ``now``."""
        if self._method == SMOOTHING_EXPONENTIAL:
            if self._value is None or self._last is None or self._window == 0:
                self._value = value
            else:
                alpha = 1 - math.exp(-max(now - self._last, 0.0) / self._window)
                self._value += alpha * (value - self._value)
            self._last = now
            return

        self._samples.append((now, value))
        cutoff = now - self._window
        while len(self._samples) > 1 and self._samples[0][0] < cutoff:
            self._samples.popleft()
        values = [sample for _, sample in self._samples]
        self._value = median(values) if self._method == SMOOTHING_MEDIAN else fmean(values)
