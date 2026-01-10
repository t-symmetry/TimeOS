#!/usr/bin/env python3
"""Anchor Node - Temporal reference management."""

import rclpy
from rclpy.node import Node

try:
    from timeos_msgs.msg import AnchorState, ChronoStamp
    from timeos_msgs.srv import SetAnchor
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class AnchorNode(Node):
    """ROS2 node for temporal anchor management."""

    def __init__(self):
        super().__init__('anchor_node')

        self._connected = True
        self._locked = True

        if MSGS_AVAILABLE:
            self._pub = self.create_publisher(AnchorState, '/timeos/anchor_state', 10)
            self._srv = self.create_service(SetAnchor, '/timeos/set_anchor', self._handle_set_anchor)

        self._timer = self.create_timer(1.0, self._publish_state)
        self.get_logger().info('Anchor node initialized')

    def _publish_state(self) -> None:
        if not MSGS_AVAILABLE:
            return

        msg = AnchorState()
        msg.stamp = self.get_clock().now().to_msg()
        msg.connected = self._connected
        msg.locked = self._locked
        msg.lock_quality = 0.99
        msg.reference_source = AnchorState.REF_GPS
        msg.drift_ppm = 0.001
        msg.jitter_ns = 10.0
        msg.pps_present = True
        msg.disciplined = True

        self._pub.publish(msg)

    def _handle_set_anchor(self, request, response):
        response.success = True
        response.message = 'Anchor set'
        return response


def main(args=None):
    rclpy.init(args=args)
    node = AnchorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
