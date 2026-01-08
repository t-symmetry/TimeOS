"""Emulated Field Generator - Realistic superconducting magnet simulation.

Provides hardware-accurate emulation including:
- Realistic ramp-up/ramp-down timing with current limits
- Thermal modeling (temperature, quench detection/protection)
- Power supply limitations (voltage, current, ripple)
- Sensor noise and measurement uncertainty
- Configurable failure modes and degradation
"""

from __future__ import annotations

import math
import random
import time
import threading
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from timeos.hardware.base import (
    HardwareModule,
    ModuleStatus,
    ModuleDiagnostics,
    HardwareError,
)
from timeos.hardware.field_generator import (
    FieldGenerator,
    FieldConfiguration,
    FieldState,
    FieldType,
    FieldGeometry,
    Vector3,
)
from timeos.hardware.drivers.emulated.thermal_model import (
    ThermalModel,
    ThermalConfig,
    ThermalState,
    ThermalStatus,
)


class RampState(Enum):
    """State of field ramping operation."""

    IDLE = "idle"
    RAMPING_UP = "ramping_up"
    RAMPING_DOWN = "ramping_down"
    HOLDING = "holding"
    EMERGENCY_DUMP = "emergency_dump"


class FaultType(Enum):
    """Types of faults that can occur."""

    NONE = "none"
    QUENCH = "quench"
    POWER_SUPPLY_FAULT = "power_supply_fault"
    COOLING_FAILURE = "cooling_failure"
    CURRENT_LIMIT = "current_limit"
    VOLTAGE_LIMIT = "voltage_limit"
    INTERLOCK_TRIP = "interlock_trip"
    COMMUNICATION_ERROR = "communication_error"


@dataclass
class PowerSupplyConfig:
    """Power supply configuration.

    Attributes:
        max_current_amps: Maximum output current
        max_voltage_volts: Maximum output voltage
        max_ramp_rate_as: Maximum current ramp rate (A/s)
        voltage_ripple_percent: Output voltage ripple (%)
        current_regulation_percent: Current regulation accuracy (%)
        response_time_ms: Control loop response time
    """

    max_current_amps: float = 500.0  # Typical superconducting magnet supply
    max_voltage_volts: float = 10.0  # Low voltage, high current
    max_ramp_rate_as: float = 50.0  # Amps per second
    voltage_ripple_percent: float = 0.1  # 0.1% ripple
    current_regulation_percent: float = 0.01  # 0.01% regulation
    response_time_ms: float = 10.0  # 10ms response


@dataclass
class MagnetConfig:
    """Superconducting magnet configuration.

    Attributes:
        inductance_henry: Magnet inductance
        field_constant_ta: Field per amp (Tesla/Ampere)
        max_field_tesla: Maximum rated field
        stored_energy_factor: E = 0.5 * L * I^2 factor
    """

    inductance_henry: float = 10.0  # 10 Henry inductance
    field_constant_ta: float = 0.02  # 0.02 T/A -> 500A = 10T
    max_field_tesla: float = 12.0  # Maximum rated field
    stored_energy_factor: float = 0.5  # E = 0.5 * L * I^2


@dataclass
class SensorConfig:
    """Sensor configuration for noise modeling.

    Attributes:
        field_noise_tesla: Gaussian noise on field measurement
        field_offset_tesla: Systematic offset in field measurement
        field_drift_ts: Drift rate (Tesla per second)
        temperature_noise_kelvin: Temperature measurement noise
        current_noise_amps: Current measurement noise
    """

    field_noise_tesla: float = 0.0001  # 0.1 mT noise
    field_offset_tesla: float = 0.0  # Calibration offset
    field_drift_ts: float = 1e-6  # 1 uT/s drift
    temperature_noise_kelvin: float = 0.01  # 10 mK noise
    current_noise_amps: float = 0.01  # 10 mA noise


