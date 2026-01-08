"""Emulated Temporal Displacement Unit - Realistic TDU simulation.

Provides hardware-accurate TDU emulation including:
- Realistic timing profiles for each displacement phase
- Energy consumption curves with efficiency modeling
- Position/time uncertainty from various sources
- Communication and processing latency
- Configurable failure modes
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
    CalibrationError,
)
from timeos.hardware.temporal_displacement import (
    TemporalDisplacementUnit,
    DisplacementRequest,
    DisplacementResult,
    DisplacementMode,
    DisplacementState,
)
from timeos.msgs import ChronoStamp, TemporalFrame


class TDUFaultType(Enum):
    """Types of TDU faults."""

    NONE = "none"
    CALIBRATION_DRIFT = "calibration_drift"
    FIELD_INSTABILITY = "field_instability"
    ENERGY_OVERFLOW = "energy_overflow"
    TIMING_ERROR = "timing_error"
    POSITION_LOCK_LOST = "position_lock_lost"
    COMMUNICATION_ERROR = "communication_error"
    INTERLOCK_TRIP = "interlock_trip"


class DisplacementPhase(Enum):
    """Detailed phases of displacement operation."""

    IDLE = "idle"
    VALIDATING = "validating"
    CHARGING_CAPACITORS = "charging_capacitors"
    FIELD_RAMP = "field_ramp"
    FIELD_STABILIZE = "field_stabilize"
    DISPLACEMENT_INITIATE = "displacement_initiate"
    DISPLACEMENT_TRANSIT = "displacement_transit"
    DISPLACEMENT_EMERGE = "displacement_emerge"
    POST_STABILIZE = "post_stabilize"
    COOLDOWN = "cooldown"
    COMPLETE = "complete"
    ABORTED = "aborted"
    FAILED = "failed"


@dataclass
class TimingProfile:
    """Timing parameters for displacement phases.

    All times in seconds.
    """

    validation_time: float = 0.5
    capacitor_charge_time: float = 2.0
    field_ramp_time: float = 5.0
    field_stabilize_time: float = 1.0
    displacement_initiate_time: float = 0.5
    displacement_transit_time_per_second: float = 0.001  # Time per second displaced
    displacement_emerge_time: float = 0.5
    post_stabilize_time: float = 2.0
    cooldown_time: float = 3.0

    # Minimum total displacement time
    minimum_operation_time: float = 10.0


@dataclass
class EnergyProfile:
    """Energy consumption parameters."""

    # Base energy costs (Joules)
    standby_power_watts: float = 100.0
    capacitor_charge_energy: float = 1e6  # 1 MJ to charge
    field_maintain_power_watts: float = 1000.0

    # Displacement energy scaling
    base_displacement_energy: float = 1e9  # 1 GJ base
    energy_per_second_displaced: float = 1e6  # 1 MJ per second of displacement
    backward_penalty_factor: float = 10.0  # 10x energy for backward

    # Efficiency
    conversion_efficiency: float = 0.85  # 85% efficiency
    loss_to_heat_fraction: float = 0.15


@dataclass
class UncertaintyModel:
    """Uncertainty sources for displacement accuracy."""

    # Timing uncertainty
    base_time_uncertainty_seconds: float = 1e-6  # 1 microsecond base
    uncertainty_per_second_displaced: float = 1e-9  # Additional per second

    # Position uncertainty
    base_position_uncertainty_meters: float = 0.001  # 1mm base
    position_drift_rate: float = 1e-6  # Meters per second of displacement

    # Calibration drift
    calibration_drift_per_hour: float = 1e-9  # Time drift per hour

    # Random jitter
    timing_jitter_std: float = 1e-7  # Random timing noise


@dataclass
class TDUConfig:
    """Complete TDU emulator configuration."""

    timing: TimingProfile = dataclass_field(default_factory=TimingProfile)
    energy: EnergyProfile = dataclass_field(default_factory=EnergyProfile)
    uncertainty: UncertaintyModel = dataclass_field(default_factory=UncertaintyModel)

    # Limits
    max_displacement_seconds: float = 3.154e7  # 1 year
    max_energy_joules: float = 1e15  # 1 PJ maximum
    max_power_watts: float = 1e9  # 1 GW peak power

    # Failure injection
    enable_failures: bool = True
    failure_probability_per_operation: float = 0.001

    # Update rate
    update_rate_hz: float = 100.0


class EmulatedTDU(TemporalDisplacementUnit):
    """Hardware-accurate Temporal Displacement Unit emulation.

    Emulates a TDU with realistic:
    - Multi-phase operation timing
    - Energy consumption modeling
    - Position/time uncertainty propagation
    - Failure modes for testing

    The emulator models the displacement as a series of phases,
    each with specific timing and energy requirements.
    """

    def __init__(
        self,
        module_id: str = "emulated_tdu",
        config: TDUConfig | None = None,
    ):
        """Initialize emulated TDU.

        Args:
            module_id: Module identifier
            config: TDU configuration
        """
        super().__init__(module_id)

        self._config = config or TDUConfig()

        # Operation state
        self._phase = DisplacementPhase.IDLE
        self._phase_start_time = 0.0
        self._phase_duration = 0.0
        self._progress = 0.0

        # Calibration state
        self._calibrated = False
        self._calibration_time: datetime | None = None
        self._accumulated_drift = 0.0

        # Energy tracking
        self._energy_consumed = 0.0
        self._peak_power = 0.0

        # Simulated temporal position
        self._sim_time = 0.0

        # Fault state
        self._active_fault = TDUFaultType.NONE
        self._fault_message = ""

        # Update thread
        self._running = False
        self._update_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._abort_requested = False

        # Callbacks
        self._on_phase_change: Callable[[DisplacementPhase], None] | None = None
        self._on_fault: Callable[[TDUFaultType, str], None] | None = None

    # =========================================================================
    # HardwareModule Interface
    # =========================================================================

    def initialize(self) -> bool:
        """Initialize the TDU."""
        self._set_status(ModuleStatus.INITIALIZING)
        self._start_time = datetime.utcnow()

        # Reset state
        self._phase = DisplacementPhase.IDLE
        self._current_state = DisplacementState.IDLE
        self._active_fault = TDUFaultType.NONE
        self._energy_consumed = 0.0
        self._calibrated = False

        # Start update thread
        self._running = True
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()

        self._set_status(ModuleStatus.STANDBY)
        return True

    def shutdown(self) -> bool:
        """Shutdown the TDU."""
        # Stop any ongoing operation
        if self.is_displacing:
            self.abort_displacement()

        # Stop update thread
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=1.0)

        self._set_status(ModuleStatus.OFFLINE)
        return True

    def calibrate(self) -> bool:
        """Calibrate the TDU."""
        if self.is_displacing:
            raise CalibrationError("Cannot calibrate during displacement", self.module_id)

        self._set_status(ModuleStatus.CALIBRATING)

        # Simulate calibration sequence
        time.sleep(0.2)

        # Reset drift
        self._accumulated_drift = 0.0
        self._calibrated = True
        self._calibration_time = datetime.utcnow()

        self._set_status(ModuleStatus.STANDBY)
        return True

    def self_test(self) -> tuple[bool, list[str]]:
        """Run self-test diagnostics."""
        issues = []

        if not self._calibrated:
            issues.append("Not calibrated")

        if self._active_fault != TDUFaultType.NONE:
            issues.append(f"Active fault: {self._active_fault.value}")

        # Check calibration age
        if self._calibration_time:
            age_hours = (datetime.utcnow() - self._calibration_time).total_seconds() / 3600
            if age_hours > 24:
                issues.append(f"Calibration is {age_hours:.1f} hours old")

        return len(issues) == 0, issues

    def emergency_stop(self) -> bool:
        """Emergency stop - immediate abort."""
        self._abort_requested = True
        self._current_state = DisplacementState.ABORTED
        self._phase = DisplacementPhase.ABORTED
        self._set_status(ModuleStatus.EMERGENCY_STOP)
        return True

    def get_diagnostics(self) -> ModuleDiagnostics:
        """Get diagnostic information."""
        uptime = 0.0
        if self._start_time:
            uptime = (datetime.utcnow() - self._start_time).total_seconds()

        return ModuleDiagnostics(
            module_id=self.module_id,
            status=self._status,
            uptime_seconds=uptime,
            calibration_valid=self._calibrated,
            calibration_timestamp=self._calibration_time,
            custom_metrics={
                "phase": self._phase.value,
                "state": self._current_state.value,
                "progress": self._progress,
                "energy_consumed_joules": self._energy_consumed,
                "peak_power_watts": self._peak_power,
                "displacement_count": self._displacement_count,
                "total_displacement_seconds": self._total_displacement_seconds,
                "accumulated_drift_seconds": self._accumulated_drift,
                "active_fault": self._active_fault.value,
                "sim_time": self._sim_time,
            },
        )

    # =========================================================================
    # TemporalDisplacementUnit Interface
    # =========================================================================

    def prepare_displacement(self, request: DisplacementRequest) -> bool:
        """Prepare for displacement operation."""
        if not self._calibrated:
            raise HardwareError("TDU not calibrated", self.module_id)

        if self._active_fault != TDUFaultType.NONE:
            raise HardwareError(
                f"Cannot prepare with active fault: {self._active_fault.value}",
                self.module_id,
            )

        if self.is_displacing:
            raise HardwareError("Displacement already in progress", self.module_id)

        # Validate request
        feasible, reason, _ = self.estimate_displacement(request)
        if not feasible:
            raise HardwareError(f"Displacement not feasible: {reason}", self.module_id)

        with self._lock:
            self._active_request = request
            self._current_state = DisplacementState.PREPARING
            self._phase = DisplacementPhase.VALIDATING
            self._progress = 0.0
            self._energy_consumed = 0.0
            self._abort_requested = False

        self._set_status(ModuleStatus.ACTIVE)
        return True

    def execute_displacement(self) -> DisplacementResult:
        """Execute the prepared displacement."""
        if self._active_request is None:
            return self._create_error_result("No displacement prepared")

        request = self._active_request
        origin_stamp = ChronoStamp(
            frame_id=request.target_frame.frame_id,
            t=self._sim_time,
            clock_class="emulated",
        )

        # Run through phases
        try:
            self._execute_phases(request)
        except Exception as e:
            return self._create_error_result(str(e))

        # Check if aborted
        if self._abort_requested:
            return DisplacementResult(
                success=False,
                actual_displacement=0,
                origin_stamp=origin_stamp,
                destination_stamp=origin_stamp,
                energy_consumed_joules=self._energy_consumed,
                duration_seconds=time.monotonic() - self._phase_start_time,
                state=DisplacementState.ABORTED,
                error_message="Operation aborted",
            )

        # Calculate final position with uncertainty
        target_t = request.target_time.t
        uncertainty = self._calculate_uncertainty(request)
        actual_t = target_t + random.gauss(0, uncertainty)

        destination_stamp = ChronoStamp(
            frame_id=request.target_frame.frame_id,
            t=actual_t,
            t_uncertainty=uncertainty,
            clock_class="emulated",
        )

        # Update state
        self._sim_time = actual_t
        self._displacement_count += 1
        self._total_displacement_seconds += abs(actual_t - origin_stamp.t)
        self._active_request = None

        # Complete
        self._phase = DisplacementPhase.COMPLETE
        self._current_state = DisplacementState.COMPLETE
        self._progress = 1.0
        self._set_status(ModuleStatus.STANDBY)

        return DisplacementResult(
            success=True,
            actual_displacement=actual_t - origin_stamp.t,
            origin_stamp=origin_stamp,
            destination_stamp=destination_stamp,
            energy_consumed_joules=self._energy_consumed,
            duration_seconds=self._calculate_total_duration(request),
            state=DisplacementState.COMPLETE,
            telemetry={
                "uncertainty_seconds": uncertainty,
                "peak_power_watts": self._peak_power,
                "efficiency": self._config.energy.conversion_efficiency,
                "phases_completed": self._phase.value,
            },
        )

    def abort_displacement(self) -> bool:
        """Abort an in-progress displacement."""
        self._abort_requested = True
        return True

    def get_displacement_progress(self) -> float:
        """Get progress of current displacement (0.0 to 1.0)."""
        return self._progress

    def estimate_displacement(
        self, request: DisplacementRequest
    ) -> tuple[bool, str, dict[str, Any]]:
        """Estimate if a displacement is feasible."""
        estimates = {}

        # Check displacement magnitude
        delta_t = abs(request.delta_t)
        if delta_t > self._config.max_displacement_seconds:
            return False, f"Displacement {delta_t:.1f}s exceeds maximum", estimates

        # Estimate energy
        energy = self._estimate_energy(request)
        estimates["estimated_energy_joules"] = energy

        if energy > self._config.max_energy_joules:
            return False, f"Energy {energy:.2e}J exceeds maximum", estimates

        if energy > request.energy_budget_joules:
            return False, f"Energy {energy:.2e}J exceeds budget {request.energy_budget_joules:.2e}J", estimates

        # Estimate duration
        duration = self._calculate_total_duration(request)
        estimates["estimated_duration_seconds"] = duration

        if duration > request.max_duration_seconds:
            return False, f"Duration {duration:.1f}s exceeds maximum", estimates

        # Estimate uncertainty
        uncertainty = self._calculate_uncertainty(request)
        estimates["estimated_uncertainty_seconds"] = uncertainty

        # Estimate power
        peak_power = energy / duration if duration > 0 else float('inf')
        estimates["estimated_peak_power_watts"] = peak_power

        if peak_power > self._config.max_power_watts:
            return False, f"Peak power {peak_power:.2e}W exceeds maximum", estimates

        return True, "Displacement feasible", estimates

    # =========================================================================
    # Emulator-Specific Methods
    # =========================================================================

    def get_phase(self) -> DisplacementPhase:
        """Get current displacement phase."""
        return self._phase

    def get_fault(self) -> tuple[TDUFaultType, str]:
        """Get active fault information."""
        return self._active_fault, self._fault_message

    def clear_fault(self) -> bool:
        """Attempt to clear active fault."""
        if self._phase not in (DisplacementPhase.IDLE, DisplacementPhase.COMPLETE,
                               DisplacementPhase.ABORTED, DisplacementPhase.FAILED):
            return False

        self._active_fault = TDUFaultType.NONE
        self._fault_message = ""
        self._current_state = DisplacementState.IDLE
        self._phase = DisplacementPhase.IDLE
        self._set_status(ModuleStatus.STANDBY)
        return True

    def inject_fault(self, fault: TDUFaultType, message: str = "") -> None:
        """Inject a fault for testing."""
        self._trigger_fault(fault, message or f"Injected {fault.value}")

    def set_phase_callback(self, callback: Callable[[DisplacementPhase], None]) -> None:
        """Set callback for phase changes."""
        self._on_phase_change = callback

    def set_fault_callback(self, callback: Callable[[TDUFaultType, str], None]) -> None:
        """Set callback for fault events."""
        self._on_fault = callback

    def get_sim_time(self) -> float:
        """Get current simulated time position."""
        return self._sim_time

    def set_sim_time(self, t: float) -> None:
        """Set simulated time position (for testing)."""
        self._sim_time = t

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _update_loop(self) -> None:
        """Main update loop."""
        dt = 1.0 / self._config.update_rate_hz

        while self._running:
            try:
                self._update(dt)
                time.sleep(dt)
            except Exception:
                pass

    def _update(self, dt: float) -> None:
        """Update internal state."""
        # Accumulate calibration drift
        if self._calibration_time:
            hours = (datetime.utcnow() - self._calibration_time).total_seconds() / 3600
            self._accumulated_drift = hours * self._config.uncertainty.calibration_drift_per_hour

        # Consume standby power
        if self._status != ModuleStatus.OFFLINE:
            self._energy_consumed += self._config.energy.standby_power_watts * dt

    def _execute_phases(self, request: DisplacementRequest) -> None:
        """Execute all displacement phases."""
        phases = [
            (DisplacementPhase.VALIDATING, self._config.timing.validation_time, DisplacementState.PREPARING),
            (DisplacementPhase.CHARGING_CAPACITORS, self._config.timing.capacitor_charge_time, DisplacementState.FIELD_CHARGING),
            (DisplacementPhase.FIELD_RAMP, self._config.timing.field_ramp_time, DisplacementState.FIELD_CHARGING),
            (DisplacementPhase.FIELD_STABILIZE, self._config.timing.field_stabilize_time, DisplacementState.FIELD_CHARGING),
            (DisplacementPhase.DISPLACEMENT_INITIATE, self._config.timing.displacement_initiate_time, DisplacementState.DISPLACEMENT_ACTIVE),
            (DisplacementPhase.DISPLACEMENT_TRANSIT, self._calculate_transit_time(request), DisplacementState.DISPLACEMENT_ACTIVE),
            (DisplacementPhase.DISPLACEMENT_EMERGE, self._config.timing.displacement_emerge_time, DisplacementState.STABILIZING),
            (DisplacementPhase.POST_STABILIZE, self._config.timing.post_stabilize_time, DisplacementState.STABILIZING),
            (DisplacementPhase.COOLDOWN, self._config.timing.cooldown_time, DisplacementState.STABILIZING),
        ]

        total_duration = sum(duration for _, duration, _ in phases)
        elapsed = 0.0

        for phase, duration, state in phases:
            if self._abort_requested:
                break

            self._set_phase(phase, state)

            # Execute phase with energy consumption
            self._execute_phase(phase, duration, request)
            elapsed += duration
            self._progress = elapsed / total_duration

            # Check for random failures
            if self._config.enable_failures:
                self._check_random_failures(phase)

            if self._active_fault != TDUFaultType.NONE:
                raise HardwareError(f"Fault during {phase.value}: {self._fault_message}", self.module_id)

    def _execute_phase(self, phase: DisplacementPhase, duration: float, request: DisplacementRequest) -> None:
        """Execute a single phase with timing and energy."""
        self._phase_start_time = time.monotonic()
        self._phase_duration = duration

        # Phase-specific energy consumption
        if phase == DisplacementPhase.CHARGING_CAPACITORS:
            energy = self._config.energy.capacitor_charge_energy
            self._energy_consumed += energy
            power = energy / duration
            self._peak_power = max(self._peak_power, power)

        elif phase == DisplacementPhase.FIELD_RAMP:
            power = self._config.energy.field_maintain_power_watts * 2  # Higher during ramp
            self._energy_consumed += power * duration
            self._peak_power = max(self._peak_power, power)

        elif phase in (DisplacementPhase.FIELD_STABILIZE, DisplacementPhase.POST_STABILIZE):
            power = self._config.energy.field_maintain_power_watts
            self._energy_consumed += power * duration

        elif phase == DisplacementPhase.DISPLACEMENT_TRANSIT:
            energy = self._calculate_displacement_energy(request)
            self._energy_consumed += energy
            power = energy / duration if duration > 0 else 0
            self._peak_power = max(self._peak_power, power)

        # Simulate phase duration
        time.sleep(min(duration, 0.1))  # Cap at 100ms for responsiveness

    def _set_phase(self, phase: DisplacementPhase, state: DisplacementState) -> None:
        """Set current phase and notify callbacks."""
        self._phase = phase
        self._current_state = state

        if self._on_phase_change:
            self._on_phase_change(phase)

    def _calculate_transit_time(self, request: DisplacementRequest) -> float:
        """Calculate transit time based on displacement."""
        base = self._config.timing.displacement_transit_time_per_second
        return max(0.1, abs(request.delta_t) * base)

    def _calculate_total_duration(self, request: DisplacementRequest) -> float:
        """Calculate total operation duration."""
        timing = self._config.timing
        transit = self._calculate_transit_time(request)

        total = (
            timing.validation_time +
            timing.capacitor_charge_time +
            timing.field_ramp_time +
            timing.field_stabilize_time +
            timing.displacement_initiate_time +
            transit +
            timing.displacement_emerge_time +
            timing.post_stabilize_time +
            timing.cooldown_time
        )

        return max(total, timing.minimum_operation_time)

    def _estimate_energy(self, request: DisplacementRequest) -> float:
        """Estimate total energy for displacement."""
        energy = self._config.energy

        # Base costs
        total = energy.capacitor_charge_energy

        # Field maintenance
        total += energy.field_maintain_power_watts * self._calculate_total_duration(request)

        # Displacement energy
        total += self._calculate_displacement_energy(request)

        # Efficiency loss
        total /= energy.conversion_efficiency

        return total

    def _calculate_displacement_energy(self, request: DisplacementRequest) -> float:
        """Calculate energy for the displacement itself."""
        energy = self._config.energy
        delta_t = abs(request.delta_t)

        base = energy.base_displacement_energy
        scaling = energy.energy_per_second_displaced * delta_t

        total = base + scaling

        # Backward displacement penalty
        if request.mode == DisplacementMode.BACKWARD:
            total *= energy.backward_penalty_factor

        return total

    def _calculate_uncertainty(self, request: DisplacementRequest) -> float:
        """Calculate total timing uncertainty."""
        unc = self._config.uncertainty
        delta_t = abs(request.delta_t)

        # Base uncertainty
        total_var = unc.base_time_uncertainty_seconds ** 2

        # Uncertainty scaling with displacement
        total_var += (unc.uncertainty_per_second_displaced * delta_t) ** 2

        # Calibration drift
        total_var += self._accumulated_drift ** 2

        # Random jitter
        total_var += unc.timing_jitter_std ** 2

        return math.sqrt(total_var)

    def _trigger_fault(self, fault: TDUFaultType, message: str) -> None:
        """Trigger a fault condition."""
        self._active_fault = fault
        self._fault_message = message
        self._current_state = DisplacementState.FAILED
        self._phase = DisplacementPhase.FAILED
        self._set_status(ModuleStatus.ERROR)

        if self._on_fault:
            self._on_fault(fault, message)

    def _check_random_failures(self, phase: DisplacementPhase) -> None:
        """Check for random failures during operation."""
        if random.random() < self._config.failure_probability_per_operation:
            # Pick a fault type based on phase
            if phase in (DisplacementPhase.FIELD_RAMP, DisplacementPhase.FIELD_STABILIZE):
                self._trigger_fault(TDUFaultType.FIELD_INSTABILITY, "Random field instability")
            elif phase == DisplacementPhase.DISPLACEMENT_TRANSIT:
                self._trigger_fault(TDUFaultType.TIMING_ERROR, "Random timing error")
            else:
                self._trigger_fault(TDUFaultType.COMMUNICATION_ERROR, "Random communication error")

    def _create_error_result(self, message: str) -> DisplacementResult:
        """Create an error result."""
        return DisplacementResult(
            success=False,
            actual_displacement=0,
            origin_stamp=ChronoStamp(frame_id="error", t=0),
            destination_stamp=ChronoStamp(frame_id="error", t=0),
            energy_consumed_joules=self._energy_consumed,
            duration_seconds=0,
            state=DisplacementState.FAILED,
            error_message=message,
        )
