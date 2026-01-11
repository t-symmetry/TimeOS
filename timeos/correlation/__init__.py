"""Stream correlation and alignment.

Provides tools for aligning data streams from different clock domains,
cross-correlation analysis, and uncertainty-aware interpolation.
"""

from __future__ import annotations

from timeos.correlation.align import (
    cross_correlate,
    find_offset,
    align_streams,
    AlignmentResult,
)
from timeos.correlation.interpolate import (
    interpolate_at,
    interpolate_series,
    InterpolationMethod,
)
from timeos.correlation.resample import (
    resample_to_rate,
    resample_to_clock,
    unify_time_base,
)
from timeos.correlation.sync import (
    detect_clock_step,
    estimate_drift,
    find_sync_points,
    SyncPoint,
    DriftEstimate,
)

__all__ = [
    # Alignment
    "cross_correlate",
    "find_offset",
    "align_streams",
    "AlignmentResult",
    # Interpolation
    "interpolate_at",
    "interpolate_series",
    "InterpolationMethod",
    # Resampling
    "resample_to_rate",
    "resample_to_clock",
    "unify_time_base",
    # Synchronization
    "detect_clock_step",
    "estimate_drift",
    "find_sync_points",
    "SyncPoint",
    "DriftEstimate",
]
