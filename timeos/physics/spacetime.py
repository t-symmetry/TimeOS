"""Spacetime - 4-vectors and Minkowski geometry.

This module implements the mathematical foundation for special relativity:
- 4-vectors (contravariant and covariant)
- Minkowski metric tensor
- Spacetime intervals
- Event representation

Convention: We use the (+,-,-,-) metric signature (timelike positive).
This means ds² = c²dt² - dx² - dy² - dz² > 0 for timelike intervals.

Natural units (c=1) are used internally, with conversion methods for SI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple

# Physical constants
SPEED_OF_LIGHT = 299_792_458.0  # m/s


class IntervalType(Enum):
    """Classification of spacetime intervals."""

    TIMELIKE = "timelike"      # ds² > 0, causally connected, Δt > Δx/c
    SPACELIKE = "spacelike"    # ds² < 0, causally disconnected, Δt < Δx/c
    LIGHTLIKE = "lightlike"    # ds² = 0, on light cone, Δt = Δx/c (null)


@dataclass
class FourVector:
    """A 4-vector in Minkowski spacetime.

    Represents contravariant 4-vectors x^μ = (ct, x, y, z) or (t, x, y, z)
    in natural units.

    Attributes:
        t: Time component (or ct in SI units)
        x: Spatial x component
        y: Spatial y component
        z: Spatial z component

    Example:
        # Position 4-vector
        pos = FourVector(t=1.0, x=0.5, y=0.0, z=0.0)

        # 4-velocity (always has magnitude c)
        v = FourVector(t=gamma, x=gamma*vx, y=0, z=0)

        # Compute interval
        interval = pos.squared_norm()  # ds²
    """

    t: float = 0.0  # Time component (natural units: t, SI: ct)
    x: float = 0.0  # Spatial x
    y: float = 0.0  # Spatial y
    z: float = 0.0  # Spatial z

    @classmethod
    def from_si(cls, t_seconds: float, x_meters: float,
                y_meters: float, z_meters: float) -> FourVector:
        """Create 4-vector from SI units.

        Converts to natural units where c=1.
        Time is converted: t_natural = c * t_seconds (in meters of time)
        """
        return cls(
            t=SPEED_OF_LIGHT * t_seconds,
            x=x_meters,
            y=y_meters,
            z=z_meters,
        )

    def to_si(self) -> Tuple[float, float, float, float]:
        """Convert to SI units (seconds, meters, meters, meters)."""
        return (self.t / SPEED_OF_LIGHT, self.x, self.y, self.z)

    @property
    def components(self) -> Tuple[float, float, float, float]:
        """Return components as tuple (t, x, y, z)."""
        return (self.t, self.x, self.y, self.z)

    @property
    def spatial(self) -> Tuple[float, float, float]:
        """Return spatial components (x, y, z)."""
        return (self.x, self.y, self.z)

    @property
    def spatial_magnitude(self) -> float:
        """Magnitude of spatial part: |r| = sqrt(x² + y² + z²)."""
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def squared_norm(self) -> float:
        """Compute Minkowski squared norm (interval).

        Using (+,-,-,-) signature:
        ||x||² = t² - x² - y² - z²

        Returns:
            Positive for timelike, negative for spacelike, zero for lightlike.
        """
        return self.t**2 - self.x**2 - self.y**2 - self.z**2

    def norm(self) -> float:
        """Compute Minkowski norm (proper time/length).

        For timelike vectors: sqrt(t² - x² - y² - z²) = proper time
        For spacelike vectors: sqrt(x² + y² + z² - t²) = proper length

        Returns:
            Proper time for timelike, proper length for spacelike.

        Raises:
            ValueError: For lightlike vectors (norm is zero).
        """
        s2 = self.squared_norm()
        if abs(s2) < 1e-15:
            return 0.0  # Lightlike
        elif s2 > 0:
            return math.sqrt(s2)  # Timelike - proper time
        else:
            return math.sqrt(-s2)  # Spacelike - proper length

    def interval_type(self, tolerance: float = 1e-10) -> IntervalType:
        """Classify this vector's interval type."""
        s2 = self.squared_norm()
        if abs(s2) < tolerance:
            return IntervalType.LIGHTLIKE
        elif s2 > 0:
            return IntervalType.TIMELIKE
        else:
            return IntervalType.SPACELIKE

    def dot(self, other: FourVector) -> float:
        """Minkowski inner product with another 4-vector.

        η_μν x^μ y^ν = t1*t2 - x1*x2 - y1*y2 - z1*z2
        """
        return (self.t * other.t -
                self.x * other.x -
                self.y * other.y -
                self.z * other.z)

    def __add__(self, other: FourVector) -> FourVector:
        """Vector addition."""
        return FourVector(
            t=self.t + other.t,
            x=self.x + other.x,
            y=self.y + other.y,
            z=self.z + other.z,
        )

    def __sub__(self, other: FourVector) -> FourVector:
        """Vector subtraction."""
        return FourVector(
            t=self.t - other.t,
            x=self.x - other.x,
            y=self.y - other.y,
            z=self.z - other.z,
        )

    def __mul__(self, scalar: float) -> FourVector:
        """Scalar multiplication."""
        return FourVector(
            t=self.t * scalar,
            x=self.x * scalar,
            y=self.y * scalar,
            z=self.z * scalar,
        )

    def __rmul__(self, scalar: float) -> FourVector:
        """Right scalar multiplication."""
        return self.__mul__(scalar)

    def __neg__(self) -> FourVector:
        """Negation."""
        return FourVector(t=-self.t, x=-self.x, y=-self.y, z=-self.z)

    def __eq__(self, other: object) -> bool:
        """Equality check."""
        if not isinstance(other, FourVector):
            return NotImplemented
        return (abs(self.t - other.t) < 1e-15 and
                abs(self.x - other.x) < 1e-15 and
                abs(self.y - other.y) < 1e-15 and
                abs(self.z - other.z) < 1e-15)

    def __repr__(self) -> str:
        return f"FourVector(t={self.t:.6g}, x={self.x:.6g}, y={self.y:.6g}, z={self.z:.6g})"