@dataclass
class EmulatorConfig:
    """Complete emulator configuration."""

    power_supply: PowerSupplyConfig = dataclass_field(default_factory=PowerSupplyConfig)
    magnet: MagnetConfig = dataclass_field(default_factory=MagnetConfig)
    thermal: ThermalConfig = dataclass_field(default_factory=ThermalConfig)
    sensors: SensorConfig = dataclass_field(default_factory=SensorConfig)

    # Timing
    update_rate_hz: float = 100.0  # Internal update rate
    settling_time_seconds: float = 0.5  # Time to stabilize after ramp

    # Failure injection
    enable_failures: bool = True
    quench_probability_per_hour: float = 0.001  # Base quench rate
    power_fault_probability_per_hour: float = 0.0001


class EmulatedFieldGenerator(FieldGenerator):
    """Hardware-accurate field generator emulation.

    Emulates a superconducting magnet system with realistic:
    - Ramp timing based on inductance and power supply limits
    - Thermal behavior with quench detection
    - Sensor noise and measurement uncertainty
    - Failure modes for testing

    The emulator runs an internal update loop that simulates
    the continuous physics of the magnet system.
    """

    def __init__(
        self,
        module_id: str = "emulated_field_gen",
        config: EmulatorConfig | None = None,
    ):
        """Initialize emulated field generator.

        Args:
            module_id: Module identifier
            config: Emulator configuration
        """
        super().__init__(module_id)

        self._config = config or EmulatorConfig()

        # Thermal model
        self._thermal = ThermalModel(self._config.thermal)

        # Internal state
        self._current_amps = 0.0  # Actual magnet current
        self._target_current = 0.0  # Target current for ramping
        self._actual_b = 0.0  # Actual field (from current)
        self._actual_e = 0.0  # Electric field component
        self._ramp_state = RampState.IDLE
        self._ramp_rate_as = 0.0  # Current ramp rate

        # Fault state
        self._active_fault = FaultType.NONE
        self._fault_message = ""
        self._fault_history: list[tuple[datetime, FaultType, str]] = []

        # Sensor drift accumulator
        self._accumulated_drift = 0.0
        self._last_update = time.monotonic()

        # Statistics
        self._total_energy_joules = 0.0  # Cumulative energy delivered
        self._ramp_count = 0
        self._quench_count = 0

        # Update thread
        self._running = False
        self._update_thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Event callbacks
        self._on_quench: Callable[[], None] | None = None
        self._on_fault: Callable[[FaultType, str], None] | None = None

    # =========================================================================
    # HardwareModule Interface
    # =========================================================================

    def initialize(self) -> bool:
        """Initialize the emulated field generator."""
        self._set_status(ModuleStatus.INITIALIZING)
        self._start_time = datetime.utcnow()

        # Reset state
        self._current_amps = 0.0
        self._target_current = 0.0
        self._actual_b = 0.0
        self._ramp_state = RampState.IDLE
        self._active_fault = FaultType.NONE
        self._thermal.reset()

        # Start update thread
        self._running = True
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()

        self._set_status(ModuleStatus.STANDBY)
        return True

    def shutdown(self) -> bool:
        """Shutdown the emulated field generator."""
        # Stop update thread
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=1.0)

        # Safe ramp down if energized
        if self._field_active:
            self.de_energize()

        self._set_status(ModuleStatus.OFFLINE)
        return True

    def calibrate(self) -> bool:
        """Calibrate the field generator."""
        self._set_status(ModuleStatus.CALIBRATING)

        # Reset sensor drift
        self._accumulated_drift = 0.0

        # Simulate calibration time
        time.sleep(0.1)

        self._set_status(ModuleStatus.STANDBY)
        return True

    def self_test(self) -> tuple[bool, list[str]]:
        """Run self-test diagnostics."""
        issues = []

        # Check thermal state
        thermal_status = self._thermal.update(0.0)
        if thermal_status.state == ThermalState.QUENCH:
            issues.append("Quench condition detected")
        elif thermal_status.state == ThermalState.CRITICAL:
            issues.append("Temperature critical")

        # Check for active faults
        if self._active_fault != FaultType.NONE:
            issues.append(f"Active fault: {self._active_fault.value}")

        # Check cooling
        if not self._thermal._cooling_active:
            issues.append("Cooling system offline")

        return len(issues) == 0, issues

    def emergency_stop(self) -> bool:
        """Emergency stop - fast field dump."""
        with self._lock:
            self._ramp_state = RampState.EMERGENCY_DUMP
            self._target_current = 0.0
            # Emergency dump is much faster than normal ramp
            self._ramp_rate_as = self._config.power_supply.max_ramp_rate_as * 5

        self._set_status(ModuleStatus.EMERGENCY_STOP)
        return True

    def get_diagnostics(self) -> ModuleDiagnostics:
        """Get diagnostic information."""
        uptime = 0.0
        if self._start_time:
            uptime = (datetime.utcnow() - self._start_time).total_seconds()

        thermal_status = self._thermal.update(0.0)

        return ModuleDiagnostics(
            module_id=self.module_id,
            status=self._status,
            uptime_seconds=uptime,
            calibration_valid=True,
            calibration_timestamp=self._start_time,
            custom_metrics={
                "current_amps": self._current_amps,
                "target_current": self._target_current,
                "actual_field_tesla": self._actual_b,
                "ramp_state": self._ramp_state.value,
                "temperature_kelvin": thermal_status.temperature_kelvin,
                "thermal_state": thermal_status.state.value,
                "quench_risk": thermal_status.quench_risk,
                "active_fault": self._active_fault.value,
                "total_energy_joules": self._total_energy_joules,
                "ramp_count": self._ramp_count,
                "quench_count": self._quench_count,
            },
        )

    # =========================================================================
    # FieldGenerator Interface
    # =========================================================================

    def configure(self, config: FieldConfiguration) -> bool:
        """Configure field parameters."""
        # Validate configuration
        if config.b_field_tesla > self._config.magnet.max_field_tesla:
            raise HardwareError(
                f"Requested field {config.b_field_tesla}T exceeds maximum "
                f"{self._config.magnet.max_field_tesla}T",
                self.module_id,
            )

        with self._lock:
            self._current_config = config

        return True

    def energize(self) -> bool:
        """Energize the field (ramp to configured value)."""
        if self._current_config is None:
            return False

        if self._active_fault != FaultType.NONE:
            raise HardwareError(
                f"Cannot energize with active fault: {self._active_fault.value}",
                self.module_id,
            )

        # Calculate target current from desired field
        target_field = self._current_config.b_field_tesla
        target_current = target_field / self._config.magnet.field_constant_ta

        # Check current limit
        if target_current > self._config.power_supply.max_current_amps:
            raise HardwareError(
                f"Required current {target_current:.1f}A exceeds supply limit "
                f"{self._config.power_supply.max_current_amps:.1f}A",
                self.module_id,
            )

        with self._lock:
            self._target_current = target_current
            self._ramp_state = RampState.RAMPING_UP
            self._ramp_rate_as = self._calculate_ramp_rate(target_current)
            self._field_active = True
            self._ramp_count += 1

        self._set_status(ModuleStatus.ACTIVE)
        return True

    def de_energize(self) -> bool:
        """De-energize the field (ramp to zero)."""
        with self._lock:
            self._target_current = 0.0
            self._ramp_state = RampState.RAMPING_DOWN
            self._ramp_rate_as = self._calculate_ramp_rate(0.0)

        # Wait for ramp to complete (with timeout)
        timeout = abs(self._current_amps / self._ramp_rate_as) + 5.0 if self._ramp_rate_as > 0 else 5.0
        start = time.monotonic()

        while self._ramp_state == RampState.RAMPING_DOWN:
            if time.monotonic() - start > timeout:
                break
            time.sleep(0.05)

        with self._lock:
            self._field_active = False

        self._set_status(ModuleStatus.STANDBY)
        return True

    def ramp_to(self, target_b_tesla: float, rate_ts: float | None = None) -> bool:
        """Ramp field to target value.

        Args:
            target_b_tesla: Target field strength
            rate_ts: Ramp rate in Tesla/second (None = calculate optimal)

        Returns:
            True if ramp started successfully
        """
        if self._active_fault != FaultType.NONE:
            return False

        target_current = target_b_tesla / self._config.magnet.field_constant_ta

        # Validate
        if target_current > self._config.power_supply.max_current_amps:
            return False

        with self._lock:
            self._target_current = target_current

            if rate_ts is not None:
                # Convert T/s to A/s
                self._ramp_rate_as = rate_ts / self._config.magnet.field_constant_ta
            else:
                self._ramp_rate_as = self._calculate_ramp_rate(target_current)

            if target_current > self._current_amps:
                self._ramp_state = RampState.RAMPING_UP
            elif target_current < self._current_amps:
                self._ramp_state = RampState.RAMPING_DOWN
            else:
                self._ramp_state = RampState.HOLDING

        return True

    def get_field_state(self) -> FieldState:
        """Get current field state with realistic measurements."""
        thermal_status = self._thermal.update(0.0)

        # Add sensor noise to measurements
        measured_b = self._actual_b + self._get_field_noise()
        measured_e = self._actual_e

        # Calculate stability and uniformity
        stability = self._calculate_stability()
        uniformity = self._calculate_uniformity()

        # Calculate power consumption
        # P = V * I, where V = L * dI/dt + I * R (R ~= 0 when superconducting)
        voltage = self._config.magnet.inductance_henry * self._ramp_rate_as
        power = abs(voltage * self._current_amps)

        return FieldState(
            active=self._field_active,
            configuration=self._current_config,
            actual_b_tesla=measured_b,
            actual_e_vm=measured_e,
            stability=stability,
            uniformity=uniformity,
            power_watts=power,
            temperature_kelvin=thermal_status.temperature_kelvin + self._get_temp_noise(),
            quench_risk=thermal_status.quench_risk,
        )

    def measure_field(self, position: Vector3) -> tuple[Vector3, Vector3]:
        """Measure field at position with noise."""
        if self._current_config is None:
            return Vector3(), Vector3()

        # Base field from configuration
        direction = self._current_config.direction.normalized()

        # Add position-dependent variation for non-uniform geometries
        field_magnitude = self._actual_b
        if self._current_config.geometry != FieldGeometry.UNIFORM:
            # Simple falloff model for demonstration
            r = position.magnitude
            if r > 0.1:  # Outside 10cm from center
                field_magnitude *= 1.0 / (1.0 + r * r)

        # Add noise
        field_magnitude += self._get_field_noise()

        b = direction * field_magnitude
        e = direction * self._actual_e

        return b, e

    def get_field_map(
        self, resolution: float = 0.01
    ) -> dict[tuple[float, float, float], tuple[Vector3, Vector3]]:
        """Get field map (simplified for emulation)."""
        # Return a sparse map for efficiency
        field_map = {}

        for x in [-0.1, 0.0, 0.1]:
            for y in [-0.1, 0.0, 0.1]:
                for z in [-0.1, 0.0, 0.1]:
                    pos = Vector3(x, y, z)
                    b, e = self.measure_field(pos)
                    field_map[(x, y, z)] = (b, e)

        return field_map

    # =========================================================================
    # Emulator-Specific Methods
    # =========================================================================

    def get_thermal_status(self) -> ThermalStatus:
        """Get detailed thermal status."""
        return self._thermal.update(0.0)

    def get_ramp_state(self) -> RampState:
        """Get current ramp state."""
        return self._ramp_state

    def get_fault(self) -> tuple[FaultType, str]:
        """Get active fault information."""
        return self._active_fault, self._fault_message

    def clear_fault(self) -> bool:
        """Attempt to clear active fault."""
        # Can't clear quench until temperature recovers
        if self._active_fault == FaultType.QUENCH:
            if self._thermal.state not in (ThermalState.COLD, ThermalState.RECOVERY):
                return False

        self._active_fault = FaultType.NONE
        self._fault_message = ""
        self._set_status(ModuleStatus.STANDBY)
        return True

    def inject_fault(self, fault: FaultType, message: str = "") -> None:
        """Inject a fault for testing."""
        self._trigger_fault(fault, message or f"Injected {fault.value}")

    def set_quench_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for quench events."""
        self._on_quench = callback

    def set_fault_callback(self, callback: Callable[[FaultType, str], None]) -> None:
        """Set callback for fault events."""
        self._on_fault = callback

    def get_stored_energy(self) -> float:
        """Get stored energy in magnet (Joules)."""
        # E = 0.5 * L * I^2
        return (
            self._config.magnet.stored_energy_factor
            * self._config.magnet.inductance_henry
            * self._current_amps ** 2
        )

    def get_ramp_time_estimate(self, target_b_tesla: float) -> float:
        """Estimate time to ramp to target field."""
        target_current = target_b_tesla / self._config.magnet.field_constant_ta
        current_diff = abs(target_current - self._current_amps)
        rate = self._calculate_ramp_rate(target_current)
        return current_diff / rate if rate > 0 else float('inf')

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _update_loop(self) -> None:
        """Main update loop (runs in background thread)."""
        dt = 1.0 / self._config.update_rate_hz

        while self._running:
            try:
                self._update(dt)
                time.sleep(dt)
            except Exception as e:
                # Log error but keep running
                self._trigger_fault(FaultType.COMMUNICATION_ERROR, str(e))

    def _update(self, dt: float) -> None:
        """Update internal state."""
        with self._lock:
            # Update current based on ramp state
            if self._ramp_state in (RampState.RAMPING_UP, RampState.RAMPING_DOWN, RampState.EMERGENCY_DUMP):
                self._update_ramp(dt)

            # Update field from current
            self._actual_b = self._current_amps * self._config.magnet.field_constant_ta

            # Update thermal model
            self._thermal.set_current(self._current_amps)
            self._thermal.set_field_rate(self._ramp_rate_as * self._config.magnet.field_constant_ta)
            thermal_status = self._thermal.update(dt)

            # Check for quench
            if thermal_status.state == ThermalState.QUENCH and self._active_fault != FaultType.QUENCH:
                self._trigger_quench()

            # Accumulate sensor drift
            self._accumulated_drift += self._config.sensors.field_drift_ts * dt

            # Track energy
            if self._ramp_state != RampState.IDLE:
                voltage = self._config.magnet.inductance_henry * self._ramp_rate_as
                power = abs(voltage * self._current_amps)
                self._total_energy_joules += power * dt

            # Random failure injection
            if self._config.enable_failures and self._active_fault == FaultType.NONE:
                self._check_random_failures(dt)

    def _update_ramp(self, dt: float) -> None:
        """Update current during ramping."""
        diff = self._target_current - self._current_amps

        if abs(diff) < 0.001:  # Close enough
            self._current_amps = self._target_current
            self._ramp_state = RampState.HOLDING if self._target_current > 0 else RampState.IDLE
            self._ramp_rate_as = 0.0
            return

        # Calculate step
        max_step = self._ramp_rate_as * dt
        step = min(abs(diff), max_step)

        if diff > 0:
            self._current_amps += step
        else:
            self._current_amps -= step

        # Check voltage limit (V = L * dI/dt)
        actual_rate = step / dt
        voltage = self._config.magnet.inductance_henry * actual_rate

        if voltage > self._config.power_supply.max_voltage_volts:
            # Clamp rate to voltage limit
            max_rate = self._config.power_supply.max_voltage_volts / self._config.magnet.inductance_henry
            self._ramp_rate_as = min(self._ramp_rate_as, max_rate)

    def _calculate_ramp_rate(self, target_current: float) -> float:
        """Calculate optimal ramp rate."""
        # Limit by power supply
        rate = self._config.power_supply.max_ramp_rate_as

        # Limit by voltage (V = L * dI/dt)
        voltage_limited_rate = (
            self._config.power_supply.max_voltage_volts
            / self._config.magnet.inductance_henry
        )
        rate = min(rate, voltage_limited_rate)

        # Reduce rate at high currents to limit heating
        current_fraction = max(self._current_amps, target_current) / self._config.power_supply.max_current_amps
        if current_fraction > 0.8:
            rate *= 1.0 - (current_fraction - 0.8) * 2  # 20% reduction at max current

        return max(rate, 1.0)  # Minimum 1 A/s

    def _get_field_noise(self) -> float:
        """Get current field measurement noise."""
        noise = random.gauss(0, self._config.sensors.field_noise_tesla)
        offset = self._config.sensors.field_offset_tesla
        drift = self._accumulated_drift
        return noise + offset + drift

    def _get_temp_noise(self) -> float:
        """Get temperature measurement noise."""
        return random.gauss(0, self._config.sensors.temperature_noise_kelvin)

    def _calculate_stability(self) -> float:
        """Calculate field stability metric."""
        if not self._field_active:
            return 1.0

        # Stability reduced during ramping
        if self._ramp_state in (RampState.RAMPING_UP, RampState.RAMPING_DOWN):
            return 0.8

        # Stability reduced at high quench risk
        thermal = self._thermal.update(0.0)
        return max(0.5, 1.0 - thermal.quench_risk)

    def _calculate_uniformity(self) -> float:
        """Calculate field uniformity metric."""
        if self._current_config is None:
            return 1.0

        # Uniformity depends on geometry
        geometry_uniformity = {
            FieldGeometry.UNIFORM: 0.99,
            FieldGeometry.HELMHOLTZ: 0.98,
            FieldGeometry.SOLENOID: 0.95,
            FieldGeometry.DIPOLE: 0.90,
            FieldGeometry.QUADRUPOLE: 0.85,
            FieldGeometry.TOROIDAL: 0.92,
            FieldGeometry.CUSTOM: 0.90,
        }
        return geometry_uniformity.get(self._current_config.geometry, 0.90)

    def _trigger_quench(self) -> None:
        """Handle quench event."""
        self._active_fault = FaultType.QUENCH
        self._fault_message = "Superconducting quench detected"
        self._fault_history.append((datetime.utcnow(), FaultType.QUENCH, self._fault_message))
        self._quench_count += 1

        # Emergency dump
        self._ramp_state = RampState.EMERGENCY_DUMP
        self._target_current = 0.0
        self._ramp_rate_as = self._config.power_supply.max_ramp_rate_as * 10  # Very fast dump

        self._set_status(ModuleStatus.ERROR)

        if self._on_quench:
            self._on_quench()

    def _trigger_fault(self, fault: FaultType, message: str) -> None:
        """Trigger a fault condition."""
        self._active_fault = fault
        self._fault_message = message
        self._fault_history.append((datetime.utcnow(), fault, message))

        if fault in (FaultType.QUENCH, FaultType.POWER_SUPPLY_FAULT, FaultType.COOLING_FAILURE):
            self._set_status(ModuleStatus.ERROR)
        else:
            self._set_status(ModuleStatus.FAULT)

        if self._on_fault:
            self._on_fault(fault, message)

    def _check_random_failures(self, dt: float) -> None:
        """Check for random failures (if enabled)."""
        hours = dt / 3600.0

        # Quench probability increases with field and temperature
        quench_prob = self._config.quench_probability_per_hour * hours
        thermal = self._thermal.update(0.0)
        quench_prob *= 1.0 + thermal.quench_risk * 10  # Higher risk = higher probability

        if random.random() < quench_prob:
            self._thermal.force_quench()

        # Power supply fault
        if random.random() < self._config.power_fault_probability_per_hour * hours:
            self._trigger_fault(FaultType.POWER_SUPPLY_FAULT, "Random power supply fault")
