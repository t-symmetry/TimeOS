"""Allan variance and deviation calculations.

Implements Allan variance and related statistics for clock
stability characterization.

Allan variance measures frequency stability as a function of
averaging time, revealing different noise types that dominate
at different time scales.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from enum import Enum, auto


class NoiseType(Enum):
    """Clock noise types identifiable from Allan variance."""

    WHITE_PM = auto()       # White phase modulation (τ^-1)
    FLICKER_PM = auto()     # Flicker phase modulation (τ^-1)
    WHITE_FM = auto()       # White frequency modulation (τ^-0.5)
    FLICKER_FM = auto()     # Flicker frequency modulation (τ^0)
    RANDOM_WALK_FM = auto() # Random walk frequency (τ^0.5)


@dataclass
class StabilityResult:
    """Results from stability analysis.

    Attributes:
        tau: Averaging times
        adev: Allan deviation values
        adev_error: Uncertainty in ADEV (optional)
        dominant_noise: Identified dominant noise types
        noise_parameters: Fitted noise parameters
    """

    tau: List[float]
    adev: List[float]
    adev_error: Optional[List[float]] = None
    dominant_noise: Optional[Dict[float, NoiseType]] = None
    noise_parameters: Optional[Dict[str, float]] = None


def allan_variance(
    data: List[float],
    tau0: float = 1.0,
    taus: Optional[List[float]] = None,
) -> Tuple[List[float], List[float]]:
    """Calculate Allan variance.

    The Allan variance is defined as:
        σ²_y(τ) = (1/2) * <(y_{n+1} - y_n)²>

    where y_n is the average fractional frequency over the n-th
    interval of length τ.

    For phase data x(t), we use:
        σ²_y(τ) = (1 / 2τ²) * <(x_{n+2} - 2*x_{n+1} + x_n)²>

    Args:
        data: Phase (time error) data samples
        tau0: Sample interval in seconds
        taus: List of averaging times (defaults to powers of 2)

    Returns:
        Tuple of (tau_values, avar_values)
    """
    n = len(data)
    if n < 3:
        raise ValueError("Need at least 3 data points")

    # Default taus: powers of 2 up to n/3
    if taus is None:
        max_m = n // 3
        taus = []
        m = 1
        while m <= max_m:
            taus.append(m * tau0)
            m *= 2

    results_tau = []
    results_avar = []

    for tau in taus:
        m = int(round(tau / tau0))
        if m < 1 or 2 * m >= n:
            continue

        # Calculate second differences
        sum_sq = 0.0
        count = 0

        for i in range(n - 2 * m):
            diff = data[i + 2 * m] - 2 * data[i + m] + data[i]
            sum_sq += diff ** 2
            count += 1

        if count > 0:
            avar = sum_sq / (2 * count * (m * tau0) ** 2)
            results_tau.append(m * tau0)
            results_avar.append(avar)

    return results_tau, results_avar


def allan_deviation(
    data: List[float],
    tau0: float = 1.0,
    taus: Optional[List[float]] = None,
) -> Tuple[List[float], List[float]]:
    """Calculate Allan deviation (square root of Allan variance).

    Args:
        data: Phase (time error) data samples
        tau0: Sample interval in seconds
        taus: List of averaging times

    Returns:
        Tuple of (tau_values, adev_values)
    """
    tau_vals, avar_vals = allan_variance(data, tau0, taus)
    adev_vals = [math.sqrt(v) for v in avar_vals]
    return tau_vals, adev_vals


def overlapping_allan_variance(
    data: List[float],
    tau0: float = 1.0,
    taus: Optional[List[float]] = None,
) -> Tuple[List[float], List[float], List[float]]:
    """Calculate overlapping Allan variance with error estimates.

    The overlapping estimator uses all possible starting points,
    giving better statistical confidence than standard Allan variance.

    Args:
        data: Phase (time error) data samples
        tau0: Sample interval in seconds
        taus: List of averaging times

    Returns:
        Tuple of (tau_values, avar_values, avar_errors)
    """
    n = len(data)
    if n < 3:
        raise ValueError("Need at least 3 data points")

    if taus is None:
        max_m = n // 3
        taus = []
        m = 1
        while m <= max_m:
            taus.append(m * tau0)
            m *= 2

    results_tau = []
    results_avar = []
    results_error = []

    for tau in taus:
        m = int(round(tau / tau0))
        if m < 1 or 2 * m >= n:
            continue

        # Collect all overlapping differences
        diffs = []
        for i in range(n - 2 * m):
            diff = data[i + 2 * m] - 2 * data[i + m] + data[i]
            diffs.append(diff ** 2)

        if len(diffs) > 0:
            mean_sq = sum(diffs) / len(diffs)
            avar = mean_sq / (2 * (m * tau0) ** 2)

            # Error estimate (approximate)
            # For white FM noise, relative error ≈ 1/sqrt(N)
            n_eff = len(diffs)
            rel_error = 1.0 / math.sqrt(n_eff) if n_eff > 0 else float('inf')

            results_tau.append(m * tau0)
            results_avar.append(avar)
            results_error.append(avar * rel_error)

    return results_tau, results_avar, results_error


def modified_allan_variance(
    data: List[float],
    tau0: float = 1.0,
    taus: Optional[List[float]] = None,
) -> Tuple[List[float], List[float]]:
    """Calculate modified Allan variance.

    Modified Allan variance (MVAR) is better at distinguishing
    white PM from flicker PM noise.

    Args:
        data: Phase (time error) data samples
        tau0: Sample interval in seconds
        taus: List of averaging times

    Returns:
        Tuple of (tau_values, mvar_values)
    """
    n = len(data)
    if n < 3:
        raise ValueError("Need at least 3 data points")

    if taus is None:
        max_m = n // 4
        taus = []
        m = 1
        while m <= max_m:
            taus.append(m * tau0)
            m *= 2

    results_tau = []
    results_mvar = []

    for tau in taus:
        m = int(round(tau / tau0))
        if m < 1 or 3 * m >= n:
            continue

        # Modified Allan variance uses phase averages
        sum_sq = 0.0
        count = 0

        for j in range(n - 3 * m + 1):
            # Calculate phase average
            phase_sum = 0.0
            for i in range(m):
                phase_sum += data[j + i + 2 * m] - 2 * data[j + i + m] + data[j + i]

            sum_sq += (phase_sum / m) ** 2
            count += 1

        if count > 0:
            mvar = sum_sq / (2 * count * (m * tau0) ** 2)
            results_tau.append(m * tau0)
            results_mvar.append(mvar)

    return results_tau, results_mvar


def time_deviation(
    data: List[float],
    tau0: float = 1.0,
    taus: Optional[List[float]] = None,
) -> Tuple[List[float], List[float]]:
    """Calculate time deviation (TDEV).

    TDEV is related to modified Allan deviation by:
        TDEV(τ) = τ * MDEV(τ) / sqrt(3)

    TDEV directly characterizes time error in seconds.

    Args:
        data: Phase (time error) data samples
        tau0: Sample interval in seconds
        taus: List of averaging times

    Returns:
        Tuple of (tau_values, tdev_values)
    """
    tau_vals, mvar_vals = modified_allan_variance(data, tau0, taus)

    tdev_vals = []
    for tau, mvar in zip(tau_vals, mvar_vals):
        mdev = math.sqrt(mvar)
        tdev = tau * mdev / math.sqrt(3)
        tdev_vals.append(tdev)

    return tau_vals, tdev_vals


def identify_noise_type(slope: float) -> NoiseType:
    """Identify noise type from ADEV log-log slope.

    Allan deviation scales as τ^α where α indicates noise type:
        α = -1:   White or flicker PM
        α = -0.5: White FM
        α = 0:    Flicker FM
        α = +0.5: Random walk FM

    Args:
        slope: Log-log slope of ADEV vs τ

    Returns:
        Identified noise type
    """
    if slope < -0.75:
        return NoiseType.WHITE_PM  # or FLICKER_PM
    elif slope < -0.25:
        return NoiseType.WHITE_FM
    elif slope < 0.25:
        return NoiseType.FLICKER_FM
    else:
        return NoiseType.RANDOM_WALK_FM


def stability_analysis(
    data: List[float],
    tau0: float = 1.0,
) -> StabilityResult:
    """Perform comprehensive stability analysis.

    Calculates Allan deviation, identifies noise types,
    and estimates noise parameters.

    Args:
        data: Phase (time error) data samples
        tau0: Sample interval in seconds

    Returns:
        StabilityResult with full analysis
    """
    tau_vals, avar_vals, avar_errors = overlapping_allan_variance(data, tau0)
    adev_vals = [math.sqrt(v) for v in avar_vals]
    adev_errors = [math.sqrt(e) if e > 0 else 0 for e in avar_errors]

    # Identify noise types by local slope
    noise_types = {}
    if len(tau_vals) >= 2:
        for i in range(len(tau_vals) - 1):
            log_tau1 = math.log10(tau_vals[i])
            log_tau2 = math.log10(tau_vals[i + 1])
            log_adev1 = math.log10(adev_vals[i]) if adev_vals[i] > 0 else -15
            log_adev2 = math.log10(adev_vals[i + 1]) if adev_vals[i + 1] > 0 else -15

            slope = (log_adev2 - log_adev1) / (log_tau2 - log_tau1)
            noise_types[tau_vals[i]] = identify_noise_type(slope)

    # Estimate noise parameters
    # For white FM: ADEV(1s) gives the white FM coefficient
    noise_params = {}
    if len(adev_vals) > 0:
        # Find ADEV at τ closest to 1s
        idx_1s = min(range(len(tau_vals)), key=lambda i: abs(tau_vals[i] - 1.0))
        noise_params["adev_1s"] = adev_vals[idx_1s]
        noise_params["tau_1s"] = tau_vals[idx_1s]

        # Minimum ADEV (often at flicker floor)
        idx_min = min(range(len(adev_vals)), key=lambda i: adev_vals[i])
        noise_params["adev_min"] = adev_vals[idx_min]
        noise_params["tau_min"] = tau_vals[idx_min]

    return StabilityResult(
        tau=tau_vals,
        adev=adev_vals,
        adev_error=adev_errors,
        dominant_noise=noise_types,
        noise_parameters=noise_params,
    )
