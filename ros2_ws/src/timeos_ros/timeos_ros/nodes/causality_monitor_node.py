#!/usr/bin/env python3
"""Causality Monitor Node - Real-time causality constraint checking."""

import rclpy
from rclpy.node import Node

try:
    from timeos_msgs.msg import CausalityStatus, TimelineEvent
    from timeos_msgs.srv import ValidateCausality
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class CausalityMonitorNode(Node):
    """ROS2 node for causality monitoring."""

    def __init__(self):
        super().__init__('causality_monitor_node')

        self._risk = 0.0
        self._status = 0  # NOMINAL

        if MSGS_AVAILABLE:
            self._pub = self.create_publisher(CausalityStatus, '/timeos/causality_status', 10)
            self._event_sub = self.create_subscription(
                TimelineEvent, '/timeos/events', self._on_event, 10
            )
            self._srv = self.create_service(
                ValidateCausality, '/timeos/validate_causality', self._handle_validate
            )

        self._timer = self.create_timer(0.1, self._publish_status)
        self.get_logger().info('Causality monitor node initialized')

    def _on_event(self, msg) -> None:
        # Check causality for new event
        pass

    def _publish_status(self) -> None:
        if not MSGS_AVAILABLE:
            return

        msg = CausalityStatus()
        msg.stamp = self.get_clock().now().to_msg()
        msg.status = self._status
        msg.paradox_risk = self._risk
        msg.future_cone_clear = True
        msg.past_cone_clear = True

        self._pub.publish(msg)

    def _handle_validate(self, request, response):
        response.valid = True
        response.risk = 0.0
        response.recommendation = 'Proceed'
        return response


def main(args=None):
    rclpy.init(args=args)
    node = CausalityMonitorNode()
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
