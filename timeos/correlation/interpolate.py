"""Uncertainty-aware interpolation.

Provides functions for interpolating time series values with
proper uncertainty propagation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple, Optional, Sequence
from enum import Enum

from timeos.correlation.align import TimeSeries


class InterpolationMethod(Enum):
    """Interpolation method."""
    NEAREST = "nearest"
    LINEAR = "linear"
    CUBIC = "cubic"  # Simplified cubic spline
    HOLD = "hold"    # Zero-order hold (previous value)


@dataclass
class InterpolatedValue:
    """Result of interpolating at a single point.

    Attributes:
        time: The query time
        value: Interpolated value
        uncertainty: Uncertainty in the value
        time_uncertainty: Uncertainty in time (if input times have uncertainty)
        method: Interpolation method used
        extrapolated: True if point was outside data range
    """
    time: float
    value: float
    uncertainty: float
    time_uncertainty: float = 0.0
    method: str = "linear"
    extrapolated: bool = False


def interpolate_at(
    series: TimeSeries,
    query_time: float,
    method: InterpolationMethod = InterpolationMethod.LINEAR,
    extrapolate: bool = False,
) -> InterpolatedValue:
    """Interpolate a time series at a single time point.

    Propagates uncertainty through the interpolation.

    Args:
        series: Input time series
        query_time: Time at which to interpolate
        method: Interpolation method
        extrapolate: If True, allow extrapolation beyond data range

    Returns:
        InterpolatedValue with the result and uncertainty
    """
    if len(series) == 0:
        return InterpolatedValue(
            time=query_time,
            value=float('nan'),
            uncertainty=float('inf'),
            method=method.value,
            extrapolated=True,
        )

    if len(series) == 1:
        # Single point - return it with any available uncertainty
        unc = series.value_uncertainties[0] if series.value_uncertainties else 0.0
        t_unc = series.time_uncertainties[0] if series.time_uncertainties else 0.0
        return InterpolatedValue(
            time=query_time,
            value=series.values[0],
            uncertainty=unc,
            time_uncertainty=t_unc,
            method="constant",
            extrapolated=query_time != series.times[0],
        )

    # Find bracketing indices
    t_min = series.times[0]
    t_max = series.times[-1]

    is_extrapolated = query_time < t_min or query_time > t_max

    if is_extrapolated and not extrapolate:
        # Clamp to range
        if query_time < t_min:
            query_time = t_min
        else:
            query_time = t_max
        is_extrapolated = False

    # Binary search for bracketing interval
    left = 0
    right = len(series) - 1

    while right - left > 1:
        mid = (left + right) // 2
        if series.times[mid] <= query_time:
            left = mid
        else:
            right = mid

    # Handle edge cases for extrapolation
    if query_time <= series.times[0]:
        left = 0
        right = 1
    elif query_time >= series.times[-1]:
        left = len(series) - 2
        right = len(series) - 1

    t0, t1 = series.times[left], series.times[right]
    v0, v1 = series.values[left], series.values[right]

    # Get uncertainties if available
    u0 = series.value_uncertainties[left] if series.value_uncertainties else 0.0
    u1 = series.value_uncertainties[right] if series.value_uncertainties else 0.0
    tu0 = series.time_uncertainties[left] if series.time_uncertainties else 0.0
    tu1 = series.time_uncertainties[right] if series.time_uncertainties else 0.0

    if method == InterpolationMethod.NEAREST:
        # Nearest neighbor
        if abs(query_time - t0) <= abs(query_time - t1):
            return InterpolatedValue(
                time=query_time,
                value=v0,
                uncertainty=u0,
                time_uncertainty=tu0,
                method="nearest",
                extrapolated=is_extrapolated,
            )
        else:
            return InterpolatedValue(
                time=query_time,
                value=v1,
                uncertainty=u1,
                time_uncertainty=tu1,
                method="nearest",
                extrapolated=is_extrapolated,
            )

    elif method == InterpolationMethod.HOLD:
        # Zero-order hold (previous value)
        return InterpolatedValue(
            time=query_time,
            value=v0,
            uncertainty=u0,
            time_uncertainty=tu0,
            method="hold",
            extrapolated=is_extrapolated,
        )

    elif method == InterpolationMethod.LINEAR:
        # Linear interpolation with uncertainty propagation
        dt = t1 - t0
        if dt == 0:
            # Coincident points
            value = (v0 + v1) / 2
            uncertainty = math.sqrt(u0**2 + u1**2) / 2
            time_uncertainty = math.sqrt(tu0**2 + tu1**2) / 2
        else:
            # Interpolation factor
            alpha = (query_time - t0) / dt

            # Interpolated value
            value = v0 + alpha * (v1 - v0)

            # Uncertainty propagation for linear interpolation:
            # u = sqrt((1-α)²·u0² + α²·u1² + (dv/dt)²·σt²)
            # where σt is the time uncertainty contribution
            dv_dt = (v1 - v0) / dt

            # Combine value uncertainties
            unc_from_values = math.sqrt((1 - alpha)**2 * u0**2 + alpha**2 * u1**2)

            # Time uncertainty contribution
            time_unc_combined = math.sqrt(tu0**2 + tu1**2)
            unc_from_time = abs(dv_dt) * time_unc_combined

            uncertainty = math.sqrt(unc_from_values**2 + unc_from_time**2)
            time_uncertainty = time_unc_combined

        return InterpolatedValue(
            time=query_time,
            value=value,
            uncertainty=uncertainty,
            time_uncertainty=time_uncertainty,
            method="linear",
            extrapolated=is_extrapolated,
        )

    elif method == InterpolationMethod.CUBIC:
        # Simplified cubic - use local 4-point interpolation
        # For full cubic spline, would need pre-computed coefficients
        # This uses Catmull-Rom style interpolation

        # Get 4 points if available
        idx_m1 = max(0, left - 1)
        idx_2 = min(len(series) - 1, right + 1)

        t_m1 = series.times[idx_m1]
        t_2 = series.times[idx_2]
        v_m1 = series.values[idx_m1]
        v_2 = series.values[idx_2]

        # Catmull-Rom parameter
        dt = t1 - t0
        if dt == 0:
            alpha = 0.5
        else:
            alpha = (query_time - t0) / dt

        # Catmull-Rom interpolation
        alpha2 = alpha * alpha
        alpha3 = alpha2 * alpha

        # Simplified coefficients
        value = (
            (-0.5 * v_m1 + 1.5 * v0 - 1.5 * v1 + 0.5 * v_2) * alpha3 +
            (v_m1 - 2.5 * v0 + 2.0 * v1 - 0.5 * v_2) * alpha2 +
            (-0.5 * v_m1 + 0.5 * v1) * alpha +
            v0
        )

        # Uncertainty estimation (simplified - use linear as approximation)
        unc_from_values = math.sqrt((1 - alpha)**2 * u0**2 + alpha**2 * u1**2)

        return InterpolatedValue(
            time=query_time,
            value=value,
            uncertainty=unc_from_values * 1.1,  # Slight increase for cubic
            time_uncertainty=math.sqrt(tu0**2 + tu1**2),
            method="cubic",
            extrapolated=is_extrapolated,
        )

    else:
        raise ValueError(f"Unknown interpolation method: {method}")


def interpolate_series(
    series: TimeSeries,
    query_times: Sequence[float],
    method: InterpolationMethod = InterpolationMethod.LINEAR,
    extrapolate: bool = False,
) -> TimeSeries:
    """Interpolate a time series at multiple time points.

    Args:
        series: Input time series
        query_times: Times at which to interpolate
        method: Interpolation method
        extrapolate: If True, allow extrapolation

    Returns:
        New TimeSeries at the query times
    """
    results = [
        interpolate_at(series, t, method, extrapolate)
        for t in query_times
    ]

    return TimeSeries(
        times=list(query_times),
        values=[r.value for r in results],
        time_uncertainties=[r.time_uncertainty for r in results],
        value_uncertainties=[r.uncertainty for r in results],
    )


def merge_series(
    series_list: List[TimeSeries],
    method: InterpolationMethod = InterpolationMethod.LINEAR,
) -> TimeSeries:
    """Merge multiple time series by interpolating to common times.

    Uses a weighted average based on uncertainties when series overlap.

    Args:
        series_list: List of time series to merge
        method: Interpolation method

    Returns:
        Merged TimeSeries with combined data
    """
    if not series_list:
        return TimeSeries(times=[], values=[])

    if len(series_list) == 1:
        return series_list[0]

    # Collect all unique timestamps
    all_times: set[float] = set()
    for series in series_list:
        all_times.update(series.times)

    sorted_times = sorted(all_times)

    # Interpolate each series to common times and combine
    merged_values = []
    merged_uncertainties = []

    for t in sorted_times:
        values = []
        weights = []

        for series in series_list:
            # Only use series if t is within its range (or close)
            if len(series) > 0:
                t_min = series.times[0]
                t_max = series.times[-1]

                # Allow slight extrapolation
                margin = (t_max - t_min) * 0.01 if t_max > t_min else 0.001

                if t_min - margin <= t <= t_max + margin:
                    result = interpolate_at(series, t, method, extrapolate=True)
                    if not math.isnan(result.value):
                        values.append(result.value)
                        # Weight by inverse variance
                        if result.uncertainty > 0:
                            weights.append(1.0 / result.uncertainty**2)
                        else:
                            weights.append(1.0)

        if values:
            # Weighted average
            total_weight = sum(weights)
            merged_value = sum(v * w for v, w in zip(values, weights)) / total_weight
            # Combined uncertainty
            merged_unc = 1.0 / math.sqrt(total_weight) if total_weight > 0 else 0.0

            merged_values.append(merged_value)
            merged_uncertainties.append(merged_unc)
        else:
            merged_values.append(float('nan'))
            merged_uncertainties.append(float('inf'))

    return TimeSeries(
        times=sorted_times,
        values=merged_values,
        value_uncertainties=merged_uncertainties,
    )
