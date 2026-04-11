"""Time-band scheduler. Pure functions — no I/O, no clock calls."""

from __future__ import annotations

import math
from datetime import datetime, time, timedelta
from typing import Optional

from avell_rgb.state import DeviceState, ScheduleBand


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _time_to_seconds(t: time) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second


def _band_contains(band: ScheduleBand, now_t: time) -> bool:
    start = _parse_hhmm(band.start)
    end = _parse_hhmm(band.end)
    if start == end:
        return False  # zero-length band matches nothing
    if start < end:
        return start <= now_t < end
    # crosses midnight: inside if now >= start OR now < end
    return now_t >= start or now_t < end


def resolve_schedule(
    schedule: list[ScheduleBand],
    presets: dict[str, DeviceState],
    now: datetime,
) -> Optional[DeviceState]:
    """Return the DeviceState for the first band containing `now`, or None
    if no band matches. Raises KeyError if a band references an unknown preset."""
    t = now.time()
    for band in schedule:
        if _band_contains(band, t):
            return presets[band.preset]
    return None


def seconds_until_next_schedule_boundary(
    schedule: list[ScheduleBand],
    now: datetime,
) -> float:
    """Seconds until the next boundary (start or end) across all bands.
    Returns math.inf if schedule is empty."""
    if not schedule:
        return math.inf
    now_s = _time_to_seconds(now.time())
    candidates: list[int] = []
    for band in schedule:
        for point in (_parse_hhmm(band.start), _parse_hhmm(band.end)):
            boundary_s = _time_to_seconds(point)
            delta = boundary_s - now_s
            if delta <= 0:
                delta += 24 * 3600  # wrap to tomorrow
            candidates.append(delta)
    return float(min(candidates))
