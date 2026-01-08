"""Reference Frames - Inertial frame management and transformations.

This module handles reference frames for relativistic calculations:
- Inertial frame definitions
- Frame relationships (relative velocities)
- Coordinate transformations between frames
- Frame registry for named frame management
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
import math

from timeos.physics.spacetime import FourVector, Event, SPEED_OF_LIGHT
from timeos.physics.lorentz import LorentzBoost, lorentz_factor


@dataclass
class InertialFrame:
    """An inertial (non-accelerating) reference frame.

    Each frame is defined by:
    - A unique identifier
    - Its velocity relative to a reference frame (usually "origin")
    - An optional origin offset

    Attributes:
        frame_id: Unique identifier for this frame
        velocity: 3-velocity (vx, vy, vz) relative to reference frame
        reference_frame: ID of the frame this is defined relative to
        origin_offset: 4-vector offset of this frame's origin
        description: Human-readable description

    Example:
        # Lab frame (stationary)
        lab = InertialFrame("lab", velocity=(0, 0, 0))

        # Rocket moving at 0.6c along x relative to lab
        rocket = InertialFrame(
            "rocket",
            velocity=(0.6, 0, 0),
            reference_frame="lab"
        )

        # Transform event from lab to rocket frame
        event_lab = Event.from_si(t=1.0, x=0.5, y=0, z=0, frame_id="lab")
        event_rocket = rocket.transform_from(event_lab, lab)
    """

    frame_id: str
    velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    reference_frame: str = "origin"
    origin_offset: FourVector = field(default_factory=FourVector)
    description: str = ""

    def __post_init__(self):
        """Validate and compute derived quantities."""
        vx, vy, vz = self.velocity
        self._speed_squared = vx**2 + vy**2 + vz**2
        self._speed = math.sqrt(self._speed_squared)

        if self._speed >= 1.0:
            raise ValueError(
                f"Frame velocity |v|={self._speed} must be < c=1"
            )

        self._gamma = lorentz_factor(self._speed) if self._speed > 0 else 1.0
        self._boost = LorentzBoost(vx=vx, vy=vy, vz=vz)

    @property
    def speed(self) -> float:
        """Speed relative to reference frame (as fraction of c)."""
        return self._speed

    @property
    def gamma(self) -> float:
        """Lorentz factor relative to reference frame."""
        return self._gamma

    @property
    def boost(self) -> LorentzBoost:
        """Lorentz boost from reference frame to this frame."""
        return self._boost

    def transform_to_reference(self, v: FourVector) -> FourVector:
        """Transform 4-vector from this frame to reference frame.

        Uses inverse boost (this frame → reference frame).
        """
        # First remove origin offset, then apply inverse boost
        shifted = v - self.origin_offset
        return self._boost.inverse().transform(shifted)

    def transform_from_reference(self, v: FourVector) -> FourVector:
        """Transform 4-vector from reference frame to this frame.

        Uses forward boost (reference frame → this frame).
        """
        # First apply boost, then add origin offset
        boosted = self._boost.transform(v)
        return boosted + self.origin_offset

    def transform_event_to_reference(self, event: Event) -> Event:
        """Transform an event from this frame to reference frame."""
        if event.frame_id != self.frame_id:
            raise ValueError(
                f"Event is in frame '{event.frame_id}', not '{self.frame_id}'"
            )
        return Event(
            position=self.transform_to_reference(event.position),
            event_id=event.event_id,
            frame_id=self.reference_frame,
        )

    def transform_event_from_reference(self, event: Event) -> Event:
        """Transform an event from reference frame to this frame."""
        if event.frame_id != self.reference_frame:
            raise ValueError(
                f"Event is in frame '{event.frame_id}', not '{self.reference_frame}'"
            )
        return Event(
            position=self.transform_from_reference(event.position),
            event_id=event.event_id,
            frame_id=self.frame_id,
        )

    def proper_time_for(self, coordinate_time: float) -> float:
        """Calculate proper time for this frame given coordinate time.

        For a clock moving with this frame, proper time is:
        τ = t / γ

        Args:
            coordinate_time: Time in reference frame

        Returns:
            Proper time experienced by clock in this frame
        """
        return coordinate_time / self._gamma

    def coordinate_time_for(self, proper_time: float) -> float:
        """Calculate coordinate time given proper time.

        t = γτ

        Args:
            proper_time: Proper time in this frame

        Returns:
            Coordinate time in reference frame
        """
        return proper_time * self._gamma

    def time_dilation_factor(self) -> float:
        """Get the time dilation factor (γ).

        Clocks in this frame appear to run slow by factor γ
        as seen from reference frame.
        """
        return self._gamma

    def length_contraction_factor(self) -> float:
        """Get the length contraction factor (1/γ).

        Objects in this frame appear contracted by factor 1/γ
        in direction of motion as seen from reference frame.
        """
        return 1.0 / self._gamma

    def velocity_relative_to(self, other: InertialFrame) -> Tuple[float, float, float]:
        """Calculate velocity of this frame relative to another.

        Uses relativistic velocity subtraction.

        Note: This only works correctly if both frames share the same
        reference frame. For more complex relationships, use FrameRegistry.
        """
        if self.reference_frame != other.reference_frame:
            raise ValueError(
                f"Frames have different references: "
                f"'{self.reference_frame}' vs '{other.reference_frame}'"
            )

        # Transform our velocity to other's frame
        vx, vy, vz = self.velocity
        return other._boost.transform_velocity(vx, vy, vz)

    def __repr__(self) -> str:
        v_str = f"({self.velocity[0]:.3g}, {self.velocity[1]:.3g}, {self.velocity[2]:.3g})"
        return f"InertialFrame('{self.frame_id}', v={v_str}, γ={self._gamma:.4g})"


class FrameRegistry:
    """Registry for managing multiple reference frames.

    Provides frame lookup and transformation chains between arbitrary frames.

    Example:
        registry = FrameRegistry()

        # Add frames
        registry.add(InertialFrame("earth", velocity=(0, 0, 0)))
        registry.add(InertialFrame("ship", velocity=(0.5, 0, 0), reference_frame="earth"))
        registry.add(InertialFrame("probe", velocity=(0.3, 0, 0), reference_frame="ship"))

        # Transform between any two frames
        event = Event.from_si(1.0, 0, 0, 0, frame_id="probe")
        event_earth = registry.transform(event, "earth")
    """

    def __init__(self):
        """Initialize empty frame registry."""
        self._frames: Dict[str, InertialFrame] = {}

        # Add default origin frame
        self._frames["origin"] = InertialFrame(
            "origin",
            velocity=(0, 0, 0),
            reference_frame="origin",  # Self-referential
            description="Absolute origin frame"
        )

    def add(self, frame: InertialFrame) -> None:
        """Add a frame to the registry.

        Args:
            frame: The frame to add

        Raises:
            ValueError: If frame ID already exists or reference frame not found
        """
        if frame.frame_id in self._frames:
            raise ValueError(f"Frame '{frame.frame_id}' already exists")

        if frame.reference_frame not in self._frames and frame.reference_frame != frame.frame_id:
            raise ValueError(
                f"Reference frame '{frame.reference_frame}' not found in registry"
            )

        self._frames[frame.frame_id] = frame

    def get(self, frame_id: str) -> Optional[InertialFrame]:
        """Get a frame by ID."""
        return self._frames.get(frame_id)

    def __getitem__(self, frame_id: str) -> InertialFrame:
        """Get a frame by ID (raises KeyError if not found)."""
        return self._frames[frame_id]

    def __contains__(self, frame_id: str) -> bool:
        """Check if frame exists."""
        return frame_id in self._frames

    def list_frames(self) -> list[str]:
        """List all frame IDs."""
        return list(self._frames.keys())

    def _find_path_to_origin(self, frame_id: str) -> list[str]:
        """Find chain of frames from given frame to origin."""
        path = [frame_id]
        current = frame_id

        while current != "origin":
            frame = self._frames.get(current)
            if frame is None:
                raise ValueError(f"Frame '{current}' not found")

            if frame.reference_frame == current:
                # Self-referential (like origin)
                break

            path.append(frame.reference_frame)
            current = frame.reference_frame

            # Detect cycles
            if len(path) > len(self._frames) + 1:
                raise ValueError(f"Cycle detected in frame chain: {path}")

        return path

    def transform(self, event: Event, target_frame_id: str) -> Event:
        """Transform an event to a different reference frame.

        Finds a path between frames through the reference chain
        and applies successive transformations.

        Args:
            event: Event to transform
            target_frame_id: ID of target frame

        Returns:
            Event in target frame coordinates
        """
        if event.frame_id == target_frame_id:
            return event

        if event.frame_id not in self._frames:
            raise ValueError(f"Source frame '{event.frame_id}' not in registry")
        if target_frame_id not in self._frames:
            raise ValueError(f"Target frame '{target_frame_id}' not in registry")

        # Find paths from both frames to origin
        source_path = self._find_path_to_origin(event.frame_id)
        target_path = self._find_path_to_origin(target_frame_id)

        # Find common ancestor
        source_set = set(source_path)
        common = None
        for frame_id in target_path:
            if frame_id in source_set:
                common = frame_id
                break

        if common is None:
            raise ValueError(
                f"No common reference between '{event.frame_id}' and '{target_frame_id}'"
            )

        # Transform up from source to common ancestor
        current_event = event
        for i, frame_id in enumerate(source_path):
            if frame_id == common:
                break
            frame = self._frames[frame_id]
            current_event = frame.transform_event_to_reference(current_event)

        # Transform down from common ancestor to target
        target_idx = target_path.index(common)
        for frame_id in reversed(target_path[:target_idx]):
            frame = self._frames[frame_id]
            current_event = frame.transform_event_from_reference(current_event)

        return current_event

    def relative_velocity(self, frame_a: str, frame_b: str) -> Tuple[float, float, float]:
        """Calculate velocity of frame_b as seen from frame_a.

        Uses transformation chain to compute relative velocity.
        """
        # Create a test 4-velocity at rest in frame_b
        origin_b = Event(
            position=FourVector(t=0, x=0, y=0, z=0),
            frame_id=frame_b
        )
        unit_time_b = Event(
            position=FourVector(t=1, x=0, y=0, z=0),
            frame_id=frame_b
        )

        # Transform to frame_a
        origin_a = self.transform(origin_b, frame_a)
        unit_time_a = self.transform(unit_time_b, frame_a)

        # Calculate displacement
        delta = unit_time_a.position - origin_a.position

        # Velocity = displacement / time
        if abs(delta.t) < 1e-15:
            return (0.0, 0.0, 0.0)

        return (delta.x / delta.t, delta.y / delta.t, delta.z / delta.t)

    def __repr__(self) -> str:
        return f"FrameRegistry({list(self._frames.keys())})"
