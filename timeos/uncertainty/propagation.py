"""Uncertainty propagation functions.

Implements standard uncertainty propagation rules for combining
and transforming uncertainties through mathematical operations.

Based on GUM (Guide to the Expression of Uncertainty in Measurement).
"""

from __future__ import annotations

import math
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass


@dataclass
class UncertainValue:
    """A value with associated uncertainty.

    Attributes:
        value: The nominal value
        uncertainty: Standard uncertainty (1-sigma)
        unit: Optional unit string
    """

    value: float
    uncertainty: float
    unit: str = ""

    @property
    def relative_uncertainty(self) -> float:
        """Relative uncertainty as a fraction."""
        if self.value == 0:
            return float('inf') if self.uncertainty > 0 else 0.0
        return abs(self.uncertainty / self.value)

    def __add__(self, other: UncertainValue) -> UncertainValue:
        """Add two uncertain values."""
        return UncertainValue(
            value=self.value + other.value,
            uncertainty=propagate_sum([self.uncertainty, other.uncertainty]),
            unit=self.unit,
        )

    def __sub__(self, other: UncertainValue) -> UncertainValue:
        """Subtract two uncertain values."""
        return UncertainValue(
            value=self.value - other.value,
            uncertainty=propagate_difference(self.uncertainty, other.uncertainty),
            unit=self.unit,
        )

    def __mul__(self, other: UncertainValue) -> UncertainValue:
        """Multiply two uncertain values."""
        val = self.value * other.value
        unc = propagate_product(
            self.value, self.uncertainty,
            other.value, other.uncertainty,
        )
        return UncertainValue(value=val, uncertainty=unc)

    def __truediv__(self, other: UncertainValue) -> UncertainValue:
        """Divide two uncertain values."""
        val = self.value / other.value
        unc = propagate_quotient(
            self.value, self.uncertainty,
            other.value, other.uncertainty,
        )
        return UncertainValue(value=val, uncertainty=unc)

    def __repr__(self) -> str:
        if self.unit:
            return f"{self.value:.6g} ± {self.uncertainty:.3g} {self.unit}"
        return f"{self.value:.6g} ± {self.uncertainty:.3g}"


def propagate_sum(uncertainties: List[float]) -> float:
    """Propagate uncertainty through addition.

    For independent uncertainties:
        u(sum) = sqrt(u1² + u2² + ... + un²)

    Args:
        uncertainties: List of standard uncertainties

    Returns:
        Combined uncertainty
    """
    if not uncertainties:
        return 0.0
    return math.sqrt(sum(u ** 2 for u in uncertainties))


def propagate_difference(u1: float, u2: float) -> float:
    """Propagate uncertainty through subtraction.

    Same as addition for independent uncertainties:
        u(a - b) = sqrt(u_a² + u_b²)

    Args:
        u1: Uncertainty of first value
        u2: Uncertainty of second value

    Returns:
        Combined uncertainty
    """
    return math.sqrt(u1 ** 2 + u2 ** 2)


def propagate_product(
    a: float, u_a: float,
    b: float, u_b: float,
) -> float:
    """Propagate uncertainty through multiplication.

    For f = a * b:
        u(f)/|f| = sqrt((u_a/a)² + (u_b/b)²)
        u(f) = |a * b| * sqrt((u_a/a)² + (u_b/b)²)

    Args:
        a: First value
        u_a: Uncertainty in a
        b: Second value
        u_b: Uncertainty in b

    Returns:
        Uncertainty in product
    """
    if a == 0 and b == 0:
        return 0.0

    # Handle zero values
    if a == 0:
        return abs(b) * u_a
    if b == 0:
        return abs(a) * u_b

    rel_a = u_a / abs(a)
    rel_b = u_b / abs(b)
    return abs(a * b) * math.sqrt(rel_a ** 2 + rel_b ** 2)


