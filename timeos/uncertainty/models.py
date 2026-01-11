"""Clock drift models.

Provides mathematical models for clock drift and uncertainty
growth over time. Based on standard clock characterization.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Tuple
import math


class DriftModel(ABC):
    """Abstract base class for clock drift models.

    A drift model predicts how clock uncertainty grows over time,
    based on the physical characteristics of the clock source.
    """

    @abstractmethod
    def uncertainty_at(self, elapsed: float) -> float:
        """Calculate uncertainty after elapsed time.

        Args:
            elapsed: Time elapsed since last sync (seconds)

        Returns:
            Estimated uncertainty in seconds.
        """
        pass

    @abstractmethod
    def offset_at(self, elapsed: float) -> float:
        """Calculate expected offset after elapsed time.

        Args:
            elapsed: Time elapsed since last sync (seconds)

        Returns:
            Expected offset in seconds.
        """
        pass

    def time_to_uncertainty(self, target_uncertainty: float) -> float:
        """Calculate time until uncertainty reaches target.

        Args:
            target_uncertainty: Target uncertainty in seconds

        Returns:
            Time in seconds until target uncertainty reached.
        """
        # Binary search for time
        low, high = 0.0, 1e9
        while high - low > 0.001:
            mid = (low + high) / 2
            if self.uncertainty_at(mid) < target_uncertainty:
                low = mid
            else:
                high = mid
        return mid


@dataclass
class LinearDrift(DriftModel):
    """Linear drift model.

    Models clock drift as a constant rate with initial offset:
        offset(t) = offset_0 + rate * t
        uncertainty(t) = uncertainty_0 + rate_uncertainty * t

    Suitable for temperature-compensated oscillators (TCXO),
    oven-controlled oscillators (OCXO), and disciplined clocks.

    Attributes:
        offset: Initial offset in seconds
        rate: Drift rate in seconds/second (dimensionless, often expressed as ppm)
        offset_uncertainty: Initial offset uncertainty
        rate_uncertainty: Uncertainty in drift rate

    Example:
        >>> # 1 ppm drift rate with 1ms initial uncertainty
        >>> drift = LinearDrift(rate=1e-6, offset_uncertainty=0.001)
        >>> drift.uncertainty_at(3600)  # After 1 hour
        0.0046  # ~4.6 ms
    """

    offset: float = 0.0
    rate: float = 0.0  # ppm is 1e-6
    offset_uncertainty: float = 0.0
    rate_uncertainty: float = 0.0

    def uncertainty_at(self, elapsed: float) -> float:
        """Calculate uncertainty after elapsed time.

        Uncertainty grows linearly with time due to rate uncertainty.
        """
        return self.offset_uncertainty + self.rate_uncertainty * elapsed

    def offset_at(self, elapsed: float) -> float:
        """Calculate expected offset after elapsed time."""
        return self.offset + self.rate * elapsed

    @classmethod
    def from_ppm(
        cls,
        rate_ppm: float,
        rate_uncertainty_ppm: float = 0.0,
        offset: float = 0.0,
        offset_uncertainty: float = 0.0,
    ) -> LinearDrift:
        """Create from parts-per-million values.

        Args:
            rate_ppm: Drift rate in ppm
            rate_uncertainty_ppm: Rate uncertainty in ppm
            offset: Initial offset in seconds
            offset_uncertainty: Initial offset uncertainty in seconds

        Returns:
            LinearDrift instance
        """
        return cls(
            offset=offset,
            rate=rate_ppm * 1e-6,
            offset_uncertainty=offset_uncertainty,
            rate_uncertainty=rate_uncertainty_ppm * 1e-6,
        )


@dataclass
class RandomWalkDrift(DriftModel):
    """Random walk (Brownian motion) drift model.

    Models clock drift as a random walk process:
        uncertainty(t) = uncertainty_0 + sigma * sqrt(t)

    This models the diffusion-like spreading of timing errors
    typical in free-running oscillators.

    Attributes:
        sigma: Random walk coefficient (seconds/sqrt(second))
        initial_uncertainty: Initial uncertainty

    Example:
        >>> # Typical quartz oscillator
        >>> drift = RandomWalkDrift(sigma=1e-9)  # 1 ns/sqrt(s)
        >>> drift.uncertainty_at(86400)  # After 1 day
        2.94e-7  # ~294 ns
    """

    sigma: float  # seconds / sqrt(second)
    initial_uncertainty: float = 0.0

    def uncertainty_at(self, elapsed: float) -> float:
        """Calculate uncertainty after elapsed time.

        Uncertainty grows with square root of time.
        """
        if elapsed < 0:
            return self.initial_uncertainty
        return self.initial_uncertainty + self.sigma * math.sqrt(elapsed)

    def offset_at(self, elapsed: float) -> float:
        """Random walk has zero expected offset."""
        return 0.0

    @classmethod
    def from_allan_deviation(
        cls,
        adev: float,
        tau: float = 1.0,
        initial_uncertainty: float = 0.0,
    ) -> RandomWalkDrift:
        """Create from Allan deviation at given averaging time.

        For random walk frequency noise, ADEV scales as 1/sqrt(tau).
        The random walk coefficient relates to ADEV by:
            sigma = adev * sqrt(tau) * tau

        Args:
            adev: Allan deviation at tau
            tau: Averaging time for ADEV measurement
            initial_uncertainty: Initial uncertainty

        Returns:
            RandomWalkDrift instance
        """
        # For random walk, sigma_y(tau) = sigma_rw / sqrt(tau)
        # Time error grows as sigma_rw * sqrt(t)
        sigma = adev * tau
        return cls(sigma=sigma, initial_uncertainty=initial_uncertainty)


@dataclass
class CombinedDrift(DriftModel):
    """Combined drift model with multiple components.

    Combines linear drift and random walk for realistic modeling:
        uncertainty(t) = sqrt(linear^2 + random_walk^2 + ...)

    Attributes:
        models: List of component drift models

    Example:
        >>> linear = LinearDrift(rate=1e-6, rate_uncertainty=0.1e-6)
        >>> rw = RandomWalkDrift(sigma=1e-9)
        >>> combined = CombinedDrift([linear, rw])
    """

    models: List[DriftModel]

    def uncertainty_at(self, elapsed: float) -> float:
        """Calculate combined uncertainty (root sum of squares)."""
        if not self.models:
            return 0.0

        sum_sq = sum(m.uncertainty_at(elapsed) ** 2 for m in self.models)
        return math.sqrt(sum_sq)

    def offset_at(self, elapsed: float) -> float:
        """Calculate combined offset (sum of components)."""
        return sum(m.offset_at(elapsed) for m in self.models)


@dataclass
class QuartzDrift(DriftModel):
    """Realistic quartz oscillator drift model.

    Models a typical quartz crystal oscillator with:
    - Initial frequency offset (aging)
    - Temperature-dependent drift
    - Random walk noise

    Based on typical TCXO/OCXO specifications.

    Attributes:
        aging_rate: Frequency aging rate (ppm/day)
        temp_coefficient: Temperature coefficient (ppm/°C)
        random_walk: Random walk coefficient
        initial_offset: Initial offset in seconds
        initial_uncertainty: Initial uncertainty

    Example:
        >>> # Typical TCXO
        >>> quartz = QuartzDrift.tcxo()
        >>> quartz.uncertainty_at(86400)  # 1 day holdover
    """

    aging_rate: float = 0.0  # ppm/day
    temp_coefficient: float = 0.0  # ppm/°C
    random_walk: float = 1e-11  # seconds/sqrt(second)
    initial_offset: float = 0.0
    initial_uncertainty: float = 1e-6  # 1 µs typical

    def uncertainty_at(self, elapsed: float) -> float:
        """Calculate uncertainty including all sources."""
        # Aging contribution (linear with time)
        aging_uncertainty = (self.aging_rate * 1e-6 / 86400) * elapsed

        # Random walk contribution
        rw_uncertainty = self.random_walk * math.sqrt(max(0, elapsed))

        # Temperature (assume ±5°C variation adds to uncertainty)
        temp_uncertainty = self.temp_coefficient * 1e-6 * 5.0 * elapsed

        # Combine as RSS
        combined = math.sqrt(
            self.initial_uncertainty ** 2 +
            aging_uncertainty ** 2 +
            rw_uncertainty ** 2 +
            temp_uncertainty ** 2
        )

        return combined

    def offset_at(self, elapsed: float) -> float:
        """Calculate expected offset due to aging."""
        # Aging causes linear frequency offset
        days = elapsed / 86400
        return self.initial_offset + (self.aging_rate * 1e-6 * days * elapsed)

    @classmethod
    def tcxo(cls) -> QuartzDrift:
        """Create model for typical TCXO.

        Temperature-compensated crystal oscillator.
        Stability: ±1-5 ppm over temperature range.
        """
        return cls(
            aging_rate=0.5,  # 0.5 ppm/day
            temp_coefficient=1.0,  # 1 ppm/°C
            random_walk=1e-11,
            initial_uncertainty=1e-6,
        )

    @classmethod
    def ocxo(cls) -> QuartzDrift:
        """Create model for typical OCXO.

        Oven-controlled crystal oscillator.
        Stability: ±0.01-0.1 ppm over temperature range.
        """
        return cls(
            aging_rate=0.05,  # 0.05 ppm/day
            temp_coefficient=0.01,  # 0.01 ppm/°C (oven controlled)
            random_walk=1e-12,
            initial_uncertainty=100e-9,  # 100 ns
        )

    @classmethod
    def simple_quartz(cls) -> QuartzDrift:
        """Create model for simple quartz oscillator.

        Basic crystal oscillator without compensation.
        Stability: ±20-100 ppm over temperature range.
        """
        return cls(
            aging_rate=5.0,  # 5 ppm/day
            temp_coefficient=20.0,  # 20 ppm/°C
            random_walk=1e-10,
            initial_uncertainty=10e-6,  # 10 µs
        )
