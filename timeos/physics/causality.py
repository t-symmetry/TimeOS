"""Causality - Light cones and causal structure of spacetime.

This module implements causal analysis for special relativity:
- Light cone visualization and classification
- Causal relationships between events
- Causality violation detection
- Closed timelike curve analysis

The causal structure is determined by the light cone:
- Events inside the future light cone can be influenced (effects)
- Events inside the past light cone can influence (causes)
- Events outside the light cone are causally disconnected
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from timeos.physics.spacetime import (
    FourVector,
    Event,
    SpacetimeInterval,
    IntervalType,
    SPEED_OF_LIGHT,
)


class CausalRelation(Enum):
    """Causal relationship between two events."""

    # A is in the causal past of B (A can cause B)
    PAST = "past"

    # A is in the causal future of B (A can be caused by B)
    FUTURE = "future"

    # A and B are on each other's light cone (lightlike separated)
    LIGHTLIKE = "lightlike"

    # A and B are spacelike separated (no causal connection possible)
    SPACELIKE = "spacelike"

    # A and B are the same event
    SAME = "same"


@dataclass
class LightCone:
    """The light cone of an event.

    The light cone divides spacetime into causally distinct regions:
    - Future light cone: events that can be reached by light from this event
    - Past light cone: events from which light can reach this event
    - Interior (timelike): causally connected events
    - Exterior (spacelike): causally disconnected events

    Attributes:
        apex: The event at the apex of the light cone
    """

    apex: Event

    def contains(self, event: Event) -> CausalRelation:
        """Determine the causal relationship of another event.

        Args:
            event: Event to classify

        Returns:
            CausalRelation indicating how event relates to this light cone
        """
        interval = SpacetimeInterval.between(self.apex, event)

        # Check for same event
        delta = interval.delta
        if (abs(delta.t) < 1e-15 and abs(delta.x) < 1e-15 and
            abs(delta.y) < 1e-15 and abs(delta.z) < 1e-15):
            return CausalRelation.SAME

        interval_type = interval.interval_type

        if interval_type == IntervalType.SPACELIKE:
            return CausalRelation.SPACELIKE
        elif interval_type == IntervalType.LIGHTLIKE:
            return CausalRelation.LIGHTLIKE
        else:  # Timelike
            # Determine if future or past based on time ordering
            if delta.t > 0:
                return CausalRelation.FUTURE
            else:
                return CausalRelation.PAST

    def is_in_future(self, event: Event) -> bool:
        """Check if event is in the future light cone (can be affected)."""
        relation = self.contains(event)
        return relation in (CausalRelation.FUTURE, CausalRelation.LIGHTLIKE)

    def is_in_past(self, event: Event) -> bool:
        """Check if event is in the past light cone (can affect apex)."""
        relation = self.contains(event)
        return relation in (CausalRelation.PAST, CausalRelation.LIGHTLIKE)

    def is_causally_connected(self, event: Event) -> bool:
        """Check if event is causally connected (timelike or lightlike)."""
        relation = self.contains(event)
        return relation != CausalRelation.SPACELIKE

    def distance_to_cone(self, event: Event) -> float:
        """Calculate the 'distance' from event to the light cone surface.

        Returns:
            Positive if outside cone (spacelike separation)
            Zero if on the cone
            Negative if inside cone (timelike separation)
        """
        interval = SpacetimeInterval.between(self.apex, event)
        return -interval.squared  # Negative of ds² so spacelike is positive

    def cone_radius_at_time(self, t: float) -> float:
        """Calculate the spatial radius of the light cone at a given time.

        The light cone expands at the speed of light, so at time t
        from the apex, the radius is |t-t_apex| * c.

        Args:
            t: Time coordinate (in natural units where c=1)

        Returns:
            Radius of light cone at that time
        """
        return abs(t - self.apex.t)

    def project_future_cone(self, num_points: int = 36) -> List[Tuple[float, float, float, float]]:
        """Generate points on the future light cone surface.

        Useful for visualization. Returns points at t = apex.t + 1.

        Args:
            num_points: Number of points around the cone

        Returns:
            List of (t, x, y, z) points on the cone surface
        """
        points = []
        t = self.apex.t + 1.0
        radius = 1.0  # Cone radius at t = apex.t + 1

        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            x = self.apex.x + radius * math.cos(angle)
            y = self.apex.y + radius * math.sin(angle)
            z = self.apex.z
            points.append((t, x, y, z))

        return points


def is_causally_connected(event_a: Event, event_b: Event) -> bool:
    """Check if two events are causally connected.

    Events are causally connected if a signal traveling at or below
    the speed of light could connect them.

    Args:
        event_a: First event
        event_b: Second event

    Returns:
        True if events are timelike or lightlike separated
    """
    interval = SpacetimeInterval.between(event_a, event_b)
    return interval.squared >= 0


def causal_order(event_a: Event, event_b: Event) -> Optional[int]:
    """Determine the causal ordering of two events.

    For timelike-separated events, the ordering is absolute
    (the same in all reference frames).

    Args:
        event_a: First event
        event_b: Second event

    Returns:
        -1 if A is before B (A can cause B)
         1 if A is after B (B can cause A)
         0 if A and B are the same event
        None if events are spacelike separated (no absolute ordering)
    """
    interval = SpacetimeInterval.between(event_a, event_b)

    # Check for same event
    if abs(interval.squared) < 1e-15 and interval.delta.spatial_magnitude < 1e-15:
        return 0

    if interval.squared <= 0:
        # Spacelike - no absolute ordering
        return None

    # Timelike - ordering is determined by time coordinate
    if interval.delta.t > 0:
        return -1  # A is before B
    else:
        return 1  # A is after B


def check_causality_violation(events: List[Event]) -> List[Tuple[Event, Event, str]]:
    """Check a list of events for causality violations.

    A causality violation occurs when:
    - An event claims to be caused by a future event
    - A causal chain forms a closed loop

    This function checks for simple violations based on
    parent-child relationships implied by event ordering.

    Args:
        events: List of events, assumed ordered by their timestamps

    Returns:
        List of (event_a, event_b, reason) tuples describing violations
    """
    violations = []

    for i, event_a in enumerate(events):
        for j, event_b in enumerate(events[i+1:], start=i+1):
            interval = SpacetimeInterval.between(event_a, event_b)

            # If events are timelike separated but time-ordered backwards
            # (later indexed event is in the past), that's suspicious
            if interval.squared > 0 and interval.delta.t < 0:
                violations.append((
                    event_a, event_b,
                    f"Event {j} is timelike-past of event {i} but indexed later"
                ))

    return violations


@dataclass
class WorldLine:
    """A timelike worldline through spacetime.

    Represents the path of a massive object through spacetime.
    Must be timelike (always inside the light cone).

    Attributes:
        events: Ordered list of events along the worldline
    """

    events: List[Event]

    def __post_init__(self):
        """Validate that worldline is timelike."""
        for i in range(len(self.events) - 1):
            interval = SpacetimeInterval.between(self.events[i], self.events[i+1])
            if interval.squared < 0:
                raise ValueError(
                    f"Worldline segment {i} → {i+1} is spacelike "
                    f"(ds²={interval.squared})"
                )
            if interval.delta.t < 0:
                raise ValueError(
                    f"Worldline segment {i} → {i+1} goes backward in time"
                )

    @property
    def proper_time(self) -> float:
        """Calculate total proper time along the worldline.

        This is the time experienced by an observer following
        this path through spacetime.
        """
        total = 0.0
        for i in range(len(self.events) - 1):
            interval = SpacetimeInterval.between(self.events[i], self.events[i+1])
            if interval.squared > 0:
                total += math.sqrt(interval.squared)
        return total

    @property
    def coordinate_time(self) -> float:
        """Total coordinate time from first to last event."""
        if len(self.events) < 2:
            return 0.0
        return self.events[-1].t - self.events[0].t

    @property
    def time_dilation_ratio(self) -> float:
        """Ratio of proper time to coordinate time.

        Always ≤ 1 for valid worldlines (proper time is maximized
        for inertial paths).
        """
        coord_time = self.coordinate_time
        if coord_time < 1e-15:
            return 1.0
        return self.proper_time / coord_time

    def is_inertial(self, tolerance: float = 1e-10) -> bool:
        """Check if worldline represents inertial (unaccelerated) motion.

        An inertial worldline is a straight line in spacetime,
        which maximizes proper time between endpoints.
        """
        if len(self.events) < 3:
            return True  # Can't tell with only 2 points

        # For inertial motion, proper time equals the interval between endpoints
        direct_interval = SpacetimeInterval.between(self.events[0], self.events[-1])
        if direct_interval.squared <= 0:
            return False

        direct_proper = math.sqrt(direct_interval.squared)
        return abs(self.proper_time - direct_proper) < tolerance


def closed_timelike_curve_check(events: List[Event]) -> bool:
    """Check if events could form a closed timelike curve (CTC).

    A CTC exists if there's a path through timelike-connected events
    that returns to its starting point.

    This is a simplified check - true CTC detection requires
    analysis of the spacetime geometry itself.

    Args:
        events: List of events to check

    Returns:
        True if a potential CTC is detected
    """
    if len(events) < 2:
        return False

    # Build graph of timelike connections
    n = len(events)
    can_reach = [[False] * n for _ in range(n)]

    # Direct connections
    for i in range(n):
        for j in range(n):
            if i != j:
                interval = SpacetimeInterval.between(events[i], events[j])
                if interval.squared > 0 and interval.delta.t > 0:
                    can_reach[i][j] = True

    # Transitive closure (Floyd-Warshall)
    for k in range(n):
        for i in range(n):
            for j in range(n):
                if can_reach[i][k] and can_reach[k][j]:
                    can_reach[i][j] = True

    # Check for cycles
    for i in range(n):
        if can_reach[i][i]:
            return True

    return False
