"""Emulated Sensors - Realistic sensor simulation with noise and drift.

Provides hardware-accurate sensor emulation including:
- Magnetometers with noise, offset, and temperature dependence
- Position sensors with drift and resolution limits
- Temperature sensors with response time
- Power meters with accuracy specifications
- Current/voltage sensors
"""

from __future__ import annotations

import math
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SensorStatus(Enum):
    """Sensor operational status."""

    OK = "ok"
    DEGRADED = "degraded"
    FAULT = "fault"
    CALIBRATING = "calibrating"
    OFFLINE = "offline"


@dataclass
class NoiseModel:
    """Generic noise model for sensors.

    Attributes:
        white_noise_std: Standard deviation of white noise
        pink_noise_amplitude: 1/f noise amplitude
        quantization_step: ADC quantization step (0 = continuous)
        offset: Constant offset (bias)
        drift_rate: Linear drift rate per second
        temperature_coefficient: Sensitivity to temperature (per Kelvin)
    """

    white_noise_std: float = 0.0
    pink_noise_amplitude: float = 0.0
    quantization_step: float = 0.0
    offset: float = 0.0
    drift_rate: float = 0.0
    temperature_coefficient: float = 0.0


@dataclass
class SensorSpecs:
    """Generic sensor specifications.

    Attributes:
        range_min: Minimum measurable value
        range_max: Maximum measurable value
        resolution: Measurement resolution
        accuracy_percent: Accuracy as percentage of reading
        response_time_seconds: Time constant for response
        sample_rate_hz: Maximum sample rate
    """

    range_min: float = 0.0
    range_max: float = 100.0
    resolution: float = 0.01
    accuracy_percent: float = 1.0
    response_time_seconds: float = 0.01
    sample_rate_hz: float = 1000.0