@dataclass
class Event:
    """A point in spacetime.

    Represents a specific location and time, optionally tagged with
    an identifier and reference frame.

    Attributes:
        position: 4-vector position in spacetime
        event_id: Optional identifier for this event
        frame_id: Reference frame this event is expressed in

    Example:
        # Event at origin
        origin = Event(FourVector(0, 0, 0, 0), event_id="origin")

        # Event 1 second later, 1 meter away
        later = Event(FourVector.from_si(1.0, 1.0, 0, 0), event_id="detection")

        # Compute interval between events
        interval = SpacetimeInterval.between(origin, later)
    """

    position: FourVector = field(default_factory=FourVector)
    event_id: str = ""
    frame_id: str = "origin"

    @classmethod
    def from_si(cls, t: float, x: float, y: float, z: float,
                event_id: str = "", frame_id: str = "origin") -> Event:
        """Create event from SI coordinates."""
        return cls(
            position=FourVector.from_si(t, x, y, z),
            event_id=event_id,
            frame_id=frame_id,
        )

    @property
    def t(self) -> float:
        """Time component."""
        return self.position.t

    @property
    def x(self) -> float:
        """Spatial x component."""
        return self.position.x

    @property
    def y(self) -> float:
        """Spatial y component."""
        return self.position.y

    @property
    def z(self) -> float:
        """Spatial z component."""
        return self.position.z

    def displacement_to(self, other: Event) -> FourVector:
        """4-vector displacement from this event to another."""
        return other.position - self.position

    def __repr__(self) -> str:
        id_str = f", id='{self.event_id}'" if self.event_id else ""
        return f"Event({self.position}{id_str})"


