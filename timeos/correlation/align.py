"""Cross-correlation alignment for data streams.

Provides functions to align data streams from different clock domains
using cross-correlation and other alignment techniques.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Sequence
from enum import Enum


@dataclass
class TimeSeries:
    """A time series with timestamps and values.

    Attributes:
        times: List of timestamps in seconds
        values: List of corresponding values
        time_uncertainties: Optional uncertainties on timestamps
        value_uncertainties: Optional uncertainties on values
    """
    times: List[float]
    values: List[float]
    time_uncertainties: Optional[List[float]] = None
    value_uncertainties: Optional[List[float]] = None

    def __post_init__(self) -> None:
        if len(self.times) != len(self.values):
            raise ValueError("times and values must have same length")
        if self.time_uncertainties and len(self.time_uncertainties) != len(self.times):
            raise ValueError("time_uncertainties must match times length")
        if self.value_uncertainties and len(self.value_uncertainties) != len(self.values):
            raise ValueError("value_uncertainties must match values length")

    def __len__(self) -> int:
        return len(self.times)

    @property
    def duration(self) -> float:
        """Total duration of the time series."""
        if not self.times:
            return 0.0
        return self.times[-1] - self.times[0]

    @property
    def mean_rate(self) -> float:
        """Mean sample rate in Hz."""
        if len(self.times) < 2:
            return 0.0
        return (len(self.times) - 1) / self.duration if self.duration > 0 else 0.0


@dataclass
class AlignmentResult:
    """Result of aligning two time series.

    Attributes:
        offset: Time offset to apply to series_b (seconds)
        offset_uncertainty: Uncertainty in the offset
        correlation: Peak correlation coefficient (-1 to 1)
        lag_samples: Lag in samples at peak correlation
        confidence: Confidence in the alignment (0 to 1)
        method: Alignment method used
    """
    offset: float
    offset_uncertainty: float
    correlation: float
    lag_samples: int
    confidence: float
    method: str = "cross_correlation"


def cross_correlate(
    series_a: Sequence[float],
    series_b: Sequence[float],
    normalize: bool = True,
) -> List[float]:
    """Compute cross-correlation of two sequences.

    Uses direct computation (not FFT) for simplicity and
    to avoid numpy dependency.

    Args:
        series_a: First sequence
        series_b: Second sequence
        normalize: If True, normalize to [-1, 1]

    Returns:
        Cross-correlation values for lags from -(len_b-1) to (len_a-1)
    """
    len_a = len(series_a)
    len_b = len(series_b)

    if len_a == 0 or len_b == 0:
        return []

    # Compute means for normalization
    if normalize:
        mean_a = sum(series_a) / len_a
        mean_b = sum(series_b) / len_b

        # Compute standard deviations
        var_a = sum((x - mean_a) ** 2 for x in series_a) / len_a
        var_b = sum((x - mean_b) ** 2 for x in series_b) / len_b

        std_a = math.sqrt(var_a) if var_a > 0 else 1.0
        std_b = math.sqrt(var_b) if var_b > 0 else 1.0

        # Normalize sequences
        a_norm = [(x - mean_a) / std_a for x in series_a]
        b_norm = [(x - mean_b) / std_b for x in series_b]
    else:
        a_norm = list(series_a)
        b_norm = list(series_b)

    # Compute cross-correlation for all lags
    # Lag range: -(len_b - 1) to (len_a - 1)
    min_lag = -(len_b - 1)
    max_lag = len_a - 1

    result = []
    for lag in range(min_lag, max_lag + 1):
        # Compute correlation at this lag
        corr = 0.0
        count = 0

        for i in range(len_a):
            j = i - lag
            if 0 <= j < len_b:
                corr += a_norm[i] * b_norm[j]
                count += 1

        if count > 0 and normalize:
            corr /= count

        result.append(corr)

    return result


def find_offset(
    series_a: TimeSeries,
    series_b: TimeSeries,
    max_offset: Optional[float] = None,
) -> AlignmentResult:
    """Find the time offset between two time series.

    Uses cross-correlation to find the offset that best aligns
    series_b to series_a.

    Args:
        series_a: Reference time series
        series_b: Series to align
        max_offset: Maximum offset to search (seconds). If None, uses
            the duration of the shorter series.

    Returns:
        AlignmentResult with the optimal offset and statistics
    """
    if len(series_a) < 2 or len(series_b) < 2:
        return AlignmentResult(
            offset=0.0,
            offset_uncertainty=float('inf'),
            correlation=0.0,
            lag_samples=0,
            confidence=0.0,
        )

    # Compute mean sample rates
    rate_a = series_a.mean_rate
    rate_b = series_b.mean_rate

    if rate_a <= 0 or rate_b <= 0:
        return AlignmentResult(
            offset=0.0,
            offset_uncertainty=float('inf'),
            correlation=0.0,
            lag_samples=0,
            confidence=0.0,
        )

    # Use common rate for correlation
    common_rate = min(rate_a, rate_b)

    # Determine max lag in samples
    if max_offset is None:
        max_offset = min(series_a.duration, series_b.duration) / 2

    max_lag_samples = int(max_offset * common_rate)

    # Compute cross-correlation
    xcorr = cross_correlate(series_a.values, series_b.values)

    if not xcorr:
        return AlignmentResult(
            offset=0.0,
            offset_uncertainty=float('inf'),
            correlation=0.0,
            lag_samples=0,
            confidence=0.0,
        )

    # Find peak correlation
    len_b = len(series_b)
    zero_lag_idx = len_b - 1  # Index where lag = 0

    # Search within max_lag range
    best_idx = zero_lag_idx
    best_corr = xcorr[zero_lag_idx] if 0 <= zero_lag_idx < len(xcorr) else 0.0

    search_start = max(0, zero_lag_idx - max_lag_samples)
    search_end = min(len(xcorr), zero_lag_idx + max_lag_samples + 1)

    for i in range(search_start, search_end):
        if abs(xcorr[i]) > abs(best_corr):
            best_corr = xcorr[i]
            best_idx = i

    # Convert index to lag
    lag_samples = best_idx - zero_lag_idx

    # Convert lag to time offset
    offset = lag_samples / common_rate

    # Estimate uncertainty based on correlation peak width
    # (simplified - could use parabolic interpolation)
    offset_uncertainty = 1.0 / common_rate  # At least 1 sample

    # Estimate confidence from correlation strength
    confidence = min(1.0, max(0.0, abs(best_corr)))

    return AlignmentResult(
        offset=offset,
        offset_uncertainty=offset_uncertainty,
        correlation=best_corr,
        lag_samples=lag_samples,
        confidence=confidence,
    )


def align_streams(
    series_a: TimeSeries,
    series_b: TimeSeries,
    result: Optional[AlignmentResult] = None,
) -> Tuple[TimeSeries, TimeSeries]:
    """Align two time series using a computed or provided offset.

    Args:
        series_a: Reference time series (unchanged)
        series_b: Series to align
        result: Pre-computed alignment result. If None, computes alignment.

    Returns:
        Tuple of (series_a, aligned_series_b) with adjusted timestamps
    """
    if result is None:
        result = find_offset(series_a, series_b)

    # Apply offset to series_b timestamps
    aligned_times = [t + result.offset for t in series_b.times]

    # Propagate uncertainty on timestamps
    if series_b.time_uncertainties:
        # Combine with offset uncertainty
        aligned_uncertainties = [
            math.sqrt(u ** 2 + result.offset_uncertainty ** 2)
            for u in series_b.time_uncertainties
        ]
    else:
        aligned_uncertainties = [result.offset_uncertainty] * len(aligned_times)

    aligned_b = TimeSeries(
        times=aligned_times,
        values=series_b.values.copy(),
        time_uncertainties=aligned_uncertainties,
        value_uncertainties=series_b.value_uncertainties,
    )

    return series_a, aligned_b


def align_multiple(
    reference: TimeSeries,
    streams: List[TimeSeries],
    max_offset: Optional[float] = None,
) -> Tuple[TimeSeries, List[TimeSeries], List[AlignmentResult]]:
    """Align multiple streams to a reference.

    Args:
        reference: Reference time series
        streams: List of series to align
        max_offset: Maximum offset to search

    Returns:
        Tuple of (reference, aligned_streams, alignment_results)
    """
    aligned = []
    results = []

    for stream in streams:
        result = find_offset(reference, stream, max_offset)
        _, aligned_stream = align_streams(reference, stream, result)
        aligned.append(aligned_stream)
        results.append(result)

    return reference, aligned, results
