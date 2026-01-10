#!/usr/bin/env python3
"""Field Generator Node - ROS2 node for electromagnetic field control.

This node provides:
- Field status publishing on /field/status topic
- Field control via /field/set_field service
- Thermal monitoring
- Safety interlocks
"""

from __future__ import annotations

import time
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

from std_msgs.msg import Float64

# TimeOS imports
try:
    from timeos.hardware.drivers.emulated import (
        EmulatedFieldGenerator,
        EmulatorConfig,
    )
    from timeos.hardware.field_generator import (
        FieldConfiguration,
        FieldType,
        FieldGeometry,
    )
    from timeos.physics.spacetime import Vector3
    TIMEOS_AVAILABLE = True
except ImportError:
    TIMEOS_AVAILABLE = False

# Service imports
from timeos_ros.srv import SetField, GetStatus


class FieldGeneratorNode(Node):
    """ROS2 node for field generator control.

    Publishes:
        /field/strength (Float64): Current field strength in Tesla
        /field/temperature (Float64): Current temperature in Kelvin
        /field/power (Float64): Current power consumption in Watts

    Services:
        /field/set_field (SetField): Set target field
        /field/get_status (GetStatus): Get detailed status
    """

    def __init__(self):
        super().__init__("field_generator_node")

        # Parameters
        self.declare_parameter("max_field_tesla", 10.0)
        self.declare_parameter("ramp_rate_tesla_per_second", 0.1)
        self.declare_parameter("operating_temp_kelvin", 4.2)
        self.declare_parameter("publish_rate_hz", 10.0)
        self.declare_parameter("use_emulation", True)

        max_field = self.get_parameter("max_field_tesla").value
        ramp_rate = self.get_parameter("ramp_rate_tesla_per_second").value
        operating_temp = self.get_parameter("operating_temp_kelvin").value
        publish_rate = self.get_parameter("publish_rate_hz").value
        use_emulation = self.get_parameter("use_emulation").value

        # Initialize field generator
        if TIMEOS_AVAILABLE and use_emulation:
            config = EmulatorConfig()
            config.magnet.max_field_tesla = max_field
            config.thermal.base_temperature = operating_temp

            self._generator = EmulatedFieldGenerator(
                module_id="field_gen_ros",
                config=config,
            )
            self._generator.initialize()
            self.get_logger().info("Emulated field generator initialized")
        else:
            self._generator = None
            self.get_logger().warn("Running in stub mode (no emulation)")

        # Publishers
        self._strength_pub = self.create_publisher(Float64, "/field/strength", 10)
        self._temp_pub = self.create_publisher(Float64, "/field/temperature", 10)
        self._power_pub = self.create_publisher(Float64, "/field/power", 10)

        # Services
        self._set_field_srv = self.create_service(
            SetField,
            "/field/set_field",
            self._handle_set_field,
        )

        self._get_status_srv = self.create_service(
            GetStatus,
            "/field/get_status",
            self._handle_get_status,
        )

        # Status timer
        self._timer = self.create_timer(1.0 / publish_rate, self._publish_status)

        # State
        self._target_field = 0.0
        self._last_update = time.monotonic()

        self.get_logger().info("Field generator node started")

    def _publish_status(self):
        """Publish current field status."""
        if not self._generator:
            return

        # Update emulator
        now = time.monotonic()
        dt = now - self._last_update
        self._last_update = now
        self._generator.update(dt)

        # Get state
        state = self._generator.get_field_state()
        thermal = self._generator.get_thermal_status()

        # Publish
        strength_msg = Float64()
        strength_msg.data = state.actual_b_tesla
        self._strength_pub.publish(strength_msg)

        temp_msg = Float64()
        temp_msg.data = thermal.temperature_kelvin
        self._temp_pub.publish(temp_msg)

        power_msg = Float64()
        power_msg.data = state.power_watts
        self._power_pub.publish(power_msg)

    def _handle_set_field(
        self,
        request: SetField.Request,
        response: SetField.Response,
    ) -> SetField.Response:
        """Handle SetField service request."""
        try:
            if not self._generator:
                response.accepted = False
                response.error_message = "Generator not available"
                return response

            target = request.target_tesla

            # Validate
            max_field = self.get_parameter("max_field_tesla").value
            if target < 0 or target > max_field:
                response.accepted = False
                response.error_message = f"Target must be 0-{max_field} T"
                return response

            # Configure and ramp
            if target > 0:
                config = FieldConfiguration(
                    field_type=FieldType.STATIC_MAGNETIC,
                    geometry=FieldGeometry.SOLENOID,
                    b_field_tesla=target,
                    direction=Vector3(0, 0, 1),
                )
                self._generator.configure(config)

            rate = request.ramp_rate if request.ramp_rate > 0 else None
            self._generator.ramp_to(target, rate)
            self._target_field = target

            # Get current state
            state = self._generator.get_field_state()
            ramp_state = self._generator.get_ramp_state()

            response.accepted = True
            response.current_tesla = state.actual_b_tesla
            response.ramp_state = ramp_state.state if ramp_state else "unknown"

            # Estimate duration
            if rate:
                delta = abs(target - state.actual_b_tesla)
                response.estimated_duration = delta / rate
            else:
                response.estimated_duration = 0.0

            self.get_logger().info(f"Field target set to {target} T")

        except Exception as e:
            response.accepted = False
            response.error_message = str(e)
            self.get_logger().error(f"Failed to set field: {e}")

        return response

    def _handle_get_status(
        self,
        request: GetStatus.Request,
        response: GetStatus.Response,
    ) -> GetStatus.Response:
        """Handle GetStatus service request."""
        try:
            response.timestamp = time.time()

            if not self._generator:
                response.system_state = "unavailable"
                response.safe_to_operate = False
                return response

            state = self._generator.get_field_state()
            thermal = self._generator.get_thermal_status()
            ramp_state = self._generator.get_ramp_state()
            fault_type, fault_msg = self._generator.get_fault()

            # Module state
            if ramp_state and ramp_state.state != "idle":
                response.module_state = ramp_state.state
            elif state.active:
                response.module_state = "active"
            else:
                response.module_state = "standby"

            response.system_state = response.module_state

            # Safety
            response.safe_to_operate = thermal.quench_risk < 0.5

            # Faults
            if fault_msg:
                response.faults = [fault_msg]

            # Warnings
            if thermal.quench_risk > 0.1:
                response.warnings.append(
                    f"Quench risk: {thermal.quench_risk * 100:.1f}%"
                )

            # Detailed status
            if request.include_diagnostics:
                response.status_keys = [
                    "field_tesla",
                    "target_tesla",
                    "temperature_kelvin",
                    "power_watts",
                    "quench_risk",
                    "ramp_state",
                    "stability",
                ]
                response.status_values = [
                    f"{state.actual_b_tesla:.4f}",
                    f"{self._target_field:.4f}",
                    f"{thermal.temperature_kelvin:.2f}",
                    f"{state.power_watts:.1f}",
                    f"{thermal.quench_risk:.3f}",
                    ramp_state.state if ramp_state else "unknown",
                    f"{state.stability:.3f}",
                ]

        except Exception as e:
            response.system_state = "error"
            response.faults = [str(e)]
            self.get_logger().error(f"Failed to get status: {e}")

        return response

    def destroy_node(self):
        """Clean shutdown."""
        if self._generator:
            self._generator.shutdown()
        super().destroy_node()


def main(args=None):
    """Run the field generator node."""
    rclpy.init(args=args)

    node = FieldGeneratorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
