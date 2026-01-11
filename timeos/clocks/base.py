"""Base classes for clock sources.

Provides abstract interfaces and data structures for clock sources
with uncertainty tracking and quality metrics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Tuple, List, Dict, Any

from timeos.msgs import ChronoStamp


class ClockStatus(Enum):
    """Operational status of a clock source."""

    UNKNOWN = auto()      # Status not yet determined
    SYNCING = auto()      # Acquiring synchronization
    SYNCED = auto()       # Synchronized and operational
    HOLDOVER = auto()     # Lost sync, using internal oscillator
    FREERUN = auto()      # No synchronization available
    DEGRADED = auto()     # Synchronized but quality below threshold
    FAULT = auto()        # Hardware or software fault


class ClockType(Enum):
    """Type of clock source."""

    SYSTEM_MONOTONIC = "monotonic"   # System monotonic clock
    SYSTEM_REALTIME = "realtime"     # System realtime clock
    SYSTEM_TAI = "tai"               # International Atomic Time
    NTP = "ntp"                      # Network Time Protocol
    PTP = "ptp"                      # Precision Time Protocol (IEEE 1588)
    GPS = "gps"                      # GPS time
    PPS = "pps"                      # Pulse Per Second discipline
    ATOMIC = "atomic"                # Local atomic reference
    COMPOSITE = "composite"          # Multi-source fusion
    SIMULATED = "sim"                # Simulated clock


@dataclass
class ClockQuality:
    """Quality metrics for a clock source.

    Based on ITU-T G.781 clock quality levels and NTP/PTP metrics.

    Attributes:
        stratum: NTP stratum level (1=reference, 2-15=synchronized, 16=unsync)
        offset: Current offset from reference in seconds
        offset_uncertainty: Uncertainty in offset measurement
        jitter: Short-term frequency variation (RMS, seconds)
        wander: Long-term frequency drift (seconds/second)
        drift_rate: Frequency drift rate (ppm)
        last_sync: Timestamp of last successful synchronization
        sync_age: Time since last sync in seconds
        root_delay: Round-trip delay to stratum-1 source
        root_dispersion: Maximum error accumulation to stratum-1
        leap_indicator: Leap second warning (0=none, 1=insert, 2=delete, 3=unsync)
    """

    stratum: int = 16  # Unsynchronized by default
    offset: float = 0.0
    offset_uncertainty: float = float('inf')
    jitter: float = float('inf')
    wander: float = 0.0
    drift_rate: float = 0.0  # ppm
    last_sync: Optional[datetime] = None
    sync_age: float = float('inf')
    root_delay: float = 0.0
    root_dispersion: float = float('inf')
    leap_indicator: int = 3  # Unsynchronized

    @property
    def is_synchronized(self) -> bool:
        """Check if clock is considered synchronized."""
        return self.stratum < 16 and self.leap_indicator != 3

    @property
    def estimated_error(self) -> float:
        """Estimate total error bound in seconds.

        Combines offset uncertainty, jitter, and root dispersion.
        """
        if not self.is_synchronized:
            return float('inf')

        # Conservative error estimate
        return abs(self.offset) + self.offset_uncertainty + self.jitter + self.root_dispersion

    @property
    def quality_score(self) -> float:
        """Quality score from 0.0 (worst) to 1.0 (best).

        Based on stratum, jitter, and sync status.
        """
        if not self.is_synchronized:
            return 0.0

        # Stratum contribution (lower is better)
        stratum_score = max(0, 1 - (self.stratum - 1) / 15)

        # Jitter contribution (lower is better, target < 1ms)
        jitter_score = max(0, 1 - min(self.jitter, 0.01) / 0.01)

        # Offset contribution (lower is better, target < 1ms)
        offset_score = max(0, 1 - min(abs(self.offset), 0.01) / 0.01)

        # Weighted average
        return 0.4 * stratum_score + 0.3 * jitter_score + 0.3 * offset_score

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stratum": self.stratum,
            "offset": self.offset,
            "offset_uncertainty": self.offset_uncertainty,
            "jitter": self.jitter,
            "wander": self.wander,
            "drift_rate": self.drift_rate,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "sync_age": self.sync_age,
            "root_delay": self.root_delay,
            "root_dispersion": self.root_dispersion,
            "leap_indicator": self.leap_indicator,
            "is_synchronized": self.is_synchronized,
            "estimated_error": self.estimated_error,
            "quality_score": self.quality_score,
        }


@dataclass
class ClockReading:
    """A single reading from a clock source.

    Captures both the timestamp and the quality at time of reading.
    """

    stamp: ChronoStamp
    quality: ClockQuality
    status: ClockStatus
    source_id: str
    read_latency: float = 0.0  # Time to acquire reading (seconds)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stamp": self.stamp.to_dict(),
            "quality": self.quality.to_dict(),
            "status": self.status.name,
            "source_id": self.source_id,
            "read_latency": self.read_latency,
        }


class ClockSource(ABC):
    """Abstract base class for clock sources.

    A ClockSource provides time readings with explicit uncertainty
    and quality metrics. Implementations wrap real clock sources
    (system clocks, NTP, GPS, etc.) with proper error characterization.

    Example:
        >>> clock = SystemClock("monotonic")
        >>> stamp = clock.now()
        >>> print(f"{stamp.t} ± {stamp.t_uncertainty}s")

        >>> quality = clock.get_quality()
        >>> if quality.is_synchronized:
        ...     print(f"Synced, offset: {quality.offset*1e6:.1f} µs")
    """

    def __init__(
        self,
        source_id: str,
        clock_type: ClockType,
        frame_id: str = "utc",
    ):
        """Initialize clock source.

        Args:
            source_id: Unique identifier for this clock source
            clock_type: Type of clock (NTP, GPS, etc.)
            frame_id: Reference frame for timestamps (default: "utc")
        """
        self._source_id = source_id
        self._clock_type = clock_type
        self._frame_id = frame_id
        self._status = ClockStatus.UNKNOWN
        self._quality = ClockQuality()
        self._last_reading: Optional[ClockReading] = None

    @property
    def source_id(self) -> str:
        """Unique identifier for this clock source."""
        return self._source_id

    @property
    def clock_type(self) -> ClockType:
        """Type of clock source."""
        return self._clock_type

    @property
    def frame_id(self) -> str:
        """Reference frame for timestamps."""
        return self._frame_id

    @property
    def status(self) -> ClockStatus:
        """Current operational status."""
        return self._status

    @abstractmethod
    def now(self) -> ChronoStamp:
        """Get current time with uncertainty.

        Returns:
            ChronoStamp with current time, uncertainty, and provenance.
        """
        pass

    @abstractmethod
    def read(self) -> ClockReading:
        """Get full clock reading with quality metrics.

        Returns:
            ClockReading with timestamp, quality, and status.
        """
        pass

    @abstractmethod
    def get_offset(self) -> Tuple[float, float]:
        """Get offset from reference with uncertainty.

        Returns:
            Tuple of (offset_seconds, uncertainty_seconds) relative
            to the clock's reference source.
        """
        pass

    @abstractmethod
    def get_quality(self) -> ClockQuality:
        """Get current clock quality metrics.

        Returns:
            ClockQuality with stratum, jitter, offset, etc.
        """
        pass

    @abstractmethod
    def refresh(self) -> bool:
        """Refresh quality metrics from source.

        Queries the underlying clock source for updated metrics.

        Returns:
            True if refresh succeeded.
        """
        pass

    def is_available(self) -> bool:
        """Check if clock source is available.

        Returns:
            True if clock can provide readings.
        """
        return self._status not in (ClockStatus.UNKNOWN, ClockStatus.FAULT)

    def is_synchronized(self) -> bool:
        """Check if clock is synchronized.

        Returns:
            True if clock has valid synchronization.
        """
        return self._status in (ClockStatus.SYNCED, ClockStatus.DEGRADED)

    def get_uncertainty(self) -> float:
        """Get current uncertainty bound in seconds.

        Convenience method combining quality metrics into
        a single uncertainty value.

        Returns:
            Uncertainty in seconds.
        """
        return self._quality.estimated_error

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"id={self._source_id!r}, "
            f"type={self._clock_type.value}, "
            f"status={self._status.name})"
        )


class ClockRegistry:
    """Registry for managing multiple clock sources.

    Provides centralized access to clock sources with
    automatic quality tracking and source selection.

    Example:
        >>> registry = ClockRegistry()
        >>> registry.register(SystemClock())
        >>> registry.register(NTPClock())
        >>>
        >>> # Get best available clock
        >>> best = registry.get_best()
        >>> stamp = best.now()
    """

    def __init__(self):
        self._sources: Dict[str, ClockSource] = {}
        self._primary: Optional[str] = None

    def register(self, source: ClockSource) -> None:
        """Register a clock source.

        Args:
            source: Clock source to register.
        """
        self._sources[source.source_id] = source

        # Set as primary if first source
        if self._primary is None:
            self._primary = source.source_id

    def unregister(self, source_id: str) -> Optional[ClockSource]:
        """Unregister a clock source.

        Args:
            source_id: ID of source to remove.

        Returns:
            Removed source, or None if not found.
        """
        source = self._sources.pop(source_id, None)

        if self._primary == source_id:
            self._primary = next(iter(self._sources), None)

        return source

    def get(self, source_id: str) -> Optional[ClockSource]:
        """Get clock source by ID.

        Args:
            source_id: ID of source to retrieve.

        Returns:
            Clock source, or None if not found.
        """
        return self._sources.get(source_id)

    def get_all(self) -> List[ClockSource]:
        """Get all registered clock sources.

        Returns:
            List of all clock sources.
        """
        return list(self._sources.values())

    def get_primary(self) -> Optional[ClockSource]:
        """Get primary clock source.

        Returns:
            Primary clock source, or None if no sources registered.
        """
        if self._primary:
            return self._sources.get(self._primary)
        return None

    def set_primary(self, source_id: str) -> bool:
        """Set primary clock source.

        Args:
            source_id: ID of source to set as primary.

        Returns:
            True if source exists and was set as primary.
        """
        if source_id in self._sources:
            self._primary = source_id
            return True
        return False

    def get_best(self) -> Optional[ClockSource]:
        """Get best available clock source.

        Selects the synchronized source with highest quality score.

        Returns:
            Best clock source, or None if no sources available.
        """
        available = [
            s for s in self._sources.values()
            if s.is_available()
        ]

        if not available:
            return None

        # Prefer synchronized sources
        synced = [s for s in available if s.is_synchronized()]
        candidates = synced if synced else available

        # Sort by quality score
        return max(candidates, key=lambda s: s.get_quality().quality_score)

    def refresh_all(self) -> Dict[str, bool]:
        """Refresh all clock sources.

        Returns:
            Dict mapping source_id to refresh success.
        """
        return {
            source_id: source.refresh()
            for source_id, source in self._sources.items()
        }

    def now(self) -> ChronoStamp:
        """Get current time from best available source.

        Returns:
            ChronoStamp from best source.

        Raises:
            RuntimeError: If no clock sources available.
        """
        source = self.get_best()
        if source is None:
            raise RuntimeError("No clock sources available")
        return source.now()

    def __len__(self) -> int:
        return len(self._sources)

    def __iter__(self):
        return iter(self._sources.values())