@dataclass
class SpacetimeInterval:
    """The invariant interval between two events.

    The spacetime interval ds² is invariant under Lorentz transformations.
    It determines the causal relationship between events.

    Attributes:
        squared: The squared interval ds²
        delta: The 4-vector displacement between events
        event_a: First event
        event_b: Second event

    Properties:
        interval_type: TIMELIKE, SPACELIKE, or LIGHTLIKE
        proper_time: For timelike intervals, the proper time (in natural units)
        proper_distance: For spacelike intervals, the proper distance
    """

    squared: float
    delta: FourVector
    event_a: Event
    event_b: Event

    @classmethod
    def between(cls, event_a: Event, event_b: Event) -> SpacetimeInterval:
        """Calculate the spacetime interval between two events."""
        delta = event_b.position - event_a.position
        return cls(
            squared=delta.squared_norm(),
            delta=delta,
            event_a=event_a,
            event_b=event_b,
        )

    @property
    def interval_type(self) -> IntervalType:
        """Classification of this interval."""
        return self.delta.interval_type()

    @property
    def proper_time(self) -> float:
        """Proper time for timelike intervals.

        τ = √(ds²) / c in SI units

        Returns:
            Proper time in natural units (divide by c for seconds).

        Raises:
            ValueError: If interval is not timelike.
        """
        if self.squared <= 0:
            if abs(self.squared) < 1e-15:
                return 0.0  # Lightlike
            raise ValueError(
                f"Proper time only defined for timelike intervals "
                f"(ds²={self.squared} is spacelike)"
            )
        return math.sqrt(self.squared)

    @property
    def proper_time_seconds(self) -> float:
        """Proper time in seconds (SI units)."""
        return self.proper_time / SPEED_OF_LIGHT

    @property
    def proper_distance(self) -> float:
        """Proper distance for spacelike intervals.

        Returns:
            Proper distance in meters.

        Raises:
            ValueError: If interval is not spacelike.
        """
        if self.squared >= 0:
            if abs(self.squared) < 1e-15:
                return 0.0  # Lightlike
            raise ValueError(
                f"Proper distance only defined for spacelike intervals "
                f"(ds²={self.squared} is timelike)"
            )
        return math.sqrt(-self.squared)

    @property
    def coordinate_time(self) -> float:
        """Coordinate time difference Δt."""
        return self.delta.t

    @property
    def coordinate_distance(self) -> float:
        """Coordinate spatial distance |Δr|."""
        return self.delta.spatial_magnitude

    def is_causally_connected(self) -> bool:
        """Check if the two events can be causally connected.

        Events are causally connected if their interval is timelike or lightlike
        (i.e., a signal traveling at or below c can connect them).
        """
        return self.squared >= 0

    def time_order_preserved(self) -> bool:
        """Check if time ordering is absolute (frame-independent).

        For timelike intervals, the time ordering is preserved in all frames.
        For spacelike intervals, different frames may disagree on ordering.
        """
        return self.squared > 0

    def __repr__(self) -> str:
        return (f"SpacetimeInterval(ds²={self.squared:.6g}, "
                f"type={self.interval_type.value})")


def minkowski_metric() -> list[list[float]]:
    """Return the Minkowski metric tensor η_μν.

    Using (+,-,-,-) signature:
    η = diag(1, -1, -1, -1)
    """
    return [
        [1.0,  0.0,  0.0,  0.0],
        [0.0, -1.0,  0.0,  0.0],
        [0.0,  0.0, -1.0,  0.0],
        [0.0,  0.0,  0.0, -1.0],
    ]


def raise_index(v: FourVector) -> FourVector:
    """Raise the index of a covariant 4-vector (v_μ → v^μ).

    With (+,-,-,-) signature:
    v^0 = v_0, v^i = -v_i
    """
    return FourVector(t=v.t, x=-v.x, y=-v.y, z=-v.z)


def lower_index(v: FourVector) -> FourVector:
    """Lower the index of a contravariant 4-vector (v^μ → v_μ).

    With (+,-,-,-) signature:
    v_0 = v^0, v_i = -v^i
    """
    return FourVector(t=v.t, x=-v.x, y=-v.y, z=-v.z)
