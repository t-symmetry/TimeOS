"""Safety System - Emergency protocols and fail-safes.

The safety system monitors all hardware modules and intervenes
when dangerous conditions are detected.

Safety priorities (in order):
1. Prevent paradoxes that could destabilize reality
2. Preserve human life
3. Maintain timeline integrity
4. Protect equipment
5. Complete mission objectives

Emergency protocols:
- ABORT: Halt all operations immediately
- RETURN: Emergency return to anchor
- BRANCH: Force timeline branch to isolate damage
- FREEZE: Hold position, await manual intervention
- SHUTDOWN: Complete system shutdown

The safety system has override authority over all other modules.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from timeos.hardware.base import HardwareModule, ModuleStatus, ModuleDiagnostics


class SafetyLevel(Enum):
    """Overall system safety level."""

    NOMINAL = "nominal"  # All systems normal
    CAUTION = "caution"  # Minor issues, continue with care
    WARNING = "warning"  # Significant issues, consider abort
    DANGER = "danger"  # Serious issues, abort recommended
    CRITICAL = "critical"  # Emergency, automatic intervention
    CATASTROPHIC = "catastrophic"  # System failure imminent


class EmergencyProtocol(Enum):
    """Emergency response protocols."""

    NONE = "none"  # No action needed
    MONITOR = "monitor"  # Increase monitoring
    ALERT = "alert"  # Alert operator
    PAUSE = "pause"  # Pause operations
    ABORT = "abort"  # Abort current operation
    RETURN = "return"  # Emergency return to anchor
    BRANCH = "branch"  # Force timeline branch
    FREEZE = "freeze"  # Hold position
    SHUTDOWN = "shutdown"  # Complete shutdown


class InterlockType(Enum):
    """Type of safety interlock."""

    HARDWARE = "hardware"  # Physical hardware interlock
    SOFTWARE = "software"  # Software safety check
    TEMPORAL = "temporal"  # Temporal consistency check
    CAUSAL = "causal"  # Causality violation check
    ENERGY = "energy"  # Energy limit check
    BIOLOGICAL = "biological"  # Human safety check


@dataclass
class SafetyInterlock:
    """A safety interlock condition.

    Attributes:
        interlock_id: Unique identifier
        interlock_type: Type of interlock
        description: Human-readable description
        is_engaged: Whether interlock is currently triggered
        can_override: Whether operator can override
        override_requires: Conditions for override
        engaged_at: When interlock was triggered
    """

    interlock_id: str
    interlock_type: InterlockType
    description: str
    is_engaged: bool = False
    can_override: bool = False
    override_requires: list[str] = field(default_factory=list)
    engaged_at: datetime | None = None


@dataclass
class SafetyStatus:
    """Overall safety system status.

    Attributes:
        level: Current safety level
        active_protocol: Currently active emergency protocol
        engaged_interlocks: List of triggered interlocks
        monitored_modules: Modules being monitored
        last_check: Last safety check timestamp
        issues: Current safety issues
        recommendations: Recommended actions
    """

    level: SafetyLevel = SafetyLevel.NOMINAL
    active_protocol: EmergencyProtocol = EmergencyProtocol.NONE
    engaged_interlocks: list[SafetyInterlock] = field(default_factory=list)
    monitored_modules: list[str] = field(default_factory=list)
    last_check: datetime = field(default_factory=datetime.utcnow)
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class SafetyLimits:
    """Operational safety limits.

    Attributes:
        max_displacement_seconds: Maximum temporal displacement
        max_energy_joules: Maximum energy per operation
        max_paradox_probability: Maximum acceptable paradox risk
        min_anchor_strength: Minimum anchor signal strength
        max_field_tesla: Maximum magnetic field
        min_return_energy: Reserved energy for return
        max_operation_duration: Maximum operation time
    """

    max_displacement_seconds: float = 3.154e7  # ~1 year
    max_energy_joules: float = 1e15  # 1 petajoule
    max_paradox_probability: float = 0.01  # 1%
    min_anchor_strength: float = 0.3
    max_field_tesla: float = 100.0
    min_return_energy: float = 1e12  # Always keep enough to return
    max_operation_duration: float = 3600.0  # 1 hour


class SafetySystem(HardwareModule):
    """Abstract interface for the safety system.

    The safety system is the highest-authority module in TimeOS.
    It monitors all other modules and can override any operation
    that poses safety risks.

    The safety system cannot be disabled during active operations.

    Features:
    - Continuous monitoring of all modules
    - Automatic emergency protocol activation
    - Interlock management
    - Operator alert system
    - Black box recording of all safety events

    Integration:
    - Receives status from all hardware modules
    - Can trigger emergency_stop on any module
    - Coordinates with CausalityMonitor
    - Controls anchor emergency return
    """

    def __init__(self, module_id: str = "safety"):
        super().__init__(module_id)
        self._interlocks: dict[str, SafetyInterlock] = {}
        self._limits = SafetyLimits()
        self._active_protocol = EmergencyProtocol.NONE
        self._event_log: list[tuple[datetime, str, dict]] = []
        self._monitored_modules: list[HardwareModule] = []

    @property
    def limits(self) -> SafetyLimits:
        """Current safety limits."""
        return self._limits

    @property
    def active_protocol(self) -> EmergencyProtocol:
        """Currently active emergency protocol."""
        return self._active_protocol

    @abstractmethod
    def register_module(self, module: HardwareModule) -> None:
        """Register a module for safety monitoring.

        Args:
            module: Module to monitor.
        """
        pass

    @abstractmethod
    def check_safety(self) -> SafetyStatus:
        """Run comprehensive safety check.

        Returns:
            Current safety status.
        """
        pass

    @abstractmethod
    def check_operation(
        self,
        operation: str,
        parameters: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """Check if an operation is safe to proceed.

        Args:
            operation: Operation name.
            parameters: Operation parameters.

        Returns:
            Tuple of (is_safe, list of concerns).
        """
        pass

    @abstractmethod
    def engage_interlock(
        self,
        interlock_type: InterlockType,
        reason: str,
    ) -> SafetyInterlock:
        """Engage a safety interlock.

        Args:
            interlock_type: Type of interlock.
            reason: Reason for engagement.

        Returns:
            The engaged interlock.
        """
        pass

    @abstractmethod
    def release_interlock(
        self,
        interlock_id: str,
        override_code: str | None = None,
    ) -> bool:
        """Release a safety interlock.

        Args:
            interlock_id: Interlock to release.
            override_code: Override authorization (if required).

        Returns:
            True if interlock was released.
        """
        pass

    @abstractmethod
    def activate_protocol(self, protocol: EmergencyProtocol) -> bool:
        """Activate an emergency protocol.

        Args:
            protocol: Protocol to activate.

        Returns:
            True if protocol was activated.
        """
        pass

    @abstractmethod
    def deactivate_protocol(self) -> bool:
        """Deactivate current emergency protocol.

        Returns:
            True if deactivation succeeded.
        """
        pass

    @abstractmethod
    def emergency_abort(self) -> bool:
        """Trigger emergency abort of all operations.

        This is the highest-priority emergency action.

        Returns:
            True if abort was successful.
        """
        pass

    @abstractmethod
    def get_event_log(
        self,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[tuple[datetime, str, dict]]:
        """Get safety event log.

        Args:
            since: Only events after this time.
            limit: Maximum number of events.

        Returns:
            List of (timestamp, event_type, details) tuples.
        """
        pass

    def set_limits(self, limits: SafetyLimits) -> None:
        """Update safety limits.

        Args:
            limits: New safety limits.
        """
        self._limits = limits
        self._log_event("limits_updated", {"new_limits": limits})

    def _log_event(self, event_type: str, details: dict[str, Any]) -> None:
        """Log a safety event."""
        self._event_log.append((datetime.utcnow(), event_type, details))

    def get_interlocks(self, engaged_only: bool = False) -> list[SafetyInterlock]:
        """Get list of interlocks.

        Args:
            engaged_only: Only return engaged interlocks.

        Returns:
            List of interlocks.
        """
        interlocks = list(self._interlocks.values())
        if engaged_only:
            interlocks = [i for i in interlocks if i.is_engaged]
        return interlocks
