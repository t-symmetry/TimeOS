"""System clock sources.

Provides access to system clocks (monotonic, realtime, TAI) with
proper uncertainty characterization based on clock type.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Tuple, Optional

from timeos.msgs import ChronoStamp
from timeos.clocks.base import (
    ClockSource,
    ClockQuality,
    ClockStatus,
    ClockType,
    ClockReading,
)


# System clock uncertainty estimates (conservative)
# These vary by platform and configuration
CLOCK_UNCERTAINTIES = {
    "monotonic": 1e-6,       # 1 µs - kernel scheduling jitter
    "realtime": 1e-3,        # 1 ms - NTP typical
    "tai": 1e-6,             # 1 µs - if available
    "process_time": 1e-6,    # 1 µs
    "thread_time": 1e-6,     # 1 µs
}


class SystemClock(ClockSource):
    """System clock source.

    Wraps Python's time module clocks with uncertainty tracking.
    Supports monotonic, realtime (wall clock), and TAI clocks.

    Example:
        >>> clock = SystemClock("realtime")
        >>> stamp = clock.now()
        >>> print(f"Time: {stamp.t:.6f} ± {stamp.t_uncertainty:.9f}s")

        >>> # Monotonic clock for elapsed time
        >>> mono = SystemClock("monotonic")
        >>> t0 = mono.now().t
        >>> # ... do work ...
        >>> elapsed = mono.now().t - t0
    """

    def __init__(
        self,
        clock_name: str = "realtime",
        source_id: Optional[str] = None,
        frame_id: str = "utc",
        custom_uncertainty: Optional[float] = None,
    ):
        """Initialize system clock.

        Args:
            clock_name: Clock type - "monotonic", "realtime", or "tai"
            source_id: Unique ID (defaults to "system_{clock_name}")
            frame_id: Reference frame (default: "utc")
            custom_uncertainty: Override default uncertainty estimate
        """
        self._clock_name = clock_name.lower()

        if source_id is None:
            source_id = f"system_{self._clock_name}"

        clock_type = self._get_clock_type()

        super().__init__(
            source_id=source_id,
            clock_type=clock_type,
            frame_id=frame_id,
        )

        # Set uncertainty
        if custom_uncertainty is not None:
            self._uncertainty = custom_uncertainty
        else:
            self._uncertainty = CLOCK_UNCERTAINTIES.get(
                self._clock_name, 1e-3
            )

        # Check availability
        self._clock_func = self._get_clock_func()
        if self._clock_func is not None:
            self._status = ClockStatus.SYNCED
            self._update_quality()
        else:
            self._status = ClockStatus.FAULT

    def _get_clock_type(self) -> ClockType:
        """Map clock name to ClockType."""
        mapping = {
            "monotonic": ClockType.SYSTEM_MONOTONIC,
            "realtime": ClockType.SYSTEM_REALTIME,
            "tai": ClockType.SYSTEM_TAI,
        }
        return mapping.get(self._clock_name, ClockType.SYSTEM_REALTIME)

    def _get_clock_func(self):
        """Get the appropriate time function."""
        if self._clock_name == "monotonic":
            return time.monotonic
        elif self._clock_name == "realtime":
            return time.time
        elif self._clock_name == "tai":
            # TAI requires CLOCK_TAI support (Linux 3.10+)
            if hasattr(time, "clock_gettime") and hasattr(time, "CLOCK_TAI"):
                return lambda: time.clock_gettime(time.CLOCK_TAI)
            else:
                # Fall back to realtime with offset
                # TAI is ahead of UTC by leap seconds (currently 37s)
                return None
        elif self._clock_name == "process_time":
            return time.process_time
        elif self._clock_name == "thread_time":
            if hasattr(time, "thread_time"):
                return time.thread_time
            return None
        else:
            return time.time

    def _update_quality(self) -> None:
        """Update quality metrics."""
        self._quality = ClockQuality(
            stratum=1 if self._clock_name == "tai" else 2,
            offset=0.0,
            offset_uncertainty=self._uncertainty,
            jitter=self._uncertainty,
            wander=0.0,
            drift_rate=0.0,
            last_sync=datetime.now(timezone.utc),
            sync_age=0.0,
            root_delay=0.0,
            root_dispersion=self._uncertainty,
            leap_indicator=0,
        )

    def now(self) -> ChronoStamp:
        """Get current time with uncertainty.

        Returns:
            ChronoStamp with current time and uncertainty.

        Raises:
            RuntimeError: If clock is not available.
        """
        if self._clock_func is None:
            raise RuntimeError(f"Clock {self._clock_name} not available")

        t_before = time.perf_counter()
        t = self._clock_func()
        t_after = time.perf_counter()

        # Account for read latency in uncertainty
        read_latency = t_after - t_before
        uncertainty = self._uncertainty + read_latency / 2

        return ChronoStamp(
            frame_id=self._frame_id,
            t=t,
            t_uncertainty=uncertainty,
            clock_id=self._source_id,
            clock_class=self._clock_type.value,
            provenance=[],
        )

    def read(self) -> ClockReading:
        """Get full clock reading with quality metrics.

        Returns:
            ClockReading with timestamp, quality, and status.
        """
        t_before = time.perf_counter()
        stamp = self.now()
        t_after = time.perf_counter()

        self._last_reading = ClockReading(
            stamp=stamp,
            quality=self._quality,
            status=self._status,
            source_id=self._source_id,
            read_latency=t_after - t_before,
        )

        return self._last_reading

    def get_offset(self) -> Tuple[float, float]:
        """Get offset from reference.

        For system clocks, offset is defined relative to the
        system's reference (typically NTP).

        Returns:
            Tuple of (offset, uncertainty) in seconds.
        """
        # System clock offset would come from NTP/chrony
        # For now, return zero offset with uncertainty
        return (0.0, self._uncertainty)

    def get_quality(self) -> ClockQuality:
        """Get current clock quality metrics.

        Returns:
            ClockQuality with current metrics.
        """
        return self._quality

    def refresh(self) -> bool:
        """Refresh quality metrics.

        For system clocks, this updates the sync age.

        Returns:
            True (always succeeds for system clocks).
        """
        self._update_quality()
        return True

    def get_resolution(self) -> float:
        """Get clock resolution in seconds.

        Returns:
            Clock resolution from time.get_clock_info().
        """
        try:
            info = time.get_clock_info(self._clock_name)
            return info.resolution
        except ValueError:
            return 1e-6  # Default to 1 µs


class MonotonicClock(SystemClock):
    """Monotonic system clock.

    A clock that cannot go backwards, suitable for measuring
    elapsed time. Not affected by NTP adjustments.

    Example:
        >>> clock = MonotonicClock()
        >>> start = clock.now().t
        >>> # ... work ...
        >>> elapsed = clock.now().t - start
    """

    def __init__(
        self,
        source_id: str = "monotonic",
        frame_id: str = "local_monotonic",
    ):
        super().__init__(
            clock_name="monotonic",
            source_id=source_id,
            frame_id=frame_id,
        )


class RealtimeClock(SystemClock):
    """Realtime (wall clock) system clock.

    Returns current wall-clock time, subject to NTP adjustments.
    Use for timestamps that need to correlate with real-world time.

    Example:
        >>> clock = RealtimeClock()
        >>> stamp = clock.now()
        >>> dt = datetime.fromtimestamp(stamp.t, tz=timezone.utc)
    """

    def __init__(
        self,
        source_id: str = "realtime",
        frame_id: str = "utc",
    ):
        super().__init__(
            clock_name="realtime",
            source_id=source_id,
            frame_id=frame_id,
        )


class TAIClock(SystemClock):
    """International Atomic Time (TAI) clock.

    TAI is a continuous time scale without leap seconds.
    Requires Linux 3.10+ with CLOCK_TAI support.

    Note:
        Falls back to realtime + offset if CLOCK_TAI unavailable.

    Example:
        >>> clock = TAIClock()
        >>> if clock.is_available():
        ...     stamp = clock.now()
    """

    # Current TAI-UTC offset (leap seconds as of 2024)
    TAI_UTC_OFFSET = 37.0

    def __init__(
        self,
        source_id: str = "tai",
        frame_id: str = "tai",
    ):
        super().__init__(
            clock_name="tai",
            source_id=source_id,
            frame_id=frame_id,
        )

        # Check if native TAI is available
        self._has_native_tai = (
            hasattr(time, "clock_gettime") and
            hasattr(time, "CLOCK_TAI")
        )

        if not self._has_native_tai:
            # Use realtime with offset
            self._clock_func = lambda: time.time() + self.TAI_UTC_OFFSET
            self._status = ClockStatus.DEGRADED
            # Increase uncertainty due to leap second ambiguity
            self._uncertainty = 1.0

    def get_tai_utc_offset(self) -> float:
        """Get current TAI-UTC offset in seconds.

        Returns:
            Offset in seconds (TAI - UTC).
        """
        return self.TAI_UTC_OFFSET


class HighResolutionClock(SystemClock):
    """High-resolution performance counter.

    Uses time.perf_counter() for maximum resolution.
    Values are relative, not absolute time.

    Example:
        >>> clock = HighResolutionClock()
        >>> t0 = clock.now().t
        >>> # ... precise timing ...
        >>> dt = clock.now().t - t0
    """

    def __init__(
        self,
        source_id: str = "perf_counter",
        frame_id: str = "local_perf",
    ):
        self._clock_name = "perf_counter"
        self._uncertainty = 1e-9  # Nanosecond resolution typical

        super(SystemClock, self).__init__(
            source_id=source_id,
            clock_type=ClockType.SYSTEM_MONOTONIC,
            frame_id=frame_id,
        )

        self._clock_func = time.perf_counter
        self._status = ClockStatus.SYNCED
        self._update_quality()

    def _update_quality(self) -> None:
        """Update quality metrics."""
        self._quality = ClockQuality(
            stratum=0,  # Reference quality for relative time
            offset=0.0,
            offset_uncertainty=self._uncertainty,
            jitter=self._uncertainty,
            last_sync=datetime.now(timezone.utc),
            sync_age=0.0,
            root_dispersion=self._uncertainty,
            leap_indicator=0,
        )

    def get_resolution(self) -> float:
        """Get clock resolution.

        Returns:
            Resolution from perf_counter info.
        """
        try:
            info = time.get_clock_info("perf_counter")
            return info.resolution
        except ValueError:
            return 1e-9
