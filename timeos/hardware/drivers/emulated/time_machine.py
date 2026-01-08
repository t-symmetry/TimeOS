"""Emulated Time Machine - Integrated system combining all emulated modules.

This module provides a complete EmulatedTimeMachine that:
- Integrates field generator, TDU, sensors, and thermal systems
- Uses ROS-compatible pub/sub and service interfaces
- Can be converted to ROS2 nodes with minimal changes

The architecture maps cleanly to ROS2:
- Each subsystem publishes status on its own topic
- Displacement is exposed as a service
- Parameters control system behavior
- Timers drive periodic status updates
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from .interfaces import (
    NodeBase,
    MessageBroker,
    ServiceRegistry,
    ParameterServer,
    Publisher,
    Service,
    Header,
    FieldStatus,
    TDUStatus,
    ThermalStatus,
    SensorReading,
    SafetyStatus,
    SystemStatus,
    DisplacementRequest,
    DisplacementResponse,
)
from .field_generator import (
    EmulatedFieldGenerator,
    EmulatorConfig,
    RampState,
    FaultType as FieldFaultType,
)
from .temporal_displacement import (
    EmulatedTDU,
    TDUConfig,
    DisplacementPhase,
    TDUFaultType,
)
from .thermal_model import ThermalModel, ThermalState, ThermalConfig
from .sensors import (
    SensorArray,
    create_field_generator_sensors,
    create_tdu_sensors,
    SensorStatus,
)
from .failure_injection import FailureInjector, FailureScenario
from timeos.hardware.field_generator import FieldConfiguration, FieldType, FieldGeometry, Vector3
from timeos.hardware.temporal_displacement import (
    DisplacementRequest as TDUDisplacementRequest,
    DisplacementMode,
    DisplacementState,
)
from timeos.msgs import ChronoStamp, TemporalFrame


class MachineState(Enum):
    """Overall time machine state."""

    OFFLINE = "offline"
    INITIALIZING = "initializing"
    STANDBY = "standby"
    FIELD_RAMPING = "field_ramping"
    FIELD_READY = "field_ready"
    DISPLACING = "displacing"
    RETURNING = "returning"
    EMERGENCY_STOP = "emergency_stop"
    FAULT = "fault"


@dataclass
class MachineConfig:
    """Configuration for the emulated time machine.

    These parameters would be ROS2 parameters in a ROS deployment.
    """

    # Field generator settings
    max_field_tesla: float = 10.0
    field_ramp_rate_tesla_per_second: float = 0.1

    # TDU settings
    max_displacement_years: float = 100.0
    displacement_energy_scale: float = 1e12  # Joules per year

    # Thermal settings
    operating_temp_kelvin: float = 4.2
    quench_temp_kelvin: float = 9.2
    cooling_power_watts: float = 50.0

    # Safety settings
    max_quench_risk: float = 0.3  # Interlock threshold
    warning_quench_risk: float = 0.15

    # Timing
    status_publish_rate_hz: float = 10.0
    sensor_sample_rate_hz: float = 100.0

    # Failure injection (for testing)
    enable_failure_injection: bool = False


class FieldGeneratorNode(NodeBase):
    """ROS-compatible node for field generator control.

    In ROS2, this would be a separate node:
    ```python
    class FieldGeneratorNode(Node):
        def __init__(self):
            super().__init__('field_generator_node')
            self.publisher = self.create_publisher(FieldStatus, 'field_status', 10)
    ```
    """

    def __init__(
        self,
        config: MachineConfig,
        broker: MessageBroker,
        services: ServiceRegistry,
        params: ParameterServer,
    ):
        super().__init__("field_generator", broker, services, params)

        self._config = config

        # Create emulator config from machine config
        emulator_config = EmulatorConfig()
        emulator_config.magnet.max_field_tesla = config.max_field_tesla
        emulator_config.thermal.base_temperature = config.operating_temp_kelvin
        emulator_config.thermal.critical_temperature = config.quench_temp_kelvin
        emulator_config.thermal.cooling_capacity_watts = config.cooling_power_watts

        # Create the emulated hardware
        self._generator = EmulatedFieldGenerator(
            module_id="field_gen_1",
            config=emulator_config,
        )

        # Sensors
        self._sensors = create_field_generator_sensors()

        # Publisher for status updates
        self._status_pub = self.create_publisher(
            FieldStatus, "status", queue_size=10
        )

        # Declare parameters
        self.declare_parameter("max_field_tesla", config.max_field_tesla)
        self.declare_parameter("ramp_rate", config.field_ramp_rate_tesla_per_second)

        # Internal state
        self._target_field = 0.0
        self._initialized = False
        self._last_update = time.monotonic()

    def initialize(self) -> bool:
        """Initialize the field generator hardware."""
        if self._initialized:
            return True
        self._initialized = self._generator.initialize()
        return self._initialized

    def update(self, dt: float) -> FieldStatus:
        """Get current field generator state and publish status.

        The EmulatedFieldGenerator runs its own background thread,
        so we just read its current state.

        Args:
            dt: Time step in seconds (unused - generator self-updates)

        Returns:
            Current field status
        """
        # Get current state from generator (it updates itself internally)
        field_state = self._generator.get_field_state()
        thermal_status = self._generator.get_thermal_status()
        ramp_state = self._generator.get_ramp_state()
        fault_type, fault_msg = self._generator.get_fault()

        # Update sensors with true values
        self._sensors.sensors["mag_main"].set_true_value(field_state.actual_b_tesla)
        self._sensors.sensors["mag_backup"].set_true_value(field_state.actual_b_tesla)
        self._sensors.sensors["temp_coil_1"].set_true_value(thermal_status.temperature_kelvin)
        self._sensors.sensors["temp_helium"].set_true_value(thermal_status.temperature_kelvin)
        self._sensors.sensors["power_main"].set_true_value(field_state.power_watts)

        # Read from sensors (adds noise)
        temp = thermal_status.temperature_kelvin
        measured_field = self._sensors.sensors["mag_main"].read(temp)
        measured_temp = self._sensors.sensors["temp_coil_1"].read(temp)
        measured_power = self._sensors.sensors["power_main"].read(temp)

        # Build status message
        status = FieldStatus(
            header=Header.now("field_generator"),
            active=field_state.active,
            field_tesla=measured_field,
            target_tesla=self._target_field,
            temperature_kelvin=measured_temp,
            quench_risk=thermal_status.quench_risk,
            power_watts=measured_power,
            stability=field_state.stability,
            ramp_state=ramp_state.value,
            fault=fault_msg if fault_type != FieldFaultType.NONE else "",
        )

        # Publish
        self._status_pub.publish(status)

        return status

    def set_target_field(self, tesla: float) -> bool:
        """Set target field strength.

        Args:
            tesla: Target field in Tesla

        Returns:
            True if target was accepted
        """
        if tesla < 0 or tesla > self._config.max_field_tesla:
            return False

        self._target_field = tesla

        # Configure and ramp to target
        if tesla > 0:
            config = FieldConfiguration(
                field_type=FieldType.STATIC,
                geometry=FieldGeometry.SOLENOID,
                b_field_tesla=tesla,
                direction=Vector3(0, 0, 1),
            )
            self._generator.configure(config)
            return self._generator.ramp_to(tesla)
        else:
            return self._generator.ramp_to(0.0)

    def activate(self) -> bool:
        """Activate the field generator (energize)."""
        if self._target_field > 0:
            return self._generator.energize()
        return False

    def deactivate(self) -> None:
        """Deactivate the field generator (de-energize)."""
        self._generator.de_energize()

    def emergency_stop(self) -> None:
        """Emergency stop."""
        self._generator.emergency_stop()
        self._target_field = 0.0

    def get_thermal_status(self):
        """Get the thermal status."""
        return self._generator.get_thermal_status()

    def get_generator(self) -> EmulatedFieldGenerator:
        """Get the underlying generator."""
        return self._generator

    def shutdown(self) -> None:
        """Shutdown the field generator."""
        self._generator.shutdown()
        self._initialized = False


class TDUNode(NodeBase):
    """ROS-compatible node for Temporal Displacement Unit control.

    In ROS2, this would be a separate node exposing a displacement service.
    """

    def __init__(
        self,
        config: MachineConfig,
        broker: MessageBroker,
        services: ServiceRegistry,
        params: ParameterServer,
    ):
        super().__init__("tdu", broker, services, params)

        self._config = config

        # Create TDU config from machine config
        tdu_config = TDUConfig()
        tdu_config.max_displacement_seconds = config.max_displacement_years * 365.25 * 24 * 3600

        # Create the emulated TDU
        self._tdu = EmulatedTDU(
            module_id="tdu_1",
            config=tdu_config,
        )

        # Sensors
        self._sensors = create_tdu_sensors()

        # Publisher for status updates
        self._status_pub = self.create_publisher(
            TDUStatus, "status", queue_size=10
        )

        # Service for displacement
        self._displace_srv = self.create_service(
            (DisplacementRequest, DisplacementResponse),
            "displace",
            self._handle_displace,
        )

        # Declare parameters
        self.declare_parameter("max_displacement_years", config.max_displacement_years)
        self.declare_parameter("energy_scale", config.displacement_energy_scale)

        # Internal state
        self._initialized = False
        self._last_result = None

    def initialize(self) -> bool:
        """Initialize the TDU hardware."""
        if self._initialized:
            return True
        self._initialized = self._tdu.initialize()
        if self._initialized:
            self._tdu.calibrate()
        return self._initialized

    def update(self, dt: float) -> TDUStatus:
        """Get current TDU state and publish status.

        The EmulatedTDU runs its own background thread,
        so we just read its current state.

        Args:
            dt: Time step in seconds (unused - TDU self-updates)

        Returns:
            Current TDU status
        """
        # Get current state from TDU
        phase = self._tdu.get_phase()
        progress = self._tdu.get_displacement_progress()
        sim_time = self._tdu.get_sim_time()
        fault_type, fault_msg = self._tdu.get_fault()
        diagnostics = self._tdu.get_diagnostics()

        # Get energy from diagnostics
        energy = diagnostics.custom_metrics.get("energy_consumed_joules", 0.0)

        # Determine state string from phase
        if phase == DisplacementPhase.IDLE:
            state_str = "idle"
        elif phase == DisplacementPhase.COMPLETE:
            state_str = "complete"
        elif phase in (DisplacementPhase.ABORTED, DisplacementPhase.FAILED):
            state_str = phase.value
        elif phase in (DisplacementPhase.DISPLACEMENT_INITIATE,
                       DisplacementPhase.DISPLACEMENT_TRANSIT,
                       DisplacementPhase.DISPLACEMENT_EMERGE):
            state_str = "displacing"
        else:
            state_str = "preparing"

        # Build status message
        status = TDUStatus(
            header=Header.now("tdu"),
            state=state_str,
            phase=phase.value,
            progress=progress,
            sim_time=sim_time,
            energy_consumed_joules=energy,
            fault=fault_msg if fault_type != TDUFaultType.NONE else "",
        )

        # Publish
        self._status_pub.publish(status)

        return status

    def _handle_displace(self, request: DisplacementRequest) -> DisplacementResponse:
        """Handle displacement request (service callback).

        In ROS2, this would be the service callback:
        ```python
        def handle_displace(self, request, response):
            # ... implementation
            return response
        ```
        """
        # Validate request
        max_seconds = self._config.max_displacement_years * 365.25 * 24 * 3600
        if abs(request.target_time) > max_seconds:
            return DisplacementResponse(
                success=False,
                error_message=f"Displacement exceeds maximum range of {self._config.max_displacement_years} years",
            )

        # Create TDU displacement request
        mode = DisplacementMode.BACKWARD if request.mode == "backward" else DisplacementMode.FORWARD
        tdu_request = TDUDisplacementRequest(
            target_time=ChronoStamp(t=request.target_time, frame_id=request.frame_id),
            target_frame=TemporalFrame(frame_id=request.frame_id),
            delta_t=request.target_time,  # Displacement amount
            mode=mode,
            energy_budget_joules=request.energy_budget_joules,
            max_duration_seconds=request.max_duration_seconds,
        )

        # Start displacement
        origin_time = self._tdu.get_sim_time()
        start_wall = time.monotonic()

        try:
            self._tdu.prepare_displacement(tdu_request)
            result = self._tdu.execute_displacement()
        except Exception as e:
            return DisplacementResponse(
                success=False,
                error_message=str(e),
            )

        self._last_result = result

        return DisplacementResponse(
            success=result.success,
            actual_displacement=result.actual_displacement,
            origin_time=origin_time,
            destination_time=result.destination_stamp.t if result.success else origin_time,
            energy_consumed_joules=result.energy_consumed_joules,
            duration_seconds=result.duration_seconds,
            error_message=result.error_message or "",
        )

    def start_displacement(
        self,
        target_time: float,
        mode: str = "backward",
        energy_budget: float = 1e12,
    ) -> bool:
        """Start a displacement operation.

        Args:
            target_time: Target temporal displacement in seconds
            mode: Displacement mode (backward, forward, lateral)
            energy_budget: Maximum energy in Joules

        Returns:
            True if displacement started
        """
        disp_mode = DisplacementMode.BACKWARD if mode == "backward" else DisplacementMode.FORWARD
        tdu_request = TDUDisplacementRequest(
            target_time=ChronoStamp(t=target_time, frame_id="origin"),
            target_frame=TemporalFrame(frame_id="origin"),
            delta_t=target_time,
            mode=disp_mode,
            energy_budget_joules=energy_budget,
            max_duration_seconds=60.0,
        )

        try:
            self._tdu.prepare_displacement(tdu_request)
            return True
        except Exception:
            return False

    def execute(self):
        """Execute a prepared displacement."""
        return self._tdu.execute_displacement()

    def abort(self) -> None:
        """Abort current displacement."""
        self._tdu.abort_displacement()

    def is_complete(self) -> bool:
        """Check if displacement is complete."""
        phase = self._tdu.get_phase()
        return phase in (DisplacementPhase.IDLE, DisplacementPhase.COMPLETE,
                        DisplacementPhase.ABORTED, DisplacementPhase.FAILED)

    def get_tdu(self) -> EmulatedTDU:
        """Get the underlying TDU."""
        return self._tdu

    def shutdown(self) -> None:
        """Shutdown the TDU."""
        self._tdu.shutdown()
        self._initialized = False


class SafetyMonitor(NodeBase):
    """ROS-compatible node for safety monitoring.

    Monitors all subsystems and enforces safety interlocks.
    """

    def __init__(
        self,
        config: MachineConfig,
        field_node: FieldGeneratorNode,
        tdu_node: TDUNode,
        broker: MessageBroker,
        services: ServiceRegistry,
        params: ParameterServer,
    ):
        super().__init__("safety_monitor", broker, services, params)

        self._config = config
        self._field_node = field_node
        self._tdu_node = tdu_node

        # Publisher for safety status
        self._status_pub = self.create_publisher(
            SafetyStatus, "status", queue_size=10
        )

        # State
        self._interlocks: list[str] = []
        self._faults: list[str] = []
        self._estop_active = False

        # Declare parameters
        self.declare_parameter("max_quench_risk", config.max_quench_risk)
        self.declare_parameter("warning_quench_risk", config.warning_quench_risk)

    def update(self, dt: float) -> SafetyStatus:
        """Update safety status.

        Args:
            dt: Time step in seconds

        Returns:
            Current safety status
        """
        self._interlocks.clear()
        self._faults.clear()

        # Check thermal status
        thermal_status = self._field_node.get_thermal_status()
        quench_risk = thermal_status.quench_risk

        if quench_risk > self._config.max_quench_risk:
            self._interlocks.append("QUENCH_RISK_HIGH")

        if thermal_status.state == ThermalState.QUENCH:
            self._faults.append("QUENCH_DETECTED")
            self._interlocks.append("QUENCH_INTERLOCK")

        # Check field generator faults
        field_fault, field_msg = self._field_node.get_generator().get_fault()
        if field_fault != FieldFaultType.NONE:
            self._faults.append(f"FIELD: {field_msg}")

        # Check TDU faults
        tdu_fault, tdu_msg = self._tdu_node.get_tdu().get_fault()
        if tdu_fault != TDUFaultType.NONE:
            self._faults.append(f"TDU: {tdu_msg}")

        # Determine safety level
        if self._estop_active or self._faults:
            level = "emergency"
        elif self._interlocks:
            level = "critical"
        elif quench_risk > self._config.warning_quench_risk:
            level = "warning"
        else:
            level = "nominal"

        # Build status
        status = SafetyStatus(
            header=Header.now("safety_monitor"),
            level=level,
            interlocks_engaged=list(self._interlocks),
            active_faults=list(self._faults),
            estop_active=self._estop_active,
        )

        # Publish
        self._status_pub.publish(status)

        return status

    def emergency_stop(self) -> None:
        """Activate emergency stop."""
        self._estop_active = True
        self._field_node.emergency_stop()
        self._tdu_node.abort()
        self.get_logger().error("EMERGENCY STOP ACTIVATED")

    def reset_estop(self) -> bool:
        """Reset emergency stop.

        Returns:
            True if reset was successful
        """
        if self._faults:
            return False

        self._estop_active = False
        self.get_logger().info("Emergency stop reset")
        return True

    def is_safe_to_operate(self) -> bool:
        """Check if system is safe to operate."""
        return not self._estop_active and not self._interlocks and not self._faults

    def get_interlocks(self) -> list[str]:
        """Get list of active interlocks."""
        return list(self._interlocks)

    def get_faults(self) -> list[str]:
        """Get list of active faults."""
        return list(self._faults)


class EmulatedTimeMachine:
    """Complete emulated time machine integrating all subsystems.

    This is the main entry point for the emulated hardware. It:
    - Creates and manages all subsystem nodes
    - Provides a unified control interface
    - Runs the main update loop
    - Handles failure injection for testing

    Migration to ROS2:
    - Each subsystem node becomes a standalone ROS2 node
    - The MessageBroker is replaced by ROS2 DDS
    - The ServiceRegistry is replaced by ROS2 service discovery
    - The update loop is replaced by ROS2 timers and executors
    """

    def __init__(self, config: MachineConfig | None = None):
        """Initialize the emulated time machine.

        Args:
            config: Machine configuration (uses defaults if None)
        """
        self._config = config or MachineConfig()

        # Create shared infrastructure
        self._broker = MessageBroker()
        self._services = ServiceRegistry()
        self._params = ParameterServer()

        # Load config into parameters
        self._params.load_from_dict({
            "max_field_tesla": self._config.max_field_tesla,
            "ramp_rate": self._config.field_ramp_rate_tesla_per_second,
            "max_displacement_years": self._config.max_displacement_years,
            "energy_scale": self._config.displacement_energy_scale,
            "operating_temp": self._config.operating_temp_kelvin,
            "quench_temp": self._config.quench_temp_kelvin,
            "cooling_power": self._config.cooling_power_watts,
        })

        # Create subsystem nodes
        self._field_node = FieldGeneratorNode(
            self._config, self._broker, self._services, self._params
        )
        self._tdu_node = TDUNode(
            self._config, self._broker, self._services, self._params
        )
        self._safety_node = SafetyMonitor(
            self._config,
            self._field_node,
            self._tdu_node,
            self._broker,
            self._services,
            self._params,
        )

        # System status publisher
        self._status_pub = self._broker.create_publisher(
            "time_machine/status", SystemStatus
        )

        # Machine state
        self._state = MachineState.OFFLINE
        self._running = False
        self._update_thread: threading.Thread | None = None
        self._last_update = time.monotonic()

        # Failure injection
        self._failure_injector: FailureInjector | None = None
        if self._config.enable_failure_injection:
            self._failure_injector = FailureInjector()

        # Callbacks for state changes
        self._state_callbacks: list[Callable[[MachineState], None]] = []
        self._status_callbacks: list[Callable[[SystemStatus], None]] = []

    def initialize(self) -> bool:
        """Initialize the time machine.

        Returns:
            True if initialization succeeded
        """
        self._state = MachineState.INITIALIZING
        self._notify_state_change()

        # Initialize subsystem hardware
        if not self._field_node.initialize():
            self._state = MachineState.FAULT
            self._notify_state_change()
            return False

        if not self._tdu_node.initialize():
            self._state = MachineState.FAULT
            self._notify_state_change()
            return False

        # Start subsystem nodes (for pub/sub)
        self._field_node.start()
        self._tdu_node.start()
        self._safety_node.start()

        # Initial safety check
        self._safety_node.update(0.0)  # Update safety status
        if not self._safety_node.is_safe_to_operate():
            self._state = MachineState.FAULT
            self._notify_state_change()
            return False

        self._state = MachineState.STANDBY
        self._notify_state_change()
        return True

    def start(self) -> None:
        """Start the update loop in a background thread."""
        if self._running:
            return

        self._running = True
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()

    def stop(self) -> None:
        """Stop the update loop."""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=1.0)

        # Stop pub/sub nodes
        self._field_node.stop()
        self._tdu_node.stop()
        self._safety_node.stop()

        # Shutdown hardware
        self._field_node.shutdown()
        self._tdu_node.shutdown()

        self._state = MachineState.OFFLINE
        self._notify_state_change()

    def _update_loop(self) -> None:
        """Main update loop (runs in background thread)."""
        update_interval = 1.0 / self._config.status_publish_rate_hz

        while self._running:
            now = time.monotonic()
            dt = now - self._last_update
            self._last_update = now

            try:
                self._update(dt)
            except Exception as e:
                print(f"[ERROR] Update failed: {e}")

            # Sleep to maintain rate
            elapsed = time.monotonic() - now
            if elapsed < update_interval:
                time.sleep(update_interval - elapsed)

    def _update(self, dt: float) -> None:
        """Update all subsystems.

        Args:
            dt: Time step in seconds
        """
        # Apply failure injection if enabled
        if self._failure_injector:
            self._failure_injector.update(dt)
            self._apply_failures()

        # Update subsystems
        field_status = self._field_node.update(dt)
        tdu_status = self._tdu_node.update(dt)
        safety_status = self._safety_node.update(dt)
        thermal_status = self._get_thermal_status()

        # Update machine state based on subsystem states
        self._update_state(field_status, tdu_status, safety_status)

        # Build and publish system status
        status = SystemStatus(
            header=Header.now("time_machine"),
            initialized=self._state != MachineState.OFFLINE,
            current_time=time.time(),
            anchor_time=None,  # TODO: Track anchor
            frame_id="origin",
            field_gen=field_status,
            tdu=tdu_status,
            thermal=thermal_status,
            safety=safety_status,
        )

        self._status_pub.publish(status)
        self._notify_status(status)

    def _get_thermal_status(self) -> ThermalStatus:
        """Get thermal status from field generator."""
        thermal_status = self._field_node.get_thermal_status()
        return ThermalStatus(
            header=Header.now("thermal"),
            temperature_kelvin=thermal_status.temperature_kelvin,
            state=thermal_status.state.value,
            quench_risk=thermal_status.quench_risk,
            cooling_load_watts=thermal_status.cooling_load_watts,
            cooling_headroom_watts=self._config.cooling_power_watts,
            time_to_quench_seconds=thermal_status.time_to_quench,
        )

    def _update_state(
        self,
        field: FieldStatus,
        tdu: TDUStatus,
        safety: SafetyStatus,
    ) -> None:
        """Update machine state based on subsystem status."""
        old_state = self._state

        if safety.estop_active:
            self._state = MachineState.EMERGENCY_STOP
        elif safety.active_faults:
            self._state = MachineState.FAULT
        elif tdu.state == "displacing":
            self._state = MachineState.DISPLACING
        elif tdu.state == "returning":
            self._state = MachineState.RETURNING
        elif field.ramp_state in ("ramping_up", "ramping_down"):
            self._state = MachineState.FIELD_RAMPING
        elif field.active and abs(field.field_tesla - field.target_tesla) < 0.001:
            self._state = MachineState.FIELD_READY
        else:
            self._state = MachineState.STANDBY

        if self._state != old_state:
            self._notify_state_change()

    def _apply_failures(self) -> None:
        """Apply any triggered failures to subsystems."""
        if not self._failure_injector:
            return

        failures = self._failure_injector.get_active_failures()
        for failure in failures:
            if failure.target == "field_generator":
                self._field_node.get_generator().inject_fault(
                    FieldFaultType.COMMUNICATION_ERROR,
                    failure.effect
                )
            elif failure.target == "tdu":
                self._tdu_node.get_tdu().inject_fault(
                    TDUFaultType.COMMUNICATION_ERROR,
                    failure.effect
                )

    # =========================================================================
    # Public Control Interface
    # =========================================================================

    def set_field(self, tesla: float) -> bool:
        """Set target magnetic field strength.

        Args:
            tesla: Target field in Tesla

        Returns:
            True if target was accepted
        """
        if not self._safety_node.is_safe_to_operate():
            return False

        if not self._field_node.get_generator().is_active():
            self._field_node.activate()

        return self._field_node.set_target_field(tesla)

    def displace(
        self,
        target_seconds: float,
        mode: str = "backward",
        energy_budget: float = 1e12,
    ) -> DisplacementResponse:
        """Perform temporal displacement.

        Args:
            target_seconds: Target displacement in seconds
            mode: Displacement mode
            energy_budget: Maximum energy in Joules

        Returns:
            Displacement response
        """
        # Check safety
        self._safety_node.update(0.0)
        if not self._safety_node.is_safe_to_operate():
            return DisplacementResponse(
                success=False,
                error_message="Safety interlock active",
            )

        # Check field is ready
        field_state = self._field_node.get_generator().get_field_state()
        if not field_state.active or field_state.actual_b_tesla < 1.0:
            return DisplacementResponse(
                success=False,
                error_message="Field not ready (minimum 1T required)",
            )

        # Create request and call service
        request = DisplacementRequest(
            target_time=target_seconds,
            mode=mode,
            energy_budget_joules=energy_budget,
            max_duration_seconds=60.0,
        )

        # Get service client
        client = self._services.create_client(
            "tdu/displace",
            DisplacementRequest,
            DisplacementResponse,
        )

        if not client:
            return DisplacementResponse(
                success=False,
                error_message="Displacement service not available",
            )

        return client.call(request)

    def emergency_stop(self) -> None:
        """Activate emergency stop."""
        self._safety_node.emergency_stop()

    def reset(self) -> bool:
        """Reset from emergency stop or fault.

        Returns:
            True if reset succeeded
        """
        return self._safety_node.reset_estop()

    def get_state(self) -> MachineState:
        """Get current machine state."""
        return self._state

    def get_status(self) -> dict[str, Any]:
        """Get complete system status as dictionary."""
        field_state = self._field_node.get_generator().get_field_state()
        ramp_state = self._field_node.get_generator().get_ramp_state()
        tdu = self._tdu_node.get_tdu()
        thermal_status = self._field_node.get_thermal_status()

        return {
            "state": self._state.value,
            "field": {
                "active": field_state.active,
                "field_tesla": field_state.actual_b_tesla,
                "target_tesla": self._field_node._target_field,
                "ramp_state": ramp_state.value,
                "power_watts": field_state.power_watts,
            },
            "thermal": {
                "temperature_kelvin": thermal_status.temperature_kelvin,
                "state": thermal_status.state.value,
                "quench_risk": thermal_status.quench_risk,
            },
            "tdu": {
                "state": tdu.get_phase().value,
                "phase": tdu.get_phase().value,
                "progress": tdu.get_displacement_progress(),
            },
            "safety": {
                "safe_to_operate": self._safety_node.is_safe_to_operate(),
                "estop_active": self._safety_node._estop_active,
                "interlocks": self._safety_node.get_interlocks(),
                "faults": self._safety_node.get_faults(),
            },
        }

    # =========================================================================
    # Callbacks
    # =========================================================================

    def add_state_callback(self, callback: Callable[[MachineState], None]) -> None:
        """Add callback for state changes."""
        self._state_callbacks.append(callback)

    def add_status_callback(self, callback: Callable[[SystemStatus], None]) -> None:
        """Add callback for status updates."""
        self._status_callbacks.append(callback)

    def _notify_state_change(self) -> None:
        """Notify callbacks of state change."""
        for callback in self._state_callbacks:
            try:
                callback(self._state)
            except Exception:
                pass

    def _notify_status(self, status: SystemStatus) -> None:
        """Notify callbacks of status update."""
        for callback in self._status_callbacks:
            try:
                callback(status)
            except Exception:
                pass

    # =========================================================================
    # Failure Injection (for testing)
    # =========================================================================

    def inject_failure(self, scenario: str | FailureScenario) -> bool:
        """Inject a failure scenario for testing.

        Args:
            scenario: Failure scenario name or object

        Returns:
            True if failure was injected
        """
        if not self._failure_injector:
            self._failure_injector = FailureInjector()

        if isinstance(scenario, str):
            return self._failure_injector.trigger_scenario(scenario)
        else:
            self._failure_injector.add_scenario(scenario)
            return self._failure_injector.trigger_scenario(scenario.name)

    def clear_failures(self) -> None:
        """Clear all injected failures."""
        if self._failure_injector:
            self._failure_injector.clear_all()

    # =========================================================================
    # Message Broker Access (for external subscribers)
    # =========================================================================

    def get_broker(self) -> MessageBroker:
        """Get the message broker for external subscribers."""
        return self._broker

    def get_services(self) -> ServiceRegistry:
        """Get the service registry."""
        return self._services

    def get_params(self) -> ParameterServer:
        """Get the parameter server."""
        return self._params
