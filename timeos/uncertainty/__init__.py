"""Uncertainty mathematics for TimeOS.

This module provides rigorous uncertainty propagation and
clock drift modeling for temporal data.

Key Components:
    - DriftModel: Clock drift modeling (linear, random walk)
    - propagate: Uncertainty propagation through operations
    - allan_variance: Clock stability analysis
    - confidence_interval: Statistical confidence bounds

Example:
    >>> from timeos.uncertainty import LinearDrift, propagate_sum
    >>>
    >>> # Model clock drift
    >>> drift = LinearDrift(offset=0.001, rate=1e-6)
    >>> error_after_1h = drift.uncertainty_at(3600)
    >>>
    >>> # Combine uncertainties
    >>> combined = propagate_sum([0.001, 0.002, 0.0005])
"""

from timeos.uncertainty.models import (
    DriftModel,
    LinearDrift,
    RandomWalkDrift,
    CombinedDrift,
    QuartzDrift,
)

from timeos.uncertainty.propagation import (
    propagate_sum,
    propagate_difference,
    propagate_product,
    propagate_quotient,
    propagate_power,
    propagate_linear,
    combine_independent,
    combine_correlated,
)

from timeos.uncertainty.allan import (
    allan_variance,
    allan_deviation,
    overlapping_allan_variance,
    modified_allan_variance,
    time_deviation,
    stability_analysis,
)

from timeos.uncertainty.confidence import (
    confidence_interval,
    credible_interval,
    prediction_interval,
    coverage_factor,
)

__all__ = [
    # Drift models
    "DriftModel",
    "LinearDrift",
    "RandomWalkDrift",
    "CombinedDrift",
    "QuartzDrift",
    # Propagation
    "propagate_sum",
    "propagate_difference",
    "propagate_product",
    "propagate_quotient",
    "propagate_power",
    "propagate_linear",
    "combine_independent",
    "combine_correlated",
    # Allan variance
    "allan_variance",
    "allan_deviation",
    "overlapping_allan_variance",
    "modified_allan_variance",
    "time_deviation",
    "stability_analysis",
    # Confidence
    "confidence_interval",
    "credible_interval",
    "prediction_interval",
    "coverage_factor",
]
