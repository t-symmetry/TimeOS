"""Lorentz Transformations - Coordinate transformations between inertial frames.

This module implements Lorentz transformations for special relativity:
- Lorentz factor (gamma)
- Boosts along arbitrary directions
- Time dilation and length contraction
- Relativistic velocity addition

Convention: Velocity v is the velocity of frame S' relative to S.
A boost transforms coordinates from S to S'.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from timeos.physics.spacetime import FourVector, SPEED_OF_LIGHT


def lorentz_factor(v: float, c: float = 1.0) -> float:
    """Calculate the Lorentz factor γ.

    γ = 1 / √(1 - v²/c²)

    Args:
        v: Relative velocity (same units as c)
        c: Speed of light (default 1.0 for natural units)

    Returns:
        Lorentz factor γ ≥ 1

    Raises:
        ValueError: If |v| ≥ c (superluminal velocity)

    Example:
        >>> lorentz_factor(0.0)
        1.0
        >>> lorentz_factor(0.6)  # 60% speed of light
        1.25
        >>> lorentz_factor(0.99)  # 99% speed of light
        7.088...
    """
    beta = v / c
    if abs(beta) >= 1.0:
        raise ValueError(
            f"Velocity |v|={abs(v)} must be less than c={c} "
            f"(β={abs(beta)} ≥ 1)"
        )
    return 1.0 / math.sqrt(1.0 - beta * beta)


def beta_from_gamma(gamma: float) -> float:
    """Calculate β = v/c from Lorentz factor γ.

    β = √(1 - 1/γ²)

    Args:
        gamma: Lorentz factor (must be ≥ 1)

    Returns:
        β = v/c in range [0, 1)
    """
    if gamma < 1.0:
        raise ValueError(f"Lorentz factor γ={gamma} must be ≥ 1")
    if gamma == 1.0:
        return 0.0
    return math.sqrt(1.0 - 1.0 / (gamma * gamma))


def time_dilation(proper_time: float, gamma: float) -> float:
    """Calculate dilated time in moving frame.

    Δt = γ Δτ

    An observer moving relative to a clock sees it tick slower.

    Args:
        proper_time: Time measured in rest frame of clock (Δτ)
        gamma: Lorentz factor of relative motion

    Returns:
        Dilated time as measured by moving observer (Δt)

    Example:
        A clock moving at 0.6c (γ=1.25) shows 1 second has passed.
        A stationary observer measures 1.25 seconds.
        >>> time_dilation(1.0, lorentz_factor(0.6))
        1.25
    """
    return gamma * proper_time


def length_contraction(proper_length: float, gamma: float) -> float:
    """Calculate contracted length in moving frame.

    L = L₀ / γ

    An observer moving relative to an object sees it shorter
    in the direction of motion.

    Args:
        proper_length: Length in rest frame of object (L₀)
        gamma: Lorentz factor of relative motion

    Returns:
        Contracted length as measured by moving observer (L)

    Example:
        A rod 1 meter long at rest, moving at 0.6c (γ=1.25):
        >>> length_contraction(1.0, lorentz_factor(0.6))
        0.8
    """
    return proper_length / gamma


def velocity_addition(u: float, v: float, c: float = 1.0) -> float:
    """Relativistic velocity addition.

    If object has velocity u in frame S', and S' moves at v relative to S,
    the velocity u' in frame S is:

    u' = (u + v) / (1 + uv/c²)

    Args:
        u: Velocity in frame S'
        v: Velocity of S' relative to S
        c: Speed of light (default 1.0 for natural units)

    Returns:
        Velocity in frame S

    Example:
        Object at 0.5c in a ship moving at 0.5c:
        >>> velocity_addition(0.5, 0.5)  # Not 1.0!
        0.8
    """
    return (u + v) / (1.0 + u * v / (c * c))


@dataclass
class LorentzBoost:
    """A Lorentz boost transformation.

    Represents a boost from frame S to frame S' moving with velocity v
    along a specified direction.

    Attributes:
        velocity: 3-velocity (vx, vy, vz) of S' relative to S
        gamma: Lorentz factor
        beta: v/c for each component

    Example:
        # Boost along x-axis at 0.6c
        boost = LorentzBoost.along_x(0.6)

        # Transform a 4-vector
        x = FourVector(t=1.0, x=0.0, y=0.0, z=0.0)
        x_prime = boost.transform(x)

        # Inverse boost (S' back to S)
        x_back = boost.inverse().transform(x_prime)
    """

    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0

    def __post_init__(self):
        """Calculate derived quantities."""
        self._v_squared = self.vx**2 + self.vy**2 + self.vz**2
        self._v = math.sqrt(self._v_squared)

        if self._v >= 1.0:
            raise ValueError(
                f"Boost velocity |v|={self._v} must be less than c=1"
            )

        self._gamma = 1.0 / math.sqrt(1.0 - self._v_squared) if self._v > 0 else 1.0
        self._beta_x = self.vx
        self._beta_y = self.vy
        self._beta_z = self.vz

    @classmethod
    def along_x(cls, v: float) -> LorentzBoost:
        """Create boost along x-axis."""
        return cls(vx=v, vy=0.0, vz=0.0)

    @classmethod
    def along_y(cls, v: float) -> LorentzBoost:
        """Create boost along y-axis."""
        return cls(vx=0.0, vy=v, vz=0.0)

    @classmethod
    def along_z(cls, v: float) -> LorentzBoost:
        """Create boost along z-axis."""
        return cls(vx=0.0, vy=0.0, vz=v)

    @classmethod
    def from_velocity(cls, vx: float, vy: float, vz: float) -> LorentzBoost:
        """Create boost from velocity components."""
        return cls(vx=vx, vy=vy, vz=vz)

    @property
    def gamma(self) -> float:
        """Lorentz factor."""
        return self._gamma

    @property
    def beta(self) -> float:
        """Speed as fraction of c."""
        return self._v

    @property
    def velocity(self) -> Tuple[float, float, float]:
        """Velocity components."""
        return (self.vx, self.vy, self.vz)

    def transform(self, v: FourVector) -> FourVector:
        """Apply Lorentz boost to a 4-vector.

        Transforms from frame S to frame S'.

        For boost along arbitrary direction with velocity (vx, vy, vz):
        t' = γ(t - v⃗·r⃗/c²)
        r⃗' = r⃗ + (γ-1)(r⃗·v̂)v̂ - γv⃗t

        Args:
            v: 4-vector in frame S

        Returns:
            Transformed 4-vector in frame S'
        """
        if self._v < 1e-15:
            # No boost needed
            return FourVector(t=v.t, x=v.x, y=v.y, z=v.z)

        # For general boost:
        gamma = self._gamma
        beta_sq = self._v_squared

        # v⃗ · r⃗
        v_dot_r = self.vx * v.x + self.vy * v.y + self.vz * v.z

        # Time component: t' = γ(t - v⃗·r⃗)
        t_prime = gamma * (v.t - v_dot_r)

        # Spatial components
        # r⃗' = r⃗ + (γ-1)(r⃗·v̂)v̂/|v|² - γv⃗t
        # Simplify: r⃗' = r⃗ + [(γ-1)/β²](v⃗·r⃗)v⃗ - γv⃗t

        if beta_sq > 1e-15:
            factor = (gamma - 1.0) / beta_sq
        else:
            factor = 0.0

        x_prime = v.x + factor * v_dot_r * self.vx - gamma * self.vx * v.t
        y_prime = v.y + factor * v_dot_r * self.vy - gamma * self.vy * v.t
        z_prime = v.z + factor * v_dot_r * self.vz - gamma * self.vz * v.t

        return FourVector(t=t_prime, x=x_prime, y=y_prime, z=z_prime)

    def inverse(self) -> LorentzBoost:
        """Return the inverse boost (from S' back to S).

        The inverse of a boost with velocity v is a boost with velocity -v.
        """
        return LorentzBoost(vx=-self.vx, vy=-self.vy, vz=-self.vz)

    def transform_velocity(self, ux: float, uy: float, uz: float) -> Tuple[float, float, float]:
        """Transform a 3-velocity from S to S'.

        Uses relativistic velocity transformation.

        Args:
            ux, uy, uz: Velocity components in frame S

        Returns:
            Velocity components (ux', uy', uz') in frame S'
        """
        gamma = self._gamma

        # u⃗ · v⃗
        u_dot_v = ux * self.vx + uy * self.vy + uz * self.vz

        # Denominator: 1 - u⃗·v⃗
        denom = 1.0 - u_dot_v

        if abs(denom) < 1e-15:
            raise ValueError("Velocity transformation undefined (denom ≈ 0)")

        # Parallel and perpendicular decomposition
        # For general case:
        # u'_∥ = (u_∥ - v) / (1 - u⃗·v⃗)
        # u'_⊥ = u_⊥ / (γ(1 - u⃗·v⃗))

        # Full formula:
        # u⃗' = [u⃗/γ + v⃗((γ-1)(u⃗·v⃗)/v² - 1)] / (1 - u⃗·v⃗)

        if self._v_squared > 1e-15:
            factor = (gamma - 1.0) * u_dot_v / self._v_squared - gamma
        else:
            factor = -gamma

        ux_prime = (ux / gamma + factor * self.vx) / denom
        uy_prime = (uy / gamma + factor * self.vy) / denom
        uz_prime = (uz / gamma + factor * self.vz) / denom

        return (ux_prime, uy_prime, uz_prime)

    def __repr__(self) -> str:
        return (f"LorentzBoost(v=({self.vx:.4g}, {self.vy:.4g}, {self.vz:.4g}), "
                f"γ={self._gamma:.4g})")


class FourVelocity(FourVector):
    """4-velocity of a massive particle.

    The 4-velocity u^μ = γ(c, v⃗) always has magnitude c (or 1 in natural units).
    u·u = c² (or 1)

    In natural units: u^μ = (γ, γvx, γvy, γvz)
    """

    @classmethod
    def from_3velocity(cls, vx: float, vy: float, vz: float) -> FourVelocity:
        """Create 4-velocity from 3-velocity components.

        Args:
            vx, vy, vz: 3-velocity components (in units of c)

        Returns:
            4-velocity with proper normalization
        """
        v_squared = vx**2 + vy**2 + vz**2
        if v_squared >= 1.0:
            raise ValueError(f"3-velocity magnitude {math.sqrt(v_squared)} must be < c")

        gamma = 1.0 / math.sqrt(1.0 - v_squared)

        return cls(
            t=gamma,
            x=gamma * vx,
            y=gamma * vy,
            z=gamma * vz,
        )

    @classmethod
    def at_rest(cls) -> FourVelocity:
        """4-velocity of an object at rest."""
        return cls(t=1.0, x=0.0, y=0.0, z=0.0)

    @property
    def gamma(self) -> float:
        """Lorentz factor (time component of 4-velocity)."""
        return self.t

    @property
    def three_velocity(self) -> Tuple[float, float, float]:
        """Extract 3-velocity from 4-velocity."""
        if self.t < 1e-15:
            return (0.0, 0.0, 0.0)
        return (self.x / self.t, self.y / self.t, self.z / self.t)

    @property
    def speed(self) -> float:
        """Speed |v| as fraction of c."""
        vx, vy, vz = self.three_velocity
        return math.sqrt(vx**2 + vy**2 + vz**2)


class FourMomentum(FourVector):
    """4-momentum of a particle.

    p^μ = (E/c, px, py, pz) in SI, or (E, px, py, pz) in natural units.

    The invariant mass satisfies: m²c⁴ = E² - |p⃗|²c²
    Or in natural units: m² = E² - |p⃗|²
    """

    @classmethod
    def from_mass_velocity(cls, mass: float, vx: float, vy: float, vz: float) -> FourMomentum:
        """Create 4-momentum from mass and 3-velocity.

        Args:
            mass: Rest mass (invariant mass)
            vx, vy, vz: 3-velocity components (in units of c)

        Returns:
            4-momentum p^μ = (γm, γmvx, γmvy, γmvz)
        """
        v_squared = vx**2 + vy**2 + vz**2
        if v_squared >= 1.0:
            raise ValueError(f"3-velocity magnitude {math.sqrt(v_squared)} must be < c")

        gamma = 1.0 / math.sqrt(1.0 - v_squared)

        return cls(
            t=gamma * mass,  # E = γm (in natural units)
            x=gamma * mass * vx,
            y=gamma * mass * vy,
            z=gamma * mass * vz,
        )

    @classmethod
    def from_energy_momentum(cls, energy: float, px: float, py: float, pz: float) -> FourMomentum:
        """Create 4-momentum from energy and 3-momentum."""
        return cls(t=energy, x=px, y=py, z=pz)

    @classmethod
    def photon(cls, energy: float, nx: float, ny: float, nz: float) -> FourMomentum:
        """Create 4-momentum for a photon.

        Photons have m=0, so E = |p⃗|c, or E = |p⃗| in natural units.

        Args:
            energy: Photon energy
            nx, ny, nz: Direction unit vector components

        Returns:
            4-momentum with |p⃗| = E
        """
        # Normalize direction
        n_mag = math.sqrt(nx**2 + ny**2 + nz**2)
        if n_mag < 1e-15:
            raise ValueError("Direction vector cannot be zero")

        nx, ny, nz = nx / n_mag, ny / n_mag, nz / n_mag

        return cls(
            t=energy,
            x=energy * nx,
            y=energy * ny,
            z=energy * nz,
        )

    @property
    def energy(self) -> float:
        """Energy component E."""
        return self.t

    @property
    def momentum_3(self) -> Tuple[float, float, float]:
        """3-momentum components."""
        return (self.x, self.y, self.z)

    @property
    def momentum_magnitude(self) -> float:
        """Magnitude of 3-momentum |p⃗|."""
        return self.spatial_magnitude

    @property
    def invariant_mass(self) -> float:
        """Invariant (rest) mass.

        m² = E² - |p⃗|²  (natural units)
        """
        m_squared = self.t**2 - self.x**2 - self.y**2 - self.z**2
        if m_squared < 0:
            if m_squared > -1e-15:
                return 0.0  # Massless (photon)
            raise ValueError(f"Tachyonic 4-momentum (m²={m_squared} < 0)")
        return math.sqrt(m_squared)

    @property
    def is_massless(self) -> bool:
        """Check if this represents a massless particle."""
        return abs(self.squared_norm()) < 1e-15
