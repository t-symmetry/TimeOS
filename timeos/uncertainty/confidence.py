"""Confidence and credible intervals.

Provides functions for calculating statistical confidence intervals,
credible intervals (Bayesian), and prediction intervals.
"""

from __future__ import annotations

import math
from typing import Tuple, Optional, List
from dataclasses import dataclass


# Pre-computed t-distribution critical values
# t_alpha/2 for common confidence levels and degrees of freedom
T_TABLE = {
    # (dof, confidence) -> t value
    (1, 0.90): 6.314,
    (1, 0.95): 12.706,
    (1, 0.99): 63.657,
    (2, 0.90): 2.920,
    (2, 0.95): 4.303,
    (2, 0.99): 9.925,
    (3, 0.90): 2.353,
    (3, 0.95): 3.182,
    (3, 0.99): 5.841,
    (4, 0.90): 2.132,
    (4, 0.95): 2.776,
    (4, 0.99): 4.604,
    (5, 0.90): 2.015,
    (5, 0.95): 2.571,
    (5, 0.99): 4.032,
    (10, 0.90): 1.812,
    (10, 0.95): 2.228,
    (10, 0.99): 3.169,
    (20, 0.90): 1.725,
    (20, 0.95): 2.086,
    (20, 0.99): 2.845,
    (30, 0.90): 1.697,
    (30, 0.95): 2.042,
    (30, 0.99): 2.750,
    (float('inf'), 0.90): 1.645,
    (float('inf'), 0.95): 1.960,
    (float('inf'), 0.99): 2.576,
}


def coverage_factor(
    confidence: float = 0.95,
    dof: Optional[int] = None,
) -> float:
    """Get coverage factor (k) for given confidence level.

    For large samples (dof -> infinity), uses normal distribution:
        k = 1.645 for 90%
        k = 1.960 for 95%
        k = 2.576 for 99%

    For small samples, uses t-distribution with given dof.

    Args:
        confidence: Confidence level (0 to 1)
        dof: Degrees of freedom. None for normal distribution.

    Returns:
        Coverage factor k
    """
    if dof is None or dof > 100:
        # Use normal distribution approximation
        if confidence <= 0 or confidence >= 1:
            raise ValueError("Confidence must be between 0 and 1")

        # Approximate inverse normal CDF
        # Using rational approximation
        p = 1 - (1 - confidence) / 2  # One-tailed p

        if p < 0.5:
            p = 1 - p
            sign = -1
        else:
            sign = 1

        t = math.sqrt(-2 * math.log(1 - p))

        # Abramowitz and Stegun approximation
        c0 = 2.515517
        c1 = 0.802853
        c2 = 0.010328
        d1 = 1.432788
        d2 = 0.189269
        d3 = 0.001308

        k = t - (c0 + c1 * t + c2 * t * t) / (1 + d1 * t + d2 * t * t + d3 * t * t * t)
        return sign * k

    # Look up in t-table
    # Find closest dof
    dof_values = [d for d, c in T_TABLE.keys() if c == confidence and d != float('inf')]
    if not dof_values:
        # Use normal approximation
        return coverage_factor(confidence, None)

    if dof in dof_values:
        return T_TABLE[(dof, confidence)]

    # Interpolate between closest values
    dof_values = sorted(dof_values)
    if dof < dof_values[0]:
        return T_TABLE[(dof_values[0], confidence)]
    if dof > dof_values[-1]:
        return T_TABLE[(float('inf'), confidence)]

    # Linear interpolation
    for i in range(len(dof_values) - 1):
        if dof_values[i] <= dof <= dof_values[i + 1]:
            t1 = T_TABLE[(dof_values[i], confidence)]
            t2 = T_TABLE[(dof_values[i + 1], confidence)]
            frac = (dof - dof_values[i]) / (dof_values[i + 1] - dof_values[i])
            return t1 + frac * (t2 - t1)

    return coverage_factor(confidence, None)


def confidence_interval(
    value: float,
    standard_uncertainty: float,
    confidence: float = 0.95,
    dof: Optional[int] = None,
) -> Tuple[float, float]:
    """Calculate confidence interval for a measurement.

    Args:
        value: Measured value
        standard_uncertainty: Standard (1-sigma) uncertainty
        confidence: Confidence level (default 0.95 = 95%)
        dof: Degrees of freedom for t-distribution

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    k = coverage_factor(confidence, dof)
    half_width = k * standard_uncertainty
    return (value - half_width, value + half_width)


def credible_interval(
    samples: List[float],
    confidence: float = 0.95,
) -> Tuple[float, float]:
    """Calculate Bayesian credible interval from samples.

    Uses highest posterior density (HPD) interval approximation
    by taking symmetric quantiles.

    Args:
        samples: Samples from posterior distribution
        confidence: Credible level (default 0.95 = 95%)

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    if not samples:
        raise ValueError("Need at least one sample")

    sorted_samples = sorted(samples)
    n = len(sorted_samples)

    alpha = 1 - confidence
    lower_idx = int(math.floor(n * alpha / 2))
    upper_idx = int(math.ceil(n * (1 - alpha / 2))) - 1

    lower_idx = max(0, min(lower_idx, n - 1))
    upper_idx = max(0, min(upper_idx, n - 1))

    return (sorted_samples[lower_idx], sorted_samples[upper_idx])


