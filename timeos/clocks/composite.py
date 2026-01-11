"""Composite clock source with multi-source fusion.

Provides a Kalman filter-based clock that fuses multiple clock sources
for improved accuracy and automatic failover.

The composite clock combines readings from multiple sources (NTP, GPS, PTP, etc.)
using optimal weighted averaging based on each source's uncertainty.
"""

from __future__ import annotations

import time
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple, Any
from enum import Enum

from timeos.clocks.base import (
    ClockSource,
    ClockQuality,
    ClockStatus,
    ClockType,
    ClockReading,
)
from timeos.msgs import ChronoStamp


class FusionMethod(Enum):
    """Method for fusing multiple clock sources."""

    BEST = "best"                  # Use single best source
    WEIGHTED_AVERAGE = "weighted"  # Weighted average by uncertainty
    KALMAN = "kalman"              # Kalman filter fusion


@dataclass
class SourceState:
    """State tracking for a single clock source.

    Attributes:
        source: The clock source
        weight: Current weight in fusion (0-1)
        offset: Estimated offset from composite time
        offset_variance: Variance in offset estimate
        last_reading: Most recent reading
        last_update: Time of last update (monotonic)
        consecutive_failures: Number of consecutive read failures
        enabled: Whether source is enabled for fusion
    """

    source: ClockSource
    weight: float = 0.0
    offset: float = 0.0
    offset_variance: float = float('inf')
    last_reading: Optional[ClockReading] = None
    last_update: float = 0.0
    consecutive_failures: int = 0
    enabled: bool = True


@dataclass
class KalmanState:
    """Kalman filter state for clock fusion.

    State vector: [offset, drift_rate]
    - offset: Current time offset from reference (seconds)
    - drift_rate: Rate of change of offset (seconds/second)

    Attributes:
        x: State estimate [offset, drift_rate]
        P: State covariance matrix (2x2)
        Q: Process noise covariance
        last_update: Time of last update (monotonic)
    """

    x: List[float] = field(default_factory=lambda: [0.0, 0.0])
    P: List[List[float]] = field(default_factory=lambda: [
        [1e-6, 0.0],    # offset variance, offset-drift covariance
        [0.0, 1e-12],   # drift-offset covariance, drift variance
    ])
    Q: List[List[float]] = field(default_factory=lambda: [
        [1e-12, 0.0],   # Process noise for offset
        [0.0, 1e-18],   # Process noise for drift
    ])
    last_update: float = 0.0

    @property
    def offset(self) -> float:
        """Current offset estimate."""
        return self.x[0]

    @property
    def drift_rate(self) -> float:
        """Current drift rate estimate."""
        return self.x[1]

    @property
    def offset_variance(self) -> float:
        """Variance in offset estimate."""
        return self.P[0][0]

    @property
    def uncertainty(self) -> float:
        """1-sigma uncertainty in offset."""
        return math.sqrt(max(0, self.P[0][0]))


