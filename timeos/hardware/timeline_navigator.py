"""Timeline Navigator - Temporal destination calculation and path planning.

This module handles the calculation of temporal displacement paths,
taking into account physical constraints, energy requirements,
and causality considerations.

Navigation concepts:
- Temporal distance: "how far" in time
- Timeline topology: structure of possible paths
- Branching points: where timelines diverge
- Convergence points: where timelines merge
- Forbidden zones: areas of high paradox risk

The navigator doesn't perform displacement; it calculates
where displacement is possible and plots safe paths.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from timeos.hardware.base import HardwareModule, ModuleStatus, ModuleDiagnostics
from timeos.msgs import ChronoStamp, TemporalFrame


class PathType(Enum):
    """Type of navigation path."""

    DIRECT = "direct"  # Straight temporal displacement
    BRANCHING = "branching"  # Path that creates new branch
    CONVERGENT = "convergent"  # Path that merges with existing
    CIRCUMVENT = "circumvent"  # Path avoiding obstacles
    MULTI_HOP = "multi_hop"  # Multiple sequential displacements


class PathRisk(Enum):
    """Risk level of a navigation path."""

    MINIMAL = "minimal"  # Standard operation parameters
    LOW = "low"  # Minor concerns, proceed with caution
    MODERATE = "moderate"  # Significant concerns
    HIGH = "high"  # Major concerns, reconsider
    EXTREME = "extreme"  # Not recommended
    FORBIDDEN = "forbidden"  # Should not be attempted


@dataclass
class NavigationTarget:
    """Specification of a navigation target.

    Attributes:
        target_stamp: Desired destination time
        target_frame: Reference frame for destination
        tolerance_seconds: Acceptable deviation from target
        prefer_branch: Prefer creating new branch over modifying existing
        avoid_events: Event IDs to avoid affecting
        required_events: Events that must still exist after navigation
    """

    target_stamp: ChronoStamp
    target_frame: TemporalFrame
    tolerance_seconds: float = 1.0
    prefer_branch: bool = True
    avoid_events: list[str] = field(default_factory=list)
    required_events: list[str] = field(default_factory=list)

    @property
    def target_time(self) -> float:
        return self.target_stamp.t


@dataclass
class NavigationWaypoint:
    """A waypoint along a navigation path."""

    stamp: ChronoStamp
    frame: TemporalFrame
    waypoint_type: str = "transit"  # "transit", "rest", "calibration"
    min_duration_seconds: float = 0.0
    notes: str = ""


@dataclass
class NavigationPath:
    """A calculated path through time.

    Attributes:
        path_id: Unique identifier for this path
        origin: Starting point
        destination: End point
        path_type: Type of path
        risk_level: Overall risk assessment
        waypoints: Intermediate points (if multi-hop)
        total_displacement: Total temporal displacement
        estimated_energy_joules: Energy required
        estimated_duration_seconds: Real-time duration
        paradox_probability: Estimated paradox risk
        affected_events: Events that may be affected
        notes: Additional information
    """

    path_id: str
    origin: ChronoStamp
    destination: ChronoStamp
    path_type: PathType = PathType.DIRECT
    risk_level: PathRisk = PathRisk.MODERATE
    waypoints: list[NavigationWaypoint] = field(default_factory=list)
    total_displacement: float = 0.0
    estimated_energy_joules: float = 0.0
    estimated_duration_seconds: float = 0.0
    paradox_probability: float = 0.0
    affected_events: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def is_safe(self) -> bool:
        """Check if path is considered safe."""
        return self.risk_level in (PathRisk.MINIMAL, PathRisk.LOW)

    @property
    def hop_count(self) -> int:
        """Number of displacement hops."""
        return len(self.waypoints) + 1


@dataclass
class TimelineMap:
    """Map of timeline structure.

    Attributes:
        branches: Known timeline branches
        branch_points: Where branches diverge
        merge_points: Where branches converge
        forbidden_zones: High-risk temporal regions
        anchor_points: Known stable reference points
    """

    branches: list[str] = field(default_factory=list)
    branch_points: dict[str, float] = field(default_factory=dict)  # branch_id -> time
    merge_points: dict[str, tuple[str, str]] = field(default_factory=dict)  # id -> (from, to)
    forbidden_zones: list[tuple[float, float]] = field(default_factory=list)  # (start, end)
    anchor_points: list[ChronoStamp] = field(default_factory=list)


class TimelineNavigator(HardwareModule):
    """Abstract interface for temporal navigation.

    The navigator calculates safe paths through time,
    considering physical constraints and causality.

    Features:
    - Path planning with multiple strategies
    - Risk assessment for proposed paths
    - Timeline topology mapping
    - Obstacle avoidance (events, paradoxes)
    - Multi-hop path optimization

    The navigator integrates with:
    - CausalityMonitor for paradox risk assessment
    - EventLog for timeline structure
    - TemporalDisplacementUnit for feasibility checks
    """

    def __init__(self, module_id: str = "navigator"):
        super().__init__(module_id)
        self._current_position: ChronoStamp | None = None
        self._timeline_map: TimelineMap | None = None
        self._cached_paths: dict[str, NavigationPath] = {}

    @property
    def current_position(self) -> ChronoStamp | None:
        """Current temporal position."""
        return self._current_position

    @abstractmethod
    def set_current_position(self, stamp: ChronoStamp) -> None:
        """Set current temporal position.

        Args:
            stamp: Current position in spacetime.
        """
        pass

    @abstractmethod
    def calculate_path(
        self,
        target: NavigationTarget,
        max_alternatives: int = 3,
    ) -> list[NavigationPath]:
        """Calculate paths to a target.

        Args:
            target: Navigation target specification.
            max_alternatives: Maximum number of alternative paths.

        Returns:
            List of possible paths, ranked by preference.
        """
        pass

    @abstractmethod
    def assess_risk(self, path: NavigationPath) -> tuple[PathRisk, list[str]]:
        """Assess risk of a navigation path.

        Args:
            path: Path to assess.

        Returns:
            Tuple of (risk_level, list of concerns).
        """
        pass

    @abstractmethod
    def find_safe_window(
        self,
        target_time: float,
        frame: TemporalFrame,
        window_size: float = 3600.0,
    ) -> list[tuple[float, float]]:
        """Find safe arrival windows near a target time.

        Args:
            target_time: Desired time.
            frame: Reference frame.
            window_size: Size of search window in seconds.

        Returns:
            List of (start, end) tuples for safe windows.
        """
        pass

    @abstractmethod
    def map_timeline(self, depth: int = 100) -> TimelineMap:
        """Map the timeline structure.

        Args:
            depth: How many events to analyze.

        Returns:
            Map of timeline structure.
        """
        pass

    @abstractmethod
    def get_forbidden_zones(self) -> list[tuple[float, float, str]]:
        """Get list of forbidden temporal zones.

        Returns:
            List of (start, end, reason) tuples.
        """
        pass

    @abstractmethod
    def estimate_energy(
        self, origin: ChronoStamp, destination: ChronoStamp
    ) -> float:
        """Estimate energy required for displacement.

        Args:
            origin: Starting point.
            destination: End point.

        Returns:
            Estimated energy in Joules.
        """
        pass

    def find_nearest_anchor(self, stamp: ChronoStamp) -> ChronoStamp | None:
        """Find nearest stable anchor point.

        Args:
            stamp: Reference position.

        Returns:
            Nearest anchor point, or None.
        """
        if self._timeline_map is None or not self._timeline_map.anchor_points:
            return None

        nearest = None
        min_distance = float('inf')

        for anchor in self._timeline_map.anchor_points:
            if anchor.frame_id == stamp.frame_id:
                distance = abs(anchor.t - stamp.t)
                if distance < min_distance:
                    min_distance = distance
                    nearest = anchor

        return nearest