class EmulatedSensor(ABC):
    """Base class for emulated sensors."""

    def __init__(
        self,
        sensor_id: str,
        specs: SensorSpecs | None = None,
        noise: NoiseModel | None = None,
    ):
        """Initialize sensor.

        Args:
            sensor_id: Unique sensor identifier
            specs: Sensor specifications
            noise: Noise model
        """
        self._sensor_id = sensor_id
        self._specs = specs or SensorSpecs()
        self._noise = noise or NoiseModel()

        self._status = SensorStatus.OK
        self._last_reading = 0.0
        self._true_value = 0.0
        self._accumulated_drift = 0.0
        self._start_time = time.monotonic()
        self._last_sample_time = 0.0
        self._calibration_offset = 0.0

        # Pink noise state (for 1/f noise generation)
        self._pink_noise_state = [0.0] * 7

    @property
    def sensor_id(self) -> str:
        return self._sensor_id

    @property
    def status(self) -> SensorStatus:
        return self._status

    def set_true_value(self, value: float, instant: bool = True) -> None:
        """Set the true value being measured.

        Args:
            value: The true physical value
            instant: If True, also update last_reading (no lag)
        """
        self._true_value = value
        if instant:
            self._last_reading = value

    def read(self, temperature_kelvin: float = 293.0) -> float:
        """Read sensor value with noise and errors.

        Args:
            temperature_kelvin: Current temperature for temp compensation

        Returns:
            Measured value with realistic errors
        """
        if self._status == SensorStatus.OFFLINE:
            return float('nan')

        if self._status == SensorStatus.FAULT:
            return float('nan')

        # Check sample rate
        now = time.monotonic()
        min_interval = 1.0 / self._specs.sample_rate_hz
        if now - self._last_sample_time < min_interval:
            return self._last_reading
        self._last_sample_time = now

        # Start with true value
        value = self._true_value

        # Apply response time (first-order filter)
        dt = now - self._start_time
        if self._specs.response_time_seconds > 0:
            alpha = 1.0 - math.exp(-dt / self._specs.response_time_seconds)
            value = self._last_reading + alpha * (value - self._last_reading)

        # Add sensor errors
        value = self._apply_errors(value, temperature_kelvin)

        # Clamp to range
        value = max(self._specs.range_min, min(self._specs.range_max, value))

        # Apply resolution/quantization
        if self._specs.resolution > 0:
            value = round(value / self._specs.resolution) * self._specs.resolution

        self._last_reading = value
        return value

    def _apply_errors(self, value: float, temperature_kelvin: float) -> float:
        """Apply noise and systematic errors."""
        # Offset (bias)
        value += self._noise.offset + self._calibration_offset

        # Drift
        elapsed = time.monotonic() - self._start_time
        self._accumulated_drift = self._noise.drift_rate * elapsed
        value += self._accumulated_drift

        # Temperature effect
        temp_deviation = temperature_kelvin - 293.0  # Reference temp
        value += self._noise.temperature_coefficient * temp_deviation * value

        # White noise
        if self._noise.white_noise_std > 0:
            value += random.gauss(0, self._noise.white_noise_std)

        # Pink noise (1/f)
        if self._noise.pink_noise_amplitude > 0:
            value += self._generate_pink_noise() * self._noise.pink_noise_amplitude

        # Quantization noise
        if self._noise.quantization_step > 0:
            value = round(value / self._noise.quantization_step) * self._noise.quantization_step

        return value

    def _generate_pink_noise(self) -> float:
        """Generate pink (1/f) noise using Voss-McCartney algorithm."""
        # Simplified pink noise approximation
        white = random.gauss(0, 1)

        # Update octave bands
        for i in range(len(self._pink_noise_state)):
            if random.random() < 1.0 / (2 ** i):
                self._pink_noise_state[i] = random.gauss(0, 1)

        return sum(self._pink_noise_state) / len(self._pink_noise_state) + white * 0.5

    def calibrate(self, reference_value: float | None = None) -> bool:
        """Calibrate the sensor.

        Args:
            reference_value: Known reference value (None = use current)

        Returns:
            True if calibration succeeded
        """
        self._status = SensorStatus.CALIBRATING
        time.sleep(0.01)  # Simulate calibration time

        if reference_value is not None:
            # Calculate offset from reference
            self._calibration_offset = reference_value - self._true_value
        else:
            # Zero the drift
            self._calibration_offset = -self._accumulated_drift

        self._accumulated_drift = 0.0
        self._start_time = time.monotonic()
        self._status = SensorStatus.OK
        return True

    def set_fault(self, fault: bool) -> None:
        """Set fault state."""
        self._status = SensorStatus.FAULT if fault else SensorStatus.OK

    def get_diagnostics(self) -> dict[str, Any]:
        """Get sensor diagnostics."""
        return {
            "sensor_id": self._sensor_id,
            "status": self._status.value,
            "last_reading": self._last_reading,
            "true_value": self._true_value,
            "accumulated_drift": self._accumulated_drift,
            "calibration_offset": self._calibration_offset,
            "uptime_seconds": time.monotonic() - self._start_time,
        }


class Magnetometer(EmulatedSensor):
    """Emulated magnetometer for field measurement.

    Models a Hall-effect or fluxgate magnetometer with realistic
    noise characteristics for superconducting magnet applications.
    """

    def __init__(
        self,
        sensor_id: str = "magnetometer_1",
        max_field_tesla: float = 20.0,
    ):
        """Initialize magnetometer.

        Args:
            sensor_id: Sensor identifier
            max_field_tesla: Maximum measurable field
        """
        specs = SensorSpecs(
            range_min=-max_field_tesla,
            range_max=max_field_tesla,
            resolution=1e-5,  # 10 uT resolution
            accuracy_percent=0.1,
            response_time_seconds=0.001,  # 1ms response
            sample_rate_hz=10000.0,
        )

        noise = NoiseModel(
            white_noise_std=1e-5,  # 10 uT noise
            pink_noise_amplitude=5e-6,  # 5 uT 1/f noise
            quantization_step=1e-6,  # 1 uT quantization
            offset=0.0,
            drift_rate=1e-9,  # 1 nT/s drift
            temperature_coefficient=1e-5,  # 10 ppm/K
        )

        super().__init__(sensor_id, specs, noise)