class CompositeClock(ClockSource):
    """Multi-source clock with Kalman filter fusion.

    Combines readings from multiple clock sources using optimal
    weighted averaging based on each source's uncertainty. Provides
    automatic failover when sources become unavailable.

    Features:
    - Weighted fusion of multiple sources
    - Kalman filter for optimal state estimation
    - Automatic source quality tracking
    - Failover on source failure
    - Holdover using drift model

    Example:
        >>> ntp = NTPClock()
        >>> gps = GPSClock()
        >>> composite = CompositeClock(sources=[ntp, gps])
        >>> stamp = composite.now()
        >>> print(f"Fused time: {stamp.t} ± {stamp.t_uncertainty}s")

        >>> # Check source weights
        >>> for source_id, weight in composite.get_weights().items():
        ...     print(f"{source_id}: {weight:.2%}")
    """

    def __init__(
        self,
        sources: Optional[List[ClockSource]] = None,
        source_id: str = "composite",
        fusion_method: FusionMethod = FusionMethod.KALMAN,
        update_interval: float = 1.0,
        max_failures: int = 5,
        holdover_drift_rate: float = 1e-6,  # ppm
    ):
        """Initialize composite clock.

        Args:
            sources: List of clock sources to fuse
            source_id: Identifier for this composite clock
            fusion_method: Method for combining sources
            update_interval: Minimum time between updates (seconds)
            max_failures: Failures before disabling a source
            holdover_drift_rate: Assumed drift during holdover (ppm)
        """
        super().__init__(source_id, ClockType.COMPOSITE)

        self._fusion_method = fusion_method
        self._update_interval = update_interval
        self._max_failures = max_failures
        self._holdover_drift_rate = holdover_drift_rate * 1e-6  # Convert ppm to fractional

        # Source tracking
        self._sources: Dict[str, SourceState] = {}
        if sources:
            for source in sources:
                self.add_source(source)

        # Kalman filter state
        self._kalman = KalmanState()
        self._kalman.last_update = time.monotonic()

        # Composite state
        self._last_update = 0.0
        self._in_holdover = False
        self._holdover_start = 0.0

    def add_source(self, source: ClockSource) -> None:
        """Add a clock source to the composite.

        Args:
            source: Clock source to add
        """
        self._sources[source.source_id] = SourceState(source=source)

    def remove_source(self, source_id: str) -> Optional[ClockSource]:
        """Remove a clock source from the composite.

        Args:
            source_id: ID of source to remove

        Returns:
            Removed source, or None if not found
        """
        state = self._sources.pop(source_id, None)
        return state.source if state else None

    def enable_source(self, source_id: str) -> bool:
        """Enable a source for fusion.

        Args:
            source_id: ID of source to enable

        Returns:
            True if source was enabled
        """
        if source_id in self._sources:
            self._sources[source_id].enabled = True
            self._sources[source_id].consecutive_failures = 0
            return True
        return False

    def disable_source(self, source_id: str) -> bool:
        """Disable a source from fusion.

        Args:
            source_id: ID of source to disable

        Returns:
            True if source was disabled
        """
        if source_id in self._sources:
            self._sources[source_id].enabled = False
            return True
        return False

    def get_sources(self) -> List[ClockSource]:
        """Get all clock sources.

        Returns:
            List of clock sources
        """
        return [s.source for s in self._sources.values()]

    def get_weights(self) -> Dict[str, float]:
        """Get current fusion weights for all sources.

        Returns:
            Dict mapping source_id to weight (0-1)
        """
        return {
            source_id: state.weight
            for source_id, state in self._sources.items()
        }

    def get_source_states(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed state for all sources.

        Returns:
            Dict mapping source_id to state info
        """
        return {
            source_id: {
                "enabled": state.enabled,
                "weight": state.weight,
                "offset": state.offset,
                "offset_uncertainty": math.sqrt(max(0, state.offset_variance)),
                "consecutive_failures": state.consecutive_failures,
                "last_update": state.last_update,
                "status": state.source.status.name if state.source else "UNKNOWN",
            }
            for source_id, state in self._sources.items()
        }

    @property
    def status(self) -> ClockStatus:
        """Get composite clock status."""
        # Check if any sources are synced
        synced_sources = []
        for s in self._sources.values():
            if not s.enabled:
                continue
            # Handle both property and method forms of is_synchronized
            try:
                is_sync = s.source.is_synchronized()
            except TypeError:
                is_sync = s.source.is_synchronized
            if is_sync:
                synced_sources.append(s)

        if synced_sources:
            self._in_holdover = False
            return ClockStatus.SYNCED
        elif self._in_holdover:
            return ClockStatus.HOLDOVER
        elif any(s.enabled for s in self._sources.values()):
            return ClockStatus.SYNCING
        else:
            return ClockStatus.FREERUN

    @property
    def in_holdover(self) -> bool:
        """Check if clock is in holdover mode."""
        return self._in_holdover

    def now(self) -> ChronoStamp:
        """Get current fused time with uncertainty.

        Returns:
            ChronoStamp with fused time and combined uncertainty
        """
        self._maybe_update()

        # Get base time
        t = time.time()

        # Apply Kalman offset correction
        t_corrected = t - self._kalman.offset

        # Calculate uncertainty
        uncertainty = self._calculate_uncertainty()

        return ChronoStamp(
            frame_id=self._frame_id,
            t=t_corrected,
            t_uncertainty=uncertainty,
            clock_id=self._source_id,
            clock_class="composite",
        )

    def read(self) -> ClockReading:
        """Get full clock reading with quality metrics.

        Returns:
            ClockReading with fused timestamp and quality
        """
        stamp = self.now()
        quality = self.get_quality()

        return ClockReading(
            stamp=stamp,
            quality=quality,
            status=self.status,
            source_id=self._source_id,
        )

    def get_offset(self) -> Tuple[float, float]:
        """Get estimated offset from reference.

        Returns:
            Tuple of (offset_seconds, uncertainty_seconds)
        """
        self._maybe_update()
        return (self._kalman.offset, self._kalman.uncertainty)

    def get_quality(self) -> ClockQuality:
        """Get composite clock quality metrics.

        Returns:
            ClockQuality combining all source information
        """
        self._maybe_update()

        # Determine stratum (minimum of enabled sources + 1)
        stratums = [
            s.source.get_quality().stratum
            for s in self._sources.values()
            if s.enabled and s.weight > 0
        ]
        stratum = min(stratums) + 1 if stratums else 16

        # Calculate jitter from recent readings variance
        jitter = self._kalman.uncertainty

        # Get best source's sync time
        last_sync = None
        for state in self._sources.values():
            if state.enabled and state.last_reading:
                q = state.source.get_quality()
                if q.last_sync and (last_sync is None or q.last_sync > last_sync):
                    last_sync = q.last_sync

        sync_age = 0.0
        if last_sync:
            sync_age = (datetime.now(timezone.utc) - last_sync).total_seconds()

        return ClockQuality(
            stratum=stratum,
            offset=self._kalman.offset,
            offset_uncertainty=self._kalman.uncertainty,
            jitter=jitter,
            drift_rate=self._kalman.drift_rate * 1e6,  # Convert to ppm
            last_sync=last_sync,
            sync_age=sync_age,
            leap_indicator=0 if self.status == ClockStatus.SYNCED else 3,
        )

    def refresh(self) -> bool:
        """Force update of all sources and fusion.

        Returns:
            True if at least one source updated successfully
        """
        success = False

        for state in self._sources.values():
            if state.enabled:
                try:
                    state.source.refresh()
                    success = True
                except Exception:
                    pass

        self._update()
        return success

    def _maybe_update(self) -> None:
        """Update if interval has passed."""
        now = time.monotonic()
        if now - self._last_update >= self._update_interval:
            self._update()

    def _update(self) -> None:
        """Update fusion state from all sources."""
        now = time.monotonic()
        self._last_update = now

        # Collect readings from enabled sources
        readings: List[Tuple[SourceState, ClockReading]] = []

        for state in self._sources.values():
            if not state.enabled:
                continue

            try:
                reading = state.source.read()
                state.last_reading = reading
                state.last_update = now
                state.consecutive_failures = 0
                readings.append((state, reading))

            except Exception:
                state.consecutive_failures += 1
                if state.consecutive_failures >= self._max_failures:
                    state.enabled = False

        if not readings:
            # Enter holdover if no sources available
            if not self._in_holdover:
                self._in_holdover = True
                self._holdover_start = now
            self._holdover_update(now)
            return

        self._in_holdover = False

        # Fuse readings
        if self._fusion_method == FusionMethod.BEST:
            self._fuse_best(readings)
        elif self._fusion_method == FusionMethod.WEIGHTED_AVERAGE:
            self._fuse_weighted(readings)
        else:  # KALMAN
            self._fuse_kalman(readings, now)

    def _fuse_best(self, readings: List[Tuple[SourceState, ClockReading]]) -> None:
        """Use single best source.

        Args:
            readings: List of (state, reading) pairs
        """
        # Find best by quality score
        best_state, best_reading = max(
            readings,
            key=lambda x: x[1].quality.quality_score
        )

        # Update weights
        for state, _ in readings:
            state.weight = 1.0 if state is best_state else 0.0

        # Use best source's offset
        offset, uncertainty = best_state.source.get_offset()
        self._kalman.x[0] = offset
        self._kalman.P[0][0] = uncertainty ** 2

    def _fuse_weighted(self, readings: List[Tuple[SourceState, ClockReading]]) -> None:
        """Weighted average by inverse variance.

        Args:
            readings: List of (state, reading) pairs
        """
        # Calculate weights from uncertainties
        total_precision = 0.0
        offsets = []

        for state, reading in readings:
            uncertainty = reading.stamp.t_uncertainty
            if uncertainty > 0 and uncertainty < float('inf'):
                precision = 1.0 / (uncertainty ** 2)
                state.weight = precision
                total_precision += precision

                # Get offset from reading
                offset, _ = state.source.get_offset()
                offsets.append((state, offset, precision))
            else:
                state.weight = 0.0

        if total_precision > 0:
            # Normalize weights
            for state, _ in readings:
                state.weight /= total_precision

            # Weighted average offset
            fused_offset = sum(
                offset * precision / total_precision
                for _, offset, precision in offsets
            )

            # Combined variance
            fused_variance = 1.0 / total_precision

            self._kalman.x[0] = fused_offset
            self._kalman.P[0][0] = fused_variance

    def _fuse_kalman(
        self,
        readings: List[Tuple[SourceState, ClockReading]],
        now: float,
    ) -> None:
        """Kalman filter fusion.

        Args:
            readings: List of (state, reading) pairs
            now: Current monotonic time
        """
        dt = now - self._kalman.last_update
        self._kalman.last_update = now

        # Predict step
        self._kalman_predict(dt)

        # Update step with each measurement
        total_info = 0.0

        for state, reading in readings:
            offset, uncertainty = state.source.get_offset()

            if uncertainty > 0 and uncertainty < float('inf'):
                # Measurement update
                info = self._kalman_update(offset, uncertainty ** 2)
                state.weight = info
                state.offset = offset
                state.offset_variance = uncertainty ** 2
                total_info += info
            else:
                state.weight = 0.0

        # Normalize weights
        if total_info > 0:
            for state, _ in readings:
                if state.weight > 0:
                    state.weight /= total_info

    def _kalman_predict(self, dt: float) -> None:
        """Kalman prediction step.

        Args:
            dt: Time since last update
        """
        # State transition: x_new = F * x
        # F = [[1, dt], [0, 1]]
        self._kalman.x[0] += self._kalman.x[1] * dt

        # Covariance prediction: P_new = F * P * F' + Q
        P = self._kalman.P
        Q = self._kalman.Q

        # F * P
        FP = [
            [P[0][0] + dt * P[1][0], P[0][1] + dt * P[1][1]],
            [P[1][0], P[1][1]],
        ]

        # F * P * F'
        FPFt = [
            [FP[0][0] + dt * FP[0][1], FP[0][1]],
            [FP[1][0] + dt * FP[1][1], FP[1][1]],
        ]

        # Add process noise
        self._kalman.P = [
            [FPFt[0][0] + Q[0][0] * dt, FPFt[0][1] + Q[0][1] * dt],
            [FPFt[1][0] + Q[1][0] * dt, FPFt[1][1] + Q[1][1] * dt],
        ]

    def _kalman_update(self, measurement: float, variance: float) -> float:
        """Kalman measurement update step.

        Args:
            measurement: Offset measurement
            variance: Measurement variance

        Returns:
            Information gain from this measurement
        """
        # Innovation
        y = measurement - self._kalman.x[0]

        # Innovation covariance: S = H * P * H' + R
        # H = [1, 0] (we measure offset directly)
        S = self._kalman.P[0][0] + variance

        if S <= 0:
            return 0.0

        # Kalman gain: K = P * H' * S^-1
        K = [self._kalman.P[0][0] / S, self._kalman.P[1][0] / S]

        # State update: x = x + K * y
        self._kalman.x[0] += K[0] * y
        self._kalman.x[1] += K[1] * y

        # Covariance update: P = (I - K * H) * P
        P = self._kalman.P
        self._kalman.P = [
            [(1 - K[0]) * P[0][0], (1 - K[0]) * P[0][1]],
            [-K[1] * P[0][0] + P[1][0], -K[1] * P[0][1] + P[1][1]],
        ]

        # Information gain is inverse of innovation variance
        return 1.0 / S

    def _holdover_update(self, now: float) -> None:
        """Update state during holdover.

        Args:
            now: Current monotonic time
        """
        dt = now - self._kalman.last_update
        self._kalman.last_update = now

        # Predict with increased uncertainty
        self._kalman_predict(dt)

        # Add holdover uncertainty growth
        holdover_duration = now - self._holdover_start
        holdover_variance = (self._holdover_drift_rate * holdover_duration) ** 2
        self._kalman.P[0][0] += holdover_variance

    def _calculate_uncertainty(self) -> float:
        """Calculate combined uncertainty.

        Returns:
            Uncertainty in seconds
        """
        # Base uncertainty from Kalman state
        base_uncertainty = self._kalman.uncertainty

        # Add holdover uncertainty if applicable
        if self._in_holdover:
            holdover_duration = time.monotonic() - self._holdover_start
            holdover_uncertainty = self._holdover_drift_rate * holdover_duration
            return math.sqrt(base_uncertainty ** 2 + holdover_uncertainty ** 2)

        return max(base_uncertainty, 1e-9)  # Minimum 1 ns


class SimulatedCompositeClock(ClockSource):
    """Simulated composite clock for testing.

    Provides a configurable composite clock without real sources.
    """

    def __init__(
        self,
        num_sources: int = 3,
        base_uncertainty: float = 1e-6,
        source_id: str = "composite_sim",
    ):
        """Initialize simulated composite clock.

        Args:
            num_sources: Number of simulated sources
            base_uncertainty: Base uncertainty in seconds
            source_id: Source identifier
        """
        super().__init__(source_id, ClockType.COMPOSITE)
        self._num_sources = num_sources
        self._base_uncertainty = base_uncertainty
        self._status = ClockStatus.SYNCED

    def now(self) -> ChronoStamp:
        t = time.time()
        # Composite reduces uncertainty by sqrt(N)
        uncertainty = self._base_uncertainty / math.sqrt(self._num_sources)

        return ChronoStamp(
            frame_id=self._frame_id,
            t=t,
            t_uncertainty=uncertainty,
            clock_id=self._source_id,
            clock_class="composite",
        )

    def read(self) -> ClockReading:
        stamp = self.now()
        return ClockReading(
            stamp=stamp,
            quality=self.get_quality(),
            status=self.status,
            source_id=self._source_id,
        )

    def get_offset(self) -> Tuple[float, float]:
        uncertainty = self._base_uncertainty / math.sqrt(self._num_sources)
        return (0.0, uncertainty)

    def get_quality(self) -> ClockQuality:
        return ClockQuality(
            stratum=2,
            offset=0.0,
            offset_uncertainty=self._base_uncertainty / math.sqrt(self._num_sources),
            jitter=self._base_uncertainty / 10,
            last_sync=datetime.now(timezone.utc),
            sync_age=0.0,
            leap_indicator=0,
        )

    def refresh(self) -> bool:
        return True