def propagate_quotient(
    a: float, u_a: float,
    b: float, u_b: float,
) -> float:
    """Propagate uncertainty through division.

    For f = a / b:
        u(f)/|f| = sqrt((u_a/a)² + (u_b/b)²)
        u(f) = |a / b| * sqrt((u_a/a)² + (u_b/b)²)

    Args:
        a: Numerator value
        u_a: Uncertainty in numerator
        b: Denominator value
        u_b: Uncertainty in denominator

    Returns:
        Uncertainty in quotient

    Raises:
        ValueError: If denominator is zero
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")

    if a == 0:
        return u_a / abs(b)

    rel_a = u_a / abs(a)
    rel_b = u_b / abs(b)
    return abs(a / b) * math.sqrt(rel_a ** 2 + rel_b ** 2)


def propagate_power(
    x: float, u_x: float,
    n: float,
) -> float:
    """Propagate uncertainty through power function.

    For f = x^n:
        u(f) = |n * x^(n-1)| * u_x = |n| * |x^n| / |x| * u_x

    Args:
        x: Base value
        u_x: Uncertainty in base
        n: Exponent

    Returns:
        Uncertainty in result
    """
    if x == 0:
        if n > 0:
            return 0.0
        raise ValueError("Cannot raise zero to non-positive power with uncertainty")

    result = x ** n
    return abs(n * result / x) * u_x


def propagate_linear(
    values: List[float],
    uncertainties: List[float],
    coefficients: List[float],
) -> float:
    """Propagate uncertainty through linear combination.

    For f = c1*x1 + c2*x2 + ... + cn*xn:
        u(f) = sqrt(sum((ci * u_xi)²))

    Args:
        values: List of values (not used, for completeness)
        uncertainties: List of uncertainties
        coefficients: List of coefficients

    Returns:
        Combined uncertainty
    """
    if len(uncertainties) != len(coefficients):
        raise ValueError("Uncertainties and coefficients must have same length")

    return math.sqrt(sum(
        (c * u) ** 2
        for c, u in zip(coefficients, uncertainties)
    ))


def combine_independent(uncertainties: List[float]) -> float:
    """Combine independent (uncorrelated) uncertainties.

    Uses root-sum-of-squares:
        u_combined = sqrt(u1² + u2² + ... + un²)

    Args:
        uncertainties: List of independent uncertainties

    Returns:
        Combined uncertainty
    """
    return propagate_sum(uncertainties)


def combine_correlated(
    uncertainties: List[float],
    correlation_matrix: Optional[List[List[float]]] = None,
) -> float:
    """Combine correlated uncertainties.

    For correlated uncertainties:
        u² = sum_i(u_i²) + 2 * sum_{i<j}(r_ij * u_i * u_j)

    Args:
        uncertainties: List of uncertainties
        correlation_matrix: Correlation matrix (r_ij).
            If None, assumes full positive correlation (worst case).

    Returns:
        Combined uncertainty
    """
    n = len(uncertainties)
    if n == 0:
        return 0.0

    if correlation_matrix is None:
        # Worst case: full positive correlation
        return sum(uncertainties)

    # Validate matrix dimensions
    if len(correlation_matrix) != n:
        raise ValueError("Correlation matrix size must match uncertainties")

    variance = 0.0

    # Diagonal terms
    for i in range(n):
        variance += uncertainties[i] ** 2

    # Off-diagonal terms (correlation)
    for i in range(n):
        for j in range(i + 1, n):
            r_ij = correlation_matrix[i][j]
            variance += 2 * r_ij * uncertainties[i] * uncertainties[j]

    return math.sqrt(max(0, variance))


def propagate_function(
    func: Callable[..., float],
    values: List[float],
    uncertainties: List[float],
    step_size: float = 1e-8,
) -> Tuple[float, float]:
    """Propagate uncertainty through arbitrary function numerically.

    Uses numerical differentiation to estimate sensitivity coefficients,
    then applies linear propagation.

    Args:
        func: Function to evaluate
        values: Input values
        uncertainties: Input uncertainties
        step_size: Step size for numerical differentiation

    Returns:
        Tuple of (function_result, uncertainty)
    """
    result = func(*values)

    # Calculate partial derivatives numerically
    partials = []
    for i, x in enumerate(values):
        # Forward difference
        values_plus = list(values)
        values_plus[i] = x + step_size

        f_plus = func(*values_plus)
        partial = (f_plus - result) / step_size
        partials.append(partial)

    # Propagate using linear formula
    uncertainty = math.sqrt(sum(
        (p * u) ** 2
        for p, u in zip(partials, uncertainties)
    ))

    return result, uncertainty


def expand_uncertainty(
    standard_uncertainty: float,
    coverage_factor: float = 2.0,
) -> float:
    """Expand standard uncertainty to coverage interval.

    Args:
        standard_uncertainty: Standard (1-sigma) uncertainty
        coverage_factor: k factor (2 for 95%, 3 for 99.7%)

    Returns:
        Expanded uncertainty
    """
    return coverage_factor * standard_uncertainty


def coverage_probability(coverage_factor: float) -> float:
    """Calculate coverage probability for given k-factor.

    Assumes normal distribution.

    Args:
        coverage_factor: k factor

    Returns:
        Coverage probability (0 to 1)
    """
    # Use error function
    # P = erf(k / sqrt(2))
    return math.erf(coverage_factor / math.sqrt(2))
