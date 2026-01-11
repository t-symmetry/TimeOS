"""Clock sources for TimeOS.

This module provides abstractions for real clock sources with
uncertainty tracking, quality metrics, and multi-source fusion.

Clock Sources:
    - SystemClock: System monotonic/realtime/TAI clocks
    - NTPClock: Network Time Protocol via chrony/ntpd
    - PTPClock: IEEE 1588 Precision Time Protocol
    - GPSClock: GPS time via gpsd with PPS discipline
    - CompositeClock: Multi-source fusion with failover

Example:
    >>> from timeos.clocks import SystemClock, ClockRegistry
    >>> clock = SystemClock()
    >>> stamp = clock.now()
    >>> print(f"Time: {stamp.t:.6f} ± {stamp.t_uncertainty:.9f}s")
"""

from timeos.clocks.base import (
    ClockSource,
    ClockQuality,
    ClockStatus,
    ClockType,
    ClockReading,
    ClockRegistry,
)

from timeos.clocks.system import (
    SystemClock,
    MonotonicClock,
    RealtimeClock,
    TAIClock,
    HighResolutionClock,
)

from timeos.clocks.ntp import NTPClock
from timeos.clocks.ptp import PTPClock, SimulatedPTPClock
from timeos.clocks.gps import GPSClock, SimulatedGPSClock

__all__ = [
    # Base classes
    "ClockSource",
    "ClockQuality",
    "ClockStatus",
    "ClockType",
    "ClockReading",
    "ClockRegistry",
    # System clocks
    "SystemClock",
    "MonotonicClock",
    "RealtimeClock",
    "TAIClock",
    "HighResolutionClock",
    # NTP
    "NTPClock",
    # PTP
    "PTPClock",
    "SimulatedPTPClock",
    # GPS
    "GPSClock",
    "SimulatedGPSClock",
]
