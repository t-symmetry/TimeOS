"""TimeOS Hardware Abstraction Layer.

Provides abstract interfaces for temporal manipulation hardware,
along with simulated implementations for testing and development.

When actual hardware becomes available, implement the abstract
interfaces and plug them in. The software layer is ready.
"""

from timeos.hardware.base import (
    HardwareModule,
    ModuleStatus,
    HardwareError,
    CalibrationError,
    SafetyInterlock,
)
from timeos.hardware.temporal_displacement import (
    TemporalDisplacementUnit,
    DisplacementRequest,
    DisplacementResult,
)
from timeos.hardware.field_generator import (
    FieldGenerator,
    FieldConfiguration,
    FieldState,
)
from timeos.hardware.causality_monitor import (
    CausalityMonitor,
    CausalityAlert,
    AlertSeverity,
)
from timeos.hardware.timeline_navigator import (
    TimelineNavigator,
    NavigationTarget,
    NavigationPath,
)
from timeos.hardware.anchor import (
    TemporalAnchor,
    AnchorPoint,
    AnchorStatus,
)
from timeos.hardware.safety import (
    SafetySystem,
    SafetyStatus,
    EmergencyProtocol,
)

__all__ = [
    # Base
    "HardwareModule",
    "ModuleStatus",
    "HardwareError",
    "CalibrationError",
    "SafetyInterlock",
    # Displacement
    "TemporalDisplacementUnit",
    "DisplacementRequest",
    "DisplacementResult",
    # Field
    "FieldGenerator",
    "FieldConfiguration",
    "FieldState",
    # Causality
    "CausalityMonitor",
    "CausalityAlert",
    "AlertSeverity",
    # Navigation
    "TimelineNavigator",
    "NavigationTarget",
    "NavigationPath",
    # Anchor
    "TemporalAnchor",
    "AnchorPoint",
    "AnchorStatus",
    # Safety
    "SafetySystem",
    "SafetyStatus",
    "EmergencyProtocol",
]
