"""Clock synchronization detection and drift estimation.

Provides functions for detecting clock steps, estimating drift,
and finding synchronization points between clock domains.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple, Optional, Sequence


@dataclass
class SyncPoint:
    """A synchronization point between two clocks.

    Attributes:
        time_a: Time in clock A
        time_b: Time in clock B
        offset: Offset (time_b - time_a)
        offset_uncertainty: Uncertainty in offset
        quality: Quality of this sync point (0 to 1)
        source: How this sync point was determined
    """
    time_a: float
    time_b: float
    offset: float
    offset_uncertainty: float
    quality: float = 1.0
    source: str = "unknown"


@dataclass
class DriftEstimate:
    """Estimated drift between two clocks.

    Attributes:
        rate: Drift rate (seconds per second, ppm = rate * 1e6)
        rate_uncertainty: Uncertainty in drift rate
        offset_at_epoch: Offset at the reference epoch
        offset_uncertainty: Uncertainty in offset
        epoch: Reference time for offset
        n_points: Number of sync points used
        residual_rms: RMS of residuals
    """
    rate: float
    rate_uncertainty: float
    offset_at_epoch: float
    offset_uncertainty: float
    epoch: float
    n_points: int
    residual_rms: float

    @property
    def rate_ppm(self) -> float:
        """Drift rate in parts per million."""
        return self.rate * 1e6

    @property
    def rate_uncertainty_ppm(self) -> float:
        """Drift rate uncertainty in ppm."""
        return self.rate_uncertainty * 1e6

    def predict_offset(self, time: float) -> Tuple[float, float]:
        """Predict offset at a given time.

        Args:
            time: Time at which to predict

        Returns:
            Tuple of (predicted_offset, uncertainty)
        """
        dt = time - self.epoch
        offset = self.offset_at_epoch + self.rate * dt

        # Propagate uncertainty
        unc = math.sqrt(
            self.offset_uncertainty ** 2 +
            (dt * self.rate_uncertainty) ** 2
        )

        return offset, unc


@dataclass
class ClockStep:
    """A detected clock step (discontinuity).

    Attributes:
        time: Time of the step
        step_size: Size of the step (seconds)
        step_uncertainty: Uncertainty in step size
        before_rate: Drift rate before step
        after_rate: Drift rate after step
    """
    time: float
    step_size: float
    step_uncertainty: float
    before_rate: float = 0.0
    after_rate: float = 0.0


def find_sync_points(
    times_a: Sequence[float],
    times_b: Sequence[float],
    max_offset: float = 1.0,
    tolerance: float = 0.001,
) -> List[SyncPoint]:
    """Find synchronization points between two sets of event times.

    Matches events from clock A to events in clock B based on
    temporal proximity.

    Args:
        times_a: Event times from clock A
        times_b: Event times from clock B
        max_offset: Maximum expected offset between clocks
        tolerance: Tolerance for matching events

    Returns:
        List of SyncPoint matches
    """
    sync_points = []

    for t_a in times_a:
        # Find best matching event in B
        best_match = None
        best_diff = float('inf')

        for t_b in times_b:
            diff = t_b - t_a

            # Check if within expected range
            if abs(diff) <= max_offset + tolerance:
                if abs(diff) < abs(best_diff):
                    best_diff = diff
                    best_match = t_b

        if best_match is not None:
            sync_points.append(SyncPoint(
                time_a=t_a,
                time_b=best_match,
                offset=best_diff,
                offset_uncertainty=tolerance,
                quality=1.0 - abs(best_diff) / (max_offset + tolerance),
                source="event_matching",
            ))

    return sync_points


def estimate_drift(
    sync_points: List[SyncPoint],
    weight_by_quality: bool = True,
) -> DriftEstimate:
    """Estimate drift rate from synchronization points.

    Uses weighted least squares to fit a linear model:
        offset(t) = offset_0 + rate * (t - epoch)

    Args:
        sync_points: List of sync points
        weight_by_quality: Weight points by their quality

    Returns:
        DriftEstimate with fitted parameters
    """
    if not sync_points:
        return DriftEstimate(
            rate=0.0,
            rate_uncertainty=float('inf'),
            offset_at_epoch=0.0,
            offset_uncertainty=float('inf'),
            epoch=0.0,
            n_points=0,
            residual_rms=float('inf'),
        )

    if len(sync_points) == 1:
        sp = sync_points[0]
        return DriftEstimate(
            rate=0.0,
            rate_uncertainty=float('inf'),
            offset_at_epoch=sp.offset,
            offset_uncertainty=sp.offset_uncertainty,
            epoch=sp.time_a,
            n_points=1,
            residual_rms=0.0,
        )

    # Use times from clock A as reference
    times = [sp.time_a for sp in sync_points]
    offsets = [sp.offset for sp in sync_points]

    if weight_by_quality:
        weights = [sp.quality for sp in sync_points]
    else:
        weights = [1.0] * len(sync_points)

    # Normalize weights
    total_weight = sum(weights)
    weights = [w / total_weight for w in weights]

    # Epoch = weighted mean time
    epoch = sum(t * w for t, w in zip(times, weights))

    # Center times
    centered_times = [t - epoch for t in times]

    # Weighted least squares
    # y = offset, x = centered_time
    sum_w = sum(weights)
    sum_wx = sum(w * x for w, x in zip(weights, centered_times))
    sum_wy = sum(w * y for w, y in zip(weights, offsets))
    sum_wxx = sum(w * x * x for w, x in zip(weights, centered_times))
    sum_wxy = sum(w * x * y for w, x, y in zip(weights, centered_times, offsets))

    # Normal equations solution
    denom = sum_w * sum_wxx - sum_wx ** 2

    if abs(denom) < 1e-20:
        # Degenerate case (all times same)
        return DriftEstimate(
            rate=0.0,
            rate_uncertainty=float('inf'),
            offset_at_epoch=sum_wy / sum_w if sum_w > 0 else 0.0,
            offset_uncertainty=float('inf'),
            epoch=epoch,
            n_points=len(sync_points),
            residual_rms=0.0,
        )

    rate = (sum_w * sum_wxy - sum_wx * sum_wy) / denom
    offset_0 = (sum_wy * sum_wxx - sum_wx * sum_wxy) / denom

    # Compute residuals and RMS
    residuals = [
        offsets[i] - (offset_0 + rate * centered_times[i])
        for i in range(len(offsets))
    ]
    residual_rms = math.sqrt(sum(r**2 for r in residuals) / len(residuals))

    # Uncertainty estimates
    n = len(sync_points)
    if n > 2:
        s2 = sum(r**2 for r in residuals) / (n - 2)
        rate_var = s2 * sum_w / denom
        offset_var = s2 * sum_wxx / denom
        rate_unc = math.sqrt(rate_var)
        offset_unc = math.sqrt(offset_var)
    else:
        # Not enough points for variance estimate
        rate_unc = float('inf')
        offset_unc = float('inf')

    return DriftEstimate(
        rate=rate,
        rate_uncertainty=rate_unc,
        offset_at_epoch=offset_0,
        offset_uncertainty=offset_unc,
        epoch=epoch,
        n_points=len(sync_points),
        residual_rms=residual_rms,
    )


def detect_clock_step(
    times_a: Sequence[float],
    offsets: Sequence[float],
    threshold: float = 0.001,
    min_points: int = 3,
) -> List[ClockStep]:
    """Detect clock steps (discontinuities) in offset data.

    Looks for sudden changes in the clock offset that cannot
    be explained by drift.

    Args:
        times_a: Reference times
        offsets: Measured offsets at each time
        threshold: Minimum step size to detect (seconds)
        min_points: Minimum points before/after step

    Returns:
        List of detected ClockStep events
    """
    if len(times_a) < 2 * min_points:
        return []

    steps = []
    n = len(times_a)

    # Simple approach: look for jumps in offset difference
    # More sophisticated: CUSUM or similar change detection

    for i in range(min_points, n - min_points):
        # Local averages before and after
        before_offsets = offsets[i - min_points:i]
        after_offsets = offsets[i:i + min_points]

        mean_before = sum(before_offsets) / len(before_offsets)
        mean_after = sum(after_offsets) / len(after_offsets)

        jump = mean_after - mean_before

        if abs(jump) > threshold:
            # Check if this is a genuine step (not gradual)
            # by looking at the local variance

            var_before = sum((x - mean_before)**2 for x in before_offsets) / len(before_offsets)
            var_after = sum((x - mean_after)**2 for x in after_offsets) / len(after_offsets)

            std = math.sqrt((var_before + var_after) / 2)

            # Step must be significantly larger than noise
            if abs(jump) > 3 * std:
                # Estimate local drift rates
                if i >= 2 * min_points:
                    rate_before = (before_offsets[-1] - offsets[i - 2*min_points]) / (
                        times_a[i-1] - times_a[i - 2*min_points]
                    ) if times_a[i-1] != times_a[i - 2*min_points] else 0.0
                else:
                    rate_before = 0.0

                if i + 2 * min_points < n:
                    rate_after = (offsets[i + 2*min_points - 1] - after_offsets[0]) / (
                        times_a[i + 2*min_points - 1] - times_a[i]
                    ) if times_a[i + 2*min_points - 1] != times_a[i] else 0.0
                else:
                    rate_after = 0.0

                steps.append(ClockStep(
                    time=times_a[i],
                    step_size=jump,
                    step_uncertainty=std,
                    before_rate=rate_before,
                    after_rate=rate_after,
                ))

    # Remove duplicate detections (keep largest)
    if len(steps) > 1:
        filtered = []
        i = 0
        while i < len(steps):
            # Find all steps within a small window
            window = [steps[i]]
            j = i + 1
            while j < len(steps) and steps[j].time - steps[i].time < 0.1:
                window.append(steps[j])
                j += 1

            # Keep the largest step in window
            best = max(window, key=lambda s: abs(s.step_size))
            filtered.append(best)
            i = j

        steps = filtered

    return steps


def correct_drift(
    times: Sequence[float],
    values: Sequence[float],
    drift: DriftEstimate,
) -> Tuple[List[float], List[float]]:
    """Correct times for measured drift.

    Args:
        times: Original timestamps
        values: Data values (unchanged)
        drift: Drift estimate to correct for

    Returns:
        Tuple of (corrected_times, values)
    """
    corrected_times = []
    for t in times:
        offset, _ = drift.predict_offset(t)
        corrected_times.append(t - offset)

    return corrected_times, list(values)


def compare_clocks(
    times_a: Sequence[float],
    times_b: Sequence[float],
    max_offset: float = 1.0,
) -> dict:
    """Compare two clock sources and return statistics.

    Args:
        times_a: Event times from clock A
        times_b: Corresponding times from clock B
        max_offset: Maximum expected offset

    Returns:
        Dictionary with comparison statistics
    """
    if len(times_a) != len(times_b):
        raise ValueError("times_a and times_b must have same length")

    if len(times_a) == 0:
        return {
            "n_points": 0,
            "mean_offset": float('nan'),
            "std_offset": float('nan'),
            "drift_rate_ppm": float('nan'),
            "max_deviation": float('nan'),
        }

    offsets = [tb - ta for ta, tb in zip(times_a, times_b)]

    mean_offset = sum(offsets) / len(offsets)
    var_offset = sum((o - mean_offset)**2 for o in offsets) / len(offsets)
    std_offset = math.sqrt(var_offset)

    # Estimate drift
    sync_points = [
        SyncPoint(
            time_a=ta,
            time_b=tb,
            offset=tb - ta,
            offset_uncertainty=0.001,
        )
        for ta, tb in zip(times_a, times_b)
    ]

    drift = estimate_drift(sync_points)

    return {
        "n_points": len(times_a),
        "mean_offset": mean_offset,
        "std_offset": std_offset,
        "drift_rate_ppm": drift.rate_ppm,
        "drift_rate_uncertainty_ppm": drift.rate_uncertainty_ppm,
        "max_deviation": max(abs(o - mean_offset) for o in offsets),
        "residual_rms": drift.residual_rms,
    }