class TemperatureSensor(EmulatedSensor):
    """Emulated temperature sensor for cryogenic monitoring.

    Models a cryogenic temperature sensor (e.g., Cernox, platinum RTD)
    with appropriate characteristics for superconducting systems.
    """

    def __init__(
        self,
        sensor_id: str = "temp_sensor_1",
        max_temp_kelvin: float = 400.0,
    ):
        """Initialize temperature sensor.

        Args:
            sensor_id: Sensor identifier
            max_temp_kelvin: Maximum measurable temperature
        """
        specs = SensorSpecs(
            range_min=0.1,  # Near absolute zero
            range_max=max_temp_kelvin,
            resolution=0.001,  # 1 mK resolution
            accuracy_percent=0.5,
            response_time_seconds=0.5,  # Thermal response
            sample_rate_hz=100.0,
        )

        noise = NoiseModel(
            white_noise_std=0.01,  # 10 mK noise
            pink_noise_amplitude=0.005,
            quantization_step=0.001,
            offset=0.0,
            drift_rate=1e-6,  # Very slow drift
            temperature_coefficient=0.0,  # Self-referential, no temp coeff
        )

        super().__init__(sensor_id, specs, noise)


class CurrentSensor(EmulatedSensor):
    """Emulated current sensor for power supply monitoring.

    Models a precision current transducer (e.g., DCCT) for
    high-current superconducting magnet applications.
    """

    def __init__(
        self,
        sensor_id: str = "current_sensor_1",
        max_current_amps: float = 1000.0,
    ):
        """Initialize current sensor.

        Args:
            sensor_id: Sensor identifier
            max_current_amps: Maximum measurable current
        """
        specs = SensorSpecs(
            range_min=-max_current_amps,
            range_max=max_current_amps,
            resolution=0.001,  # 1 mA resolution
            accuracy_percent=0.01,  # 100 ppm accuracy
            response_time_seconds=0.0001,  # 100 us response
            sample_rate_hz=100000.0,
        )

        noise = NoiseModel(
            white_noise_std=0.01,  # 10 mA noise
            pink_noise_amplitude=0.005,
            quantization_step=0.001,
            offset=0.0,
            drift_rate=1e-6,
            temperature_coefficient=5e-6,  # 5 ppm/K
        )

        super().__init__(sensor_id, specs, noise)


class VoltageSensor(EmulatedSensor):
    """Emulated voltage sensor.

    Models a precision voltage measurement for power supply monitoring.
    """

    def __init__(
        self,
        sensor_id: str = "voltage_sensor_1",
        max_voltage_volts: float = 100.0,
    ):
        """Initialize voltage sensor.

        Args:
            sensor_id: Sensor identifier
            max_voltage_volts: Maximum measurable voltage
        """
        specs = SensorSpecs(
            range_min=-max_voltage_volts,
            range_max=max_voltage_volts,
            resolution=0.0001,  # 100 uV resolution
            accuracy_percent=0.01,
            response_time_seconds=0.00001,  # 10 us response
            sample_rate_hz=1000000.0,
        )

        noise = NoiseModel(
            white_noise_std=0.0001,  # 100 uV noise
            pink_noise_amplitude=0.00005,
            quantization_step=0.0001,
            offset=0.0,
            drift_rate=1e-7,
            temperature_coefficient=2e-6,  # 2 ppm/K
        )

        super().__init__(sensor_id, specs, noise)


class PowerMeter(EmulatedSensor):
    """Emulated power meter.

    Computes power from current and voltage sensors, or directly
    measures power with appropriate uncertainty propagation.
    """

    def __init__(
        self,
        sensor_id: str = "power_meter_1",
        max_power_watts: float = 1e6,
    ):
        """Initialize power meter.

        Args:
            sensor_id: Sensor identifier
            max_power_watts: Maximum measurable power
        """
        specs = SensorSpecs(
            range_min=0.0,
            range_max=max_power_watts,
            resolution=1.0,  # 1 W resolution
            accuracy_percent=0.5,
            response_time_seconds=0.01,
            sample_rate_hz=1000.0,
        )

        noise = NoiseModel(
            white_noise_std=10.0,  # 10 W noise
            pink_noise_amplitude=5.0,
            quantization_step=1.0,
            offset=0.0,
            drift_rate=0.01,
            temperature_coefficient=1e-5,
        )

        super().__init__(sensor_id, specs, noise)


