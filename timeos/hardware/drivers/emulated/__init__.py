"""Emulated Hardware Drivers - Realistic hardware behavior simulation.

This package provides hardware-accurate emulation with:
- Realistic timing (ramp-up, ramp-down, settling)
- Thermal modeling (temperature, quench risk)
- Power supply limitations and ripple
- Sensor noise and calibration drift
- Configurable failure modes

Unlike the simulated drivers which provide instant, ideal behavior,
emulated drivers model real hardware constraints and failure modes.
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

__all__ = [
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
]
