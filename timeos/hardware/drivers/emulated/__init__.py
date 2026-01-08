"""Emulated Hardware Drivers - Realistic hardware behavior simulation.

This package provides hardware-accurate emulation with:
- Realistic timing (ramp-up, ramp-down, settling)
- Thermal modeling (temperature, quench risk)
- Power supply limitations and ripple
- Sensor noise and calibration drift
- Configurable failure modes

Unlike the simulated drivers which provide instant, ideal behavior,
emulated drivers model real hardware constraints and failure modes.

ROS2 Compatibility:
The interfaces and time_machine modules are designed for easy migration
to ROS2. Message types map to ROS2 msgs, pub/sub maps to topics,
and services map to ROS2 services.
"""

from timeos.hardware.drivers.emulated.field_generator import EmulatedFieldGenerator
from timeos.hardware.drivers.emulated.thermal_model import ThermalModel, ThermalState
from timeos.hardware.drivers.emulated.temporal_displacement import EmulatedTDU
from timeos.hardware.drivers.emulated.failure_injection import (
    FailureInjector,
    FailureScenario,
    FailureSeverity,
    TriggerType,
    RecoveryType,
    ActiveFailure,
    BUILTIN_SCENARIOS,
)
from timeos.hardware.drivers.emulated.sensors import (
    EmulatedSensor,
    Magnetometer,
    TemperatureSensor,
    CurrentSensor,
    VoltageSensor,
    PowerMeter,
    PositionSensor,
    SensorArray,
    SensorStatus,
    NoiseModel,
    SensorSpecs,
    create_field_generator_sensors,
    create_tdu_sensors,
)
from timeos.hardware.drivers.emulated.interfaces import (
    # Message types (map to ROS2 msgs)
    Header,
    FieldStatus,
    TDUStatus,
    ThermalStatus,
    SensorReading,
    SafetyStatus,
    SystemStatus,
    DisplacementRequest,
    DisplacementResponse,
    # Pub/Sub (maps to ROS2 topics)
    Publisher,
    Subscriber,
    MessageBroker,
    # Services (maps to ROS2 services)
    Service,
    ServiceClient,
    ServiceRegistry,
    # Parameters (maps to ROS2 parameters)
    ParameterServer,
    # Node base class
    NodeBase,
)
from timeos.hardware.drivers.emulated.time_machine import (
    EmulatedTimeMachine,
    MachineState,
    MachineConfig,
    FieldGeneratorNode,
    TDUNode,
    SafetyMonitor,
)

__all__ = [
    # Integrated Time Machine
    "EmulatedTimeMachine",
    "MachineState",
    "MachineConfig",
    "FieldGeneratorNode",
    "TDUNode",
    "SafetyMonitor",
    # Main components
    "EmulatedFieldGenerator",
    "EmulatedTDU",
    "ThermalModel",
    "ThermalState",
    # Failure injection
    "FailureInjector",
    "FailureScenario",
    "FailureSeverity",
    "TriggerType",
    "RecoveryType",
    "ActiveFailure",
    "BUILTIN_SCENARIOS",
    # Sensors
    "EmulatedSensor",
    "Magnetometer",
    "TemperatureSensor",
    "CurrentSensor",
    "VoltageSensor",
    "PowerMeter",
    "PositionSensor",
    "SensorArray",
    "SensorStatus",
    "NoiseModel",
    "SensorSpecs",
    "create_field_generator_sensors",
    "create_tdu_sensors",
    # ROS-compatible interfaces
    "Header",
    "FieldStatus",
    "TDUStatus",
    "ThermalStatus",
    "SensorReading",
    "SafetyStatus",
    "SystemStatus",
    "DisplacementRequest",
    "DisplacementResponse",
    "Publisher",
    "Subscriber",
    "MessageBroker",
    "Service",
    "ServiceClient",
    "ServiceRegistry",
    "ParameterServer",
    "NodeBase",
]