class PositionSensor(EmulatedSensor):
    """Emulated position sensor.

    Models an encoder or linear position sensor for
    mechanical positioning systems.
    """

    def __init__(
        self,
        sensor_id: str = "position_sensor_1",
        range_meters: float = 1.0,
    ):
        """Initialize position sensor.

        Args:
            sensor_id: Sensor identifier
            range_meters: Maximum position range
        """
        specs = SensorSpecs(
            range_min=0.0,
            range_max=range_meters,
            resolution=1e-6,  # 1 um resolution
            accuracy_percent=0.001,
            response_time_seconds=0.0001,
            sample_rate_hz=10000.0,
        )

        noise = NoiseModel(
            white_noise_std=1e-6,  # 1 um noise
            pink_noise_amplitude=5e-7,
            quantization_step=1e-6,
            offset=0.0,
            drift_rate=1e-9,  # 1 nm/s drift
            temperature_coefficient=1e-5,  # Thermal expansion
        )

        super().__init__(sensor_id, specs, noise)


@dataclass
class SensorArray:
    """Collection of sensors for a subsystem.

    Provides a convenient way to manage multiple related sensors.
    """

    array_id: str = ""
    sensors: dict[str, EmulatedSensor] = field(default_factory=dict)

    def add_sensor(self, sensor: EmulatedSensor) -> None:
        """Add a sensor to the array."""
        self.sensors[sensor.sensor_id] = sensor

    def read_all(self, temperature_kelvin: float = 293.0) -> dict[str, float]:
        """Read all sensors."""
        return {
            sensor_id: sensor.read(temperature_kelvin)
            for sensor_id, sensor in self.sensors.items()
        }

    def calibrate_all(self) -> dict[str, bool]:
        """Calibrate all sensors."""
        return {
            sensor_id: sensor.calibrate()
            for sensor_id, sensor in self.sensors.items()
        }

    def get_status(self) -> dict[str, SensorStatus]:
        """Get status of all sensors."""
        return {
            sensor_id: sensor.status
            for sensor_id, sensor in self.sensors.items()
        }


def create_field_generator_sensors() -> SensorArray:
    """Create a standard sensor array for a field generator."""
    array = SensorArray(array_id="field_gen_sensors")

    # Field measurement
    array.add_sensor(Magnetometer("mag_main"))
    array.add_sensor(Magnetometer("mag_backup"))

    # Temperature monitoring
    array.add_sensor(TemperatureSensor("temp_coil_1"))
    array.add_sensor(TemperatureSensor("temp_coil_2"))
    array.add_sensor(TemperatureSensor("temp_helium"))
    array.add_sensor(TemperatureSensor("temp_shield"))

    # Power supply monitoring
    array.add_sensor(CurrentSensor("current_main"))
    array.add_sensor(VoltageSensor("voltage_main"))
    array.add_sensor(PowerMeter("power_main"))

    return array


def create_tdu_sensors() -> SensorArray:
    """Create a standard sensor array for a TDU."""
    array = SensorArray(array_id="tdu_sensors")

    # Position/timing
    array.add_sensor(PositionSensor("pos_x"))
    array.add_sensor(PositionSensor("pos_y"))
    array.add_sensor(PositionSensor("pos_z"))

    # Temperature
    array.add_sensor(TemperatureSensor("temp_chamber"))
    array.add_sensor(TemperatureSensor("temp_electronics"))

    # Power
    array.add_sensor(PowerMeter("power_total"))
    array.add_sensor(CurrentSensor("capacitor_current"))
    array.add_sensor(VoltageSensor("capacitor_voltage"))

    return array
