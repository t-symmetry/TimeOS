"""Temporal Displacement Unit - The core time machine engine.

This module defines the interface for temporal displacement hardware.
The actual physics implementation is left as an exercise for the reader.

Theory notes:
- Displacement occurs relative to a reference frame
- Conservation laws must be respected (energy, momentum, information?)
- Causality constraints are enforced by the CausalityMonitor
- The FieldGenerator provides the necessary field configuration
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from timeos.hardware.base import HardwareModule, ModuleStatus, ModuleDiagnostics
from timeos.msgs import ChronoStamp, TemporalFrame


class DisplacementMode(Enum):
    """Mode of temporal displacement."""

    FORWARD = "forward"  # Standard forward time travel (easy, just wait)
    BACKWARD = "backward"  # Reverse temporal displacement (hard)
    LATERAL = "lateral"  # Cross-timeline displacement (theoretical)
    ANCHOR_RETURN = "anchor_return"  # Return to anchor point


class DisplacementState(Enum):
    """Current state of displacement operation."""

    IDLE = "idle"
    PREPARING = "preparing"
    FIELD_CHARGING = "field_charging"
    DISPLACEMENT_ACTIVE = "displacement_active"
    STABILIZING = "stabilizing"
    COMPLETE = "complete"
    ABORTED = "aborted"
    FAILED = "failed"


@dataclass
class DisplacementRequest:
    """Request for temporal displacement.

    Attributes:
        target_time: Destination time coordinate
        target_frame: Reference frame for displacement
        mode: Type of displacement
        payload_mass_kg: Mass to be displaced
        energy_budget_joules: Available energy for displacement
        max_duration_seconds: Maximum operation time before abort
        safety_margin: Additional safety factor (1.0 = minimum)
    """

    target_time: ChronoStamp
    target_frame: TemporalFrame
    mode: DisplacementMode = DisplacementMode.BACKWARD
    payload_mass_kg: float = 100.0  # Human + equipment
    energy_budget_joules: float = 1e12  # Start with a terajoule
    max_duration_seconds: float = 60.0
    safety_margin: float = 1.5

    # Calculated fields
    delta_t: float = field(init=False)

    def __post_init__(self):
        # Will be set by navigator based on current time
        self.delta_t = 0.0

    @property
    def is_backward(self) -> bool:
        return self.mode == DisplacementMode.BACKWARD

    @property
    def estimated_energy_joules(self) -> float:
        """Estimate energy required for this displacement.

        This is placeholder physics. Real implementation would
        depend on actual displacement mechanism.

        Current model: E = m * c^2 * ln(1 + |delta_t| / t_planck)
        (This is nonsense but looks impressive)
        """
        c = 299792458  # m/s
        t_planck = 5.391e-44  # seconds
        base_energy = self.payload_mass_kg * c * c  # E = mc^2 as baseline
        temporal_factor = abs(self.delta_t) / t_planck

        # Logarithmic scaling because exponential would be... problematic
        if temporal_factor > 0:
            import math
            return base_energy * math.log1p(temporal_factor) * 1e-20  # Scale down
        return 0.0


@dataclass
class DisplacementResult:
    """Result of a displacement operation.

    Attributes:
        success: Whether displacement completed successfully
        actual_displacement: Achieved temporal displacement
        origin_stamp: Where/when we started
        destination_stamp: Where/when we ended up
        energy_consumed_joules: Actual energy used
        duration_seconds: How long the operation took
        state: Final state of the operation
        error_message: Error details if failed
        telemetry: Additional operational data
    """

    success: bool
    actual_displacement: float  # seconds displaced
    origin_stamp: ChronoStamp
    destination_stamp: ChronoStamp
    energy_consumed_joules: float
    duration_seconds: float
    state: DisplacementState
    error_message: str = ""
    telemetry: dict[str, Any] = field(default_factory=dict)

    @property
    def displacement_error(self) -> float:
        """Difference between target and actual displacement."""
        return self.destination_stamp.t - self.origin_stamp.t - self.actual_displacement


class TemporalDisplacementUnit(HardwareModule):
    """Abstract interface for temporal displacement hardware.

    This is the core "engine" of a time machine. Implementations
    must handle the actual physics of temporal displacement.

    Current implementations:
    - SimulatedTDU: Software simulation for testing
    - ExperimentalTDU: Stub for real hardware (not yet available)

    Safety requirements:
    - Must integrate with CausalityMonitor
    - Must respect SafetySystem interlocks
    - Must maintain TemporalAnchor connection
    - Must not exceed energy budget
    """

    def __init__(self, module_id: str = "tdu_primary"):
        super().__init__(module_id)
        self._current_state = DisplacementState.IDLE
        self._active_request: DisplacementRequest | None = None
        self._displacement_count = 0
        self._total_displacement_seconds = 0.0

    @property
    def current_state(self) -> DisplacementState:
        """Current displacement operation state."""
        return self._current_state

    @property
    def is_displacing(self) -> bool:
        """Check if displacement is in progress."""
        return self._current_state in (
            DisplacementState.PREPARING,
            DisplacementState.FIELD_CHARGING,
            DisplacementState.DISPLACEMENT_ACTIVE,
            DisplacementState.STABILIZING,
        )

    @abstractmethod
    def prepare_displacement(self, request: DisplacementRequest) -> bool:
        """Prepare for displacement operation.

        This validates the request, checks safety interlocks,
        and prepares the hardware for displacement.

        Args:
            request: Displacement parameters.

        Returns:
            True if preparation succeeded.
        """
        pass

    @abstractmethod
    def execute_displacement(self) -> DisplacementResult:
        """Execute the prepared displacement.

        Must call prepare_displacement first.

        Returns:
            Result of the displacement operation.
        """
        pass

    @abstractmethod
    def abort_displacement(self) -> bool:
        """Abort an in-progress displacement.

        Returns:
            True if abort succeeded.
        """
        pass

    @abstractmethod
    def get_displacement_progress(self) -> float:
        """Get progress of current displacement (0.0 to 1.0)."""
        pass

    @abstractmethod
    def estimate_displacement(
        self, request: DisplacementRequest
    ) -> tuple[bool, str, dict[str, Any]]:
        """Estimate if a displacement is feasible.

        Args:
            request: Proposed displacement parameters.

        Returns:
            Tuple of (feasible, reason, estimates).
        """
        pass

    def get_statistics(self) -> dict[str, Any]:
        """Get displacement statistics."""
        return {
            "displacement_count": self._displacement_count,
            "total_displacement_seconds": self._total_displacement_seconds,
            "average_displacement": (
                self._total_displacement_seconds / self._displacement_count
                if self._displacement_count > 0
                else 0.0
            ),
        }