def prediction_interval(
    value: float,
    standard_uncertainty: float,
    prediction_uncertainty: float,
    confidence: float = 0.95,
    dof: Optional[int] = None,
) -> Tuple[float, float]:
    """Calculate prediction interval for future observation.

    Prediction interval includes both measurement uncertainty
    and inherent variability of future observations.

    Args:
        value: Predicted value
        standard_uncertainty: Uncertainty in prediction
        prediction_uncertainty: Additional uncertainty for new observation
        confidence: Confidence level
        dof: Degrees of freedom

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    # Combine uncertainties
    total_uncertainty = math.sqrt(
        standard_uncertainty ** 2 + prediction_uncertainty ** 2
    )

    return confidence_interval(value, total_uncertainty, confidence, dof)


@dataclass
class UncertaintyBudget:
    """Uncertainty budget for combining multiple sources.

    Tracks individual contributions and calculates combined
    uncertainty with proper correlation handling.
    """

    contributions: List[Tuple[str, float, float]]  # (name, value, uncertainty)
    correlations: Optional[List[List[float]]] = None

    def add(
        self,
        name: str,
        value: float,
        uncertainty: float,
    ) -> None:
        """Add a contribution to the budget.

        Args:
            name: Name/description of the contribution
            value: Value or sensitivity coefficient
            uncertainty: Standard uncertainty
        """
        self.contributions.append((name, value, uncertainty))

    @property
    def combined_uncertainty(self) -> float:
        """Calculate combined standard uncertainty."""
        if not self.contributions:
            return 0.0

        uncertainties = [u for _, _, u in self.contributions]

        if self.correlations is None:
            # Assume uncorrelated
            return math.sqrt(sum(u ** 2 for u in uncertainties))

        # Include correlations
        n = len(uncertainties)
        variance = sum(u ** 2 for u in uncertainties)

        for i in range(n):
            for j in range(i + 1, n):
                r = self.correlations[i][j]
                variance += 2 * r * uncertainties[i] * uncertainties[j]

        return math.sqrt(max(0, variance))

    def expanded_uncertainty(
        self,
        confidence: float = 0.95,
        dof: Optional[int] = None,
    ) -> float:
        """Calculate expanded uncertainty at given confidence.

        Args:
            confidence: Confidence level
            dof: Degrees of freedom

        Returns:
            Expanded uncertainty
        """
        k = coverage_factor(confidence, dof)
        return k * self.combined_uncertainty

    def summary(self) -> str:
        """Generate uncertainty budget summary.

        Returns:
            Formatted string with contribution table.
        """
        lines = ["Uncertainty Budget", "=" * 50]

        total_var = 0.0
        for name, value, unc in self.contributions:
            contrib = unc ** 2
            total_var += contrib
            pct = 100 * contrib / total_var if total_var > 0 else 0
            lines.append(f"  {name:20s}: {unc:.3e} ({pct:5.1f}%)")

        combined = self.combined_uncertainty
        lines.append("-" * 50)
        lines.append(f"  Combined (k=1)      : {combined:.3e}")
        lines.append(f"  Expanded (k=2, 95%) : {2 * combined:.3e}")

        return "\n".join(lines)


def welch_satterthwaite_dof(
    uncertainties: List[float],
    dofs: List[int],
) -> float:
    """Calculate effective degrees of freedom using Welch-Satterthwaite.

    Used when combining uncertainties from different sources with
    different degrees of freedom.

    Args:
        uncertainties: List of standard uncertainties
        dofs: List of degrees of freedom for each uncertainty

    Returns:
        Effective degrees of freedom
    """
    if len(uncertainties) != len(dofs):
        raise ValueError("Uncertainties and dofs must have same length")

    combined_var = sum(u ** 2 for u in uncertainties)
    if combined_var == 0:
        return float('inf')

    sum_terms = sum(
        (u ** 4) / v if v > 0 else 0
        for u, v in zip(uncertainties, dofs)
    )

    if sum_terms == 0:
        return float('inf')

    v_eff = (combined_var ** 2) / sum_terms
    return v_eff
