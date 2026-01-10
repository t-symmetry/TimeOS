#!/usr/bin/env python3
"""Thermal Monitor Node - Cryogenic thermal management."""

import rclpy
from rclpy.node import Node

try:
    from timeos_msgs.msg import ThermalState
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class ThermalMonitorNode(Node):
    """ROS2 node for thermal monitoring."""

    def __init__(self):
        super().__init__('thermal_monitor_node')

        self.declare_parameter('base_temperature', 4.2)

        self._temperature = self.get_parameter('base_temperature').value
        self._quench_risk = 0.0

        if MSGS_AVAILABLE:
            self._pub = self.create_publisher(ThermalState, '/timeos/thermal_state', 10)

        self._timer = self.create_timer(0.1, self._publish_state)
        self.get_logger().info('Thermal monitor node initialized')

    def _publish_state(self) -> None:
        if not MSGS_AVAILABLE:
            return

        msg = ThermalState()
        msg.stamp = self.get_clock().now().to_msg()
        msg.temperature_kelvin = self._temperature
        msg.temperature_setpoint = 4.2
        msg.temp_magnet_core = self._temperature
        msg.temp_cryostat = self._temperature * 0.95
        msg.temp_radiation_shield = 77.0
        msg.temp_ambient = 293.0
        msg.cryo_state = ThermalState.CRYO_COLD
        msg.cooling_power_watts = 50.0
        msg.quench_risk = self._quench_risk
        msg.thermal_margin_kelvin = 9.2 - self._temperature
        msg.critical_temperature = 9.2
        msg.quench_detected = False
        msg.cooling_active = True
        msg.thermal_stable = True

        self._pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ThermalMonitorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass  # Context may already be shutdown


if __name__ == '__main__':
    main()
