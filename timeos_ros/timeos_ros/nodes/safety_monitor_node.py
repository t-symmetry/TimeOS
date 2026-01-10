#!/usr/bin/env python3
"""Safety Monitor Node - ROS2 node for safety system monitoring.

This node provides:
- Safety status publishing
- E-stop handling
- Interlock monitoring
- Fault aggregation from all subsystems
"""

from __future__ import annotations

import time
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from std_msgs.msg import Bool, String, Float64
from std_srvs.srv import Trigger

# Service imports
from timeos_ros.srv import GetStatus


class SafetyMonitorNode(Node):
    """ROS2 node for safety system monitoring.

    Subscribes:
        /field/temperature (Float64): Field generator temperature
        /causality/risk (Float64): Causality risk level
        /causality/valid (Bool): Causality validity

    Publishes:
        /safety/safe_to_operate (Bool): Overall safety status
        /safety/estop_active (Bool): E-stop state
        /safety/system_state (String): System state description

    Services:
        /safety/estop (Trigger): Trigger emergency stop
        /safety/reset (Trigger): Reset after e-stop
        /safety/get_status (GetStatus): Get detailed status
    """

    def __init__(self):
        super().__init__("safety_monitor_node")

        # Parameters
        self.declare_parameter("max_temperature_kelvin", 9.0)
        self.declare_parameter("max_risk_level", 0.30)
        self.declare_parameter("publish_rate_hz", 20.0)

        self._max_temp = self.get_parameter("max_temperature_kelvin").value
        self._max_risk = self.get_parameter("max_risk_level").value
        publish_rate = self.get_parameter("publish_rate_hz").value

        # State
        self._estop_active = False
        self._safe_to_operate = True
        self._interlocks: list[str] = []
        self._faults: list[str] = []
        self._warnings: list[str] = []

        # Monitored values
        self._temperature = 4.2
        self._causality_risk = 0.0
        self._causality_valid = True

        # Subscribers
        self._temp_sub = self.create_subscription(
            Float64,
            "/field/temperature",
            self._on_temperature,
            10,
        )

        self._risk_sub = self.create_subscription(
            Float64,
            "/causality/risk",
            self._on_risk,
            10,
        )

        self._valid_sub = self.create_subscription(
            Bool,
            "/causality/valid",
            self._on_causality_valid,
            10,
        )

        # Publishers with reliable QoS for safety-critical data
        safety_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            depth=10,
        )

        self._safe_pub = self.create_publisher(
            Bool, "/safety/safe_to_operate", safety_qos
        )
        self._estop_pub = self.create_publisher(
            Bool, "/safety/estop_active", safety_qos
        )
        self._state_pub = self.create_publisher(
            String, "/safety/system_state", safety_qos
        )

        # Services
        self._estop_srv = self.create_service(
            Trigger,
            "/safety/estop",
            self._handle_estop,
        )

        self._reset_srv = self.create_service(
            Trigger,
            "/safety/reset",
            self._handle_reset,
        )

        self._status_srv = self.create_service(
            GetStatus,
            "/safety/get_status",
            self._handle_get_status,
        )

        # Timer
        self._timer = self.create_timer(1.0 / publish_rate, self._update_safety)

        self.get_logger().info("Safety monitor started")

    def _on_temperature(self, msg: Float64):
        """Handle temperature update."""
        self._temperature = msg.data

    def _on_risk(self, msg: Float64):
        """Handle causality risk update."""
        self._causality_risk = msg.data

    def _on_causality_valid(self, msg: Bool):
        """Handle causality validity update."""
        self._causality_valid = msg.data

    def _update_safety(self):
        """Update and publish safety status."""
        # Clear transient warnings
        self._warnings.clear()
        self._interlocks.clear()

        # Check conditions
        if self._estop_active:
            self._safe_to_operate = False
            self._interlocks.append("E-STOP ACTIVE")

        else:
            self._safe_to_operate = True

            # Temperature check
            if self._temperature > self._max_temp:
                self._safe_to_operate = False
                self._interlocks.append(
                    f"THERMAL: {self._temperature:.1f}K > {self._max_temp:.1f}K"
                )
            elif self._temperature > self._max_temp * 0.9:
                self._warnings.append(
                    f"Temperature approaching limit: {self._temperature:.1f}K"
                )

            # Causality check
            if self._causality_risk > self._max_risk:
                self._safe_to_operate = False
                self._interlocks.append(
                    f"CAUSALITY: Risk {self._causality_risk:.1%} > {self._max_risk:.1%}"
                )
            elif self._causality_risk > self._max_risk * 0.5:
                self._warnings.append(
                    f"Causality risk elevated: {self._causality_risk:.1%}"
                )

            if not self._causality_valid:
                self._safe_to_operate = False
                self._interlocks.append("CAUSALITY: Violation detected")

        # Determine system state
        if self._estop_active:
            state = "EMERGENCY_STOP"
        elif not self._safe_to_operate:
            state = "INTERLOCKED"
        elif self._warnings:
            state = "WARNING"
        else:
            state = "NOMINAL"

        # Publish
        safe_msg = Bool()
        safe_msg.data = self._safe_to_operate
        self._safe_pub.publish(safe_msg)

        estop_msg = Bool()
        estop_msg.data = self._estop_active
        self._estop_pub.publish(estop_msg)

        state_msg = String()
        state_msg.data = state
        self._state_pub.publish(state_msg)

    def _handle_estop(
        self,
        request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        """Handle E-stop trigger."""
        self._estop_active = True
        self._safe_to_operate = False

        self.get_logger().error("EMERGENCY STOP ACTIVATED")

        response.success = True
        response.message = "Emergency stop activated"
        return response

    def _handle_reset(
        self,
        request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        """Handle E-stop reset."""
        if not self._estop_active:
            response.success = False
            response.message = "E-stop not active"
            return response

        # Check if safe to reset
        if self._temperature > self._max_temp:
            response.success = False
            response.message = f"Cannot reset: temperature {self._temperature:.1f}K exceeds limit"
            return response

        if self._causality_risk > self._max_risk:
            response.success = False
            response.message = f"Cannot reset: causality risk {self._causality_risk:.1%} too high"
            return response

        # Clear e-stop
        self._estop_active = False
        self._faults.clear()

        self.get_logger().info("E-stop reset successful")

        response.success = True
        response.message = "E-stop cleared, system ready"
        return response

    def _handle_get_status(
        self,
        request: GetStatus.Request,
        response: GetStatus.Response,
    ) -> GetStatus.Response:
        """Handle GetStatus service request."""
        response.timestamp = time.time()

        if self._estop_active:
            response.system_state = "emergency_stop"
        elif not self._safe_to_operate:
            response.system_state = "interlocked"
        elif self._warnings:
            response.system_state = "warning"
        else:
            response.system_state = "nominal"

        response.module_state = response.system_state
        response.safe_to_operate = self._safe_to_operate

        response.faults = list(self._faults)
        response.warnings = list(self._warnings) + list(self._interlocks)

        if request.include_diagnostics:
            response.status_keys = [
                "estop_active",
                "safe_to_operate",
                "temperature_kelvin",
                "causality_risk",
                "causality_valid",
                "interlocks_active",
            ]
            response.status_values = [
                str(self._estop_active),
                str(self._safe_to_operate),
                f"{self._temperature:.2f}",
                f"{self._causality_risk:.3f}",
                str(self._causality_valid),
                str(len(self._interlocks)),
            ]

        return response


def main(args=None):
    """Run the safety monitor node."""
    rclpy.init(args=args)

    node = SafetyMonitorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
