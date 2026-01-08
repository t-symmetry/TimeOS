"""Base classes for TimeOS hardware modules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ModuleStatus(Enum):
    """Operational status of a hardware module."""

    OFFLINE = "offline"  # Not initialized
    INITIALIZING = "initializing"  # Starting up
    CALIBRATING = "calibrating"  # Running calibration
    STANDBY = "standby"  # Ready but not active
    ACTIVE = "active"  # Currently operating
    ERROR = "error"  # Fault condition
    EMERGENCY_STOP = "emergency_stop"  # Safety shutdown
    MAINTENANCE = "maintenance"  # Requires service


class HardwareError(Exception):
    """Base exception for hardware errors."""

    def __init__(self, message: str, module: str, error_code: int = 0):
        super().__init__(message)
        self.module = module
        self.error_code = error_code
        self.timestamp = datetime.utcnow()


class CalibrationError(HardwareError):
    """Calibration failure."""
    pass


class SafetyInterlock(HardwareError):
    """Safety system prevented operation."""
    pass


@dataclass
class ModuleDiagnostics:
    """Diagnostic information from a hardware module."""

    module_id: str
    status: ModuleStatus
    uptime_seconds: float
    temperature_kelvin: float | None = None
    power_watts: float | None = None
    error_count: int = 0
    last_error: str | None = None
    calibration_valid: bool = False
    calibration_timestamp: datetime | None = None
    custom_metrics: dict[str, Any] = field(default_factory=dict)


class HardwareModule(ABC):
    """Abstract base class for all hardware modules.

    All temporal manipulation hardware must implement this interface.
    This ensures consistent lifecycle management, diagnostics, and
    safety integration across all modules.
    """

    def __init__(self, module_id: str):
        """Initialize hardware module.

        Args:
            module_id: Unique identifier for this module instance.
        """
        self.module_id = module_id
        self._status = ModuleStatus.OFFLINE
        self._start_time: datetime | None = None
        self._error_count = 0
        self._last_error: str | None = None

    @property
    def status(self) -> ModuleStatus:
        """Current operational status."""
        return self._status

    @property
    def is_operational(self) -> bool:
        """Check if module is ready for operations."""
        return self._status in (ModuleStatus.STANDBY, ModuleStatus.ACTIVE)

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the hardware module.

        Returns:
            True if initialization succeeded.

        Raises:
            HardwareError: If initialization fails.
        """
        pass

    @abstractmethod
    def shutdown(self) -> bool:
        """Safely shutdown the hardware module.

        Returns:
            True if shutdown completed cleanly.
        """
        pass

    @abstractmethod
    def calibrate(self) -> bool:
        """Run calibration routine.

        Returns:
            True if calibration succeeded.

        Raises:
            CalibrationError: If calibration fails.
        """
        pass

    @abstractmethod
    def self_test(self) -> tuple[bool, list[str]]:
        """Run self-diagnostics.

        Returns:
            Tuple of (passed, list of issues found).
        """
        pass

    @abstractmethod
    def emergency_stop(self) -> bool:
        """Immediately halt all operations.

        This should be safe to call at any time and should
        bring the module to a safe state as quickly as possible.

        Returns:
            True if emergency stop completed.
        """
        pass

    @abstractmethod
    def get_diagnostics(self) -> ModuleDiagnostics:
        """Get current diagnostic information.

        Returns:
            Current module diagnostics.
        """
        pass

    def _set_status(self, status: ModuleStatus) -> None:
        """Update module status (internal use)."""
        self._status = status

    def _record_error(self, error: str) -> None:
        """Record an error (internal use)."""
        self._error_count += 1
        self._last_error = error


@dataclass
class PowerRequirements:
    """Power requirements for a hardware module."""

    standby_watts: float
    active_watts: float
    peak_watts: float
    voltage: float
    current_amps: float

    # For the ambitious
    gigawatts: float = 0.0  # Set to 1.21 if using flux capacitor


@dataclass
class PhysicalDimensions:
    """Physical dimensions of a hardware module."""

    length_m: float
    width_m: float
    height_m: float
    mass_kg: float

    @property
    def volume_m3(self) -> float:
        return self.length_m * self.width_m * self.height_m
