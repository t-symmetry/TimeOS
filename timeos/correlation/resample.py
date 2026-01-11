"""Time base resampling.

Provides functions for converting time series to different
sample rates and clock domains.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

from timeos.correlation.align import TimeSeries
from timeos.correlation.interpolate import (
    interpolate_series,
    InterpolationMethod,
)

if TYPE_CHECKING:
    from timeos.clocks.base import ClockSource


@dataclass
class ResampleConfig:
    """Configuration for resampling.

    Attributes:
        rate: Target sample rate in Hz
        method: Interpolation method
        anti_alias: Apply anti-aliasing filter (for downsampling)
        preserve_edges: Try to preserve edge timing
    """
    rate: float
    method: InterpolationMethod = InterpolationMethod.LINEAR
    anti_alias: bool = True
    preserve_edges: bool = True


def resample_to_rate(
    series: TimeSeries,
    target_rate: float,
    method: InterpolationMethod = InterpolationMethod.LINEAR,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
) -> TimeSeries:
    """Resample a time series to a uniform rate.

    Args:
        series: Input time series (possibly non-uniform)
        target_rate: Target sample rate in Hz
        method: Interpolation method
        start_time: Start time for output (default: series start)
        end_time: End time for output (default: series end)

    Returns:
        Uniformly sampled TimeSeries
    """
    if len(series) == 0:
        return TimeSeries(times=[], values=[])

    if target_rate <= 0:
        raise ValueError("target_rate must be positive")

    # Determine time range
    if start_time is None:
        start_time = series.times[0]
    if end_time is None:
        end_time = series.times[-1]

    if end_time <= start_time:
        return TimeSeries(times=[], values=[])

    # Generate uniform time grid
    dt = 1.0 / target_rate
    n_samples = int(math.ceil((end_time - start_time) * target_rate)) + 1

    query_times = [start_time + i * dt for i in range(n_samples)]

    # Clip to actual end time
    query_times = [t for t in query_times if t <= end_time]

    # Interpolate to new times
    return interpolate_series(series, query_times, method, extrapolate=False)


def resample_to_clock(
    series: TimeSeries,
    source_clock: "ClockSource",
    target_clock: "ClockSource",
    target_rate: Optional[float] = None,
    method: InterpolationMethod = InterpolationMethod.LINEAR,
) -> TimeSeries:
    """Resample a time series from one clock domain to another.

    Transforms timestamps from source clock to target clock,
    accounting for offsets and drift.

    Args:
        series: Input time series in source clock domain
        source_clock: Clock source for input timestamps
        target_clock: Target clock domain
        target_rate: If provided, also resample to this rate
        method: Interpolation method

    Returns:
        TimeSeries with timestamps in target clock domain
    """
    if len(series) == 0:
        return TimeSeries(times=[], values=[])

    # Get clock quality info for both clocks
    source_quality = source_clock.get_quality()
    target_quality = target_clock.get_quality()

    # Compute offset between clocks
    # offset = target_time - source_time
    clock_offset = target_quality.offset - source_quality.offset

    # Transform timestamps
    transformed_times = [t + clock_offset for t in series.times]

    # Propagate time uncertainties
    # Combine source uncertainty, clock offset uncertainties
    combined_time_unc = math.sqrt(
        source_quality.estimated_error ** 2 +
        target_quality.estimated_error ** 2
    )

    if series.time_uncertainties:
        new_time_unc = [
            math.sqrt(u ** 2 + combined_time_unc ** 2)
            for u in series.time_uncertainties
        ]
    else:
        new_time_unc = [combined_time_unc] * len(transformed_times)

    transformed = TimeSeries(
        times=transformed_times,
        values=series.values.copy(),
        time_uncertainties=new_time_unc,
        value_uncertainties=series.value_uncertainties,
    )

    # Optionally resample to target rate
    if target_rate is not None:
        return resample_to_rate(transformed, target_rate, method)

    return transformed


def unify_time_base(
    series_list: List[TimeSeries],
    target_rate: float,
    reference_time: Optional[float] = None,
    method: InterpolationMethod = InterpolationMethod.LINEAR,
) -> List[TimeSeries]:
    """Resample multiple time series to a common time base.

    All series are resampled to the same uniform rate and
    time grid, making them directly comparable.

    Args:
        series_list: List of time series to unify
        target_rate: Target sample rate in Hz
        reference_time: Reference start time (default: earliest series start)
        method: Interpolation method

    Returns:
        List of resampled TimeSeries on common time base
    """
    if not series_list:
        return []

    # Find global time range
    all_times = []
    for series in series_list:
        if len(series) > 0:
            all_times.extend([series.times[0], series.times[-1]])

    if not all_times:
        return [TimeSeries(times=[], values=[]) for _ in series_list]

    global_start = min(all_times)
    global_end = max(all_times)

    if reference_time is not None:
        global_start = reference_time

    # Generate common time grid
    dt = 1.0 / target_rate
    n_samples = int(math.ceil((global_end - global_start) * target_rate)) + 1
    common_times = [global_start + i * dt for i in range(n_samples)]

    # Resample each series to common grid
    result = []
    for series in series_list:
        if len(series) == 0:
            # Empty series - fill with NaN
            result.append(TimeSeries(
                times=common_times.copy(),
                values=[float('nan')] * len(common_times),
            ))
        else:
            # Interpolate to common times (with extrapolation disabled)
            resampled = interpolate_series(
                series,
                common_times,
                method,
                extrapolate=False,
            )

            # Mark extrapolated points as NaN
            t_min = series.times[0]
            t_max = series.times[-1]

            for i, t in enumerate(common_times):
                if t < t_min or t > t_max:
                    resampled.values[i] = float('nan')
                    if resampled.value_uncertainties:
                        resampled.value_uncertainties[i] = float('inf')

            result.append(resampled)

    return result


def downsample(
    series: TimeSeries,
    factor: int,
    method: str = "average",
) -> TimeSeries:
    """Downsample a time series by an integer factor.

    Args:
        series: Input time series
        factor: Downsampling factor (must be positive integer)
        method: "average" (mean of factor samples), "decimate" (every nth),
                "min", or "max"

    Returns:
        Downsampled TimeSeries
    """
    if factor < 1:
        raise ValueError("factor must be >= 1")

    if factor == 1 or len(series) == 0:
        return series

    n_out = len(series) // factor

    new_times = []
    new_values = []
    new_time_unc = []
    new_value_unc = []

    for i in range(n_out):
        start = i * factor
        end = start + factor

        block_times = series.times[start:end]
        block_values = series.values[start:end]

        # Time is center of block
        new_times.append(sum(block_times) / len(block_times))

        if method == "average":
            new_values.append(sum(block_values) / len(block_values))
        elif method == "decimate":
            new_values.append(block_values[0])
        elif method == "min":
            new_values.append(min(block_values))
        elif method == "max":
            new_values.append(max(block_values))
        else:
            raise ValueError(f"Unknown method: {method}")

        # Propagate uncertainties
        if series.time_uncertainties:
            block_t_unc = series.time_uncertainties[start:end]
            # RMS for time uncertainty
            new_time_unc.append(
                math.sqrt(sum(u**2 for u in block_t_unc)) / len(block_t_unc)
            )

        if series.value_uncertainties:
            block_v_unc = series.value_uncertainties[start:end]
            if method == "average":
                # Standard error of mean
                new_value_unc.append(
                    math.sqrt(sum(u**2 for u in block_v_unc)) / len(block_v_unc)
                )
            else:
                # Use first/selected point uncertainty
                new_value_unc.append(block_v_unc[0])

    return TimeSeries(
        times=new_times,
        values=new_values,
        time_uncertainties=new_time_unc if new_time_unc else None,
        value_uncertainties=new_value_unc if new_value_unc else None,
    )


def upsample(
    series: TimeSeries,
    factor: int,
    method: InterpolationMethod = InterpolationMethod.LINEAR,
) -> TimeSeries:
    """Upsample a time series by an integer factor.

    Args:
        series: Input time series
        factor: Upsampling factor (must be positive integer)
        method: Interpolation method for new samples

    Returns:
        Upsampled TimeSeries
    """
    if factor < 1:
        raise ValueError("factor must be >= 1")

    if factor == 1 or len(series) < 2:
        return series

    # Generate upsampled time grid
    original_rate = series.mean_rate
    if original_rate <= 0:
        return series

    target_rate = original_rate * factor

    return resample_to_rate(series, target_rate, method)
