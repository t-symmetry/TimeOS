#!/usr/bin/env python3
"""TDU Node - ROS2 node for Temporal Displacement Unit control.

This node provides:
- Displacement status publishing
- Displacement planning via /tdu/plan service
- Displacement execution via /tdu/execute action
"""

from __future__ import annotations

import time
from typing import Optional

import rclpy
from rclpy.node import Node

from std_msgs.msg import String, Float64

# TimeOS imports
try:
    from timeos.hardware.drivers.emulated import (
        EmulatedTDU,
        TDUConfig,
        DisplacementRequest as TDUDisplacementRequest,
    )
    TIMEOS_AVAILABLE = True
except ImportError:
    TIMEOS_AVAILABLE = False

# Service imports
from timeos_ros.srv import PlanDisplacement, GetStatus


class TDUNode(Node):
    """ROS2 node for Temporal Displacement Unit control.

    Publishes:
        /tdu/state (String): Current TDU state
        /tdu/progress (Float64): Displacement progress (0.0-1.0)

    Services:
        /tdu/plan (PlanDisplacement): Plan displacement
        /tdu/get_status (GetStatus): Get detailed status
    """

    def __init__(self):
        super().__init__("tdu_node")

        # Parameters
        self.declare_parameter("max_displacement_years", 100.0)
        self.declare_parameter("energy_per_second", 1e9)
        self.declare_parameter("publish_rate_hz", 10.0)
        self.declare_parameter("use_emulation", True)

        max_years = self.get_parameter("max_displacement_years").value
        energy_rate = self.get_parameter("energy_per_second").value
        publish_rate = self.get_parameter("publish_rate_hz").value
        use_emulation = self.get_parameter("use_emulation").value

        # Initialize TDU
        if TIMEOS_AVAILABLE and use_emulation:
            config = TDUConfig(
                max_displacement_seconds=max_years * 365.25 * 24 * 3600,
                base_energy_joules=1e6,
                energy_per_second=energy_rate,
            )
            self._tdu = EmulatedTDU(module_id="tdu_ros", config=config)
            self._tdu.initialize()
            self.get_logger().info("Emulated TDU initialized")
        else:
            self._tdu = None
            self.get_logger().warn("Running in stub mode (no emulation)")

        # Publishers
        self._state_pub = self.create_publisher(String, "/tdu/state", 10)
        self._progress_pub = self.create_publisher(Float64, "/tdu/progress", 10)

        # Services
        self._plan_srv = self.create_service(
            PlanDisplacement,
            "/tdu/plan",
            self._handle_plan,
        )

        self._status_srv = self.create_service(
            GetStatus,
            "/tdu/get_status",
            self._handle_get_status,
        )

        # Timer
        self._timer = self.create_timer(1.0 / publish_rate, self._publish_status)

        # State
        self._last_update = time.monotonic()

        self.get_logger().info("TDU node started")

    def _publish_status(self):
        """Publish current TDU status."""
        if not self._tdu:
            return

        # Update emulator
        now = time.monotonic()
        dt = now - self._last_update
        self._last_update = now
        self._tdu.update(dt)

        # Get state
        status = self._tdu.get_status()

        # Publish state
        state_msg = String()
        state_msg.data = status.state
        self._state_pub.publish(state_msg)

        # Publish progress
        progress_msg = Float64()
        progress_msg.data = status.progress
        self._progress_pub.publish(progress_msg)

    def _handle_plan(
        self,
        request: PlanDisplacement.Request,
        response: PlanDisplacement.Response,
    ) -> PlanDisplacement.Response:
        """Handle PlanDisplacement service request."""
        try:
            target_seconds = request.target_t
            mode = request.mode or "optimal"

            if not self._tdu:
                response.success = False
                response.error_message = "TDU not available"
                return response

            # Compute displacement parameters
            max_years = self.get_parameter("max_displacement_years").value
            max_seconds = max_years * 365.25 * 24 * 3600

            if abs(target_seconds) > max_seconds:
                response.success = False
                response.error_message = f"Target exceeds max displacement of {max_years} years"
                return response

            # Calculate energy and duration estimates
            energy_rate = self.get_parameter("energy_per_second").value
            base_energy = 1e6

            energy = base_energy + abs(target_seconds) * energy_rate
            duration = 10.0 + abs(target_seconds) * 0.001  # Simplified estimate

            # Risk assessment based on displacement magnitude
            risk = min(1.0, abs(target_seconds) / max_seconds)

            # Return single path (could compute multiple in future)
            response.success = True
            response.num_paths = 1
            response.path_energies = [energy]
            response.path_durations = [duration]
            response.path_risks = [risk]
            response.path_descriptions = [
                f"Direct {mode} displacement to t={target_seconds:.3f}s"
            ]

            # Causality warnings for backward displacement
            if target_seconds < 0 and request.check_causality:
                response.causality_warnings = [
                    "Backward displacement may create causal loops",
                    f"Light cone constraint: {abs(target_seconds):.1f}s temporal separation",
                ]

            self.get_logger().info(
                f"Planned displacement to t={target_seconds:.3f}s, energy={energy:.2e}J"
            )

        except Exception as e:
            response.success = False
            response.error_message = str(e)
            self.get_logger().error(f"Failed to plan displacement: {e}")

        return response

    def _handle_get_status(
        self,
        request: GetStatus.Request,
        response: GetStatus.Response,
    ) -> GetStatus.Response:
        """Handle GetStatus service request."""
        try:
            response.timestamp = time.time()

            if not self._tdu:
                response.system_state = "unavailable"
                response.safe_to_operate = False
                return response

            status = self._tdu.get_status()

            response.module_state = status.state
            response.system_state = status.state
            response.safe_to_operate = status.state not in ["fault", "emergency"]

            if request.include_diagnostics:
                response.status_keys = [
                    "state",
                    "phase",
                    "progress",
                    "sim_time",
                    "uncertainty",
                ]
                response.status_values = [
                    status.state,
                    status.phase,
                    f"{status.progress:.3f}",
                    f"{status.sim_time:.6f}",
                    f"{status.uncertainty:.9f}",
                ]

        except Exception as e:
            response.system_state = "error"
            response.faults = [str(e)]
            self.get_logger().error(f"Failed to get status: {e}")

        return response

    def destroy_node(self):
        """Clean shutdown."""
        if self._tdu:
            self._tdu.shutdown()
        super().destroy_node()


def main(args=None):
    """Run the TDU node."""
    rclpy.init(args=args)

    node = TDUNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
