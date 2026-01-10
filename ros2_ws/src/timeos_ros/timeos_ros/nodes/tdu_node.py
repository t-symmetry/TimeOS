#!/usr/bin/env python3
"""TDU Node - Temporal Displacement Unit control."""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer

try:
    from timeos_msgs.msg import DisplacementState
    from timeos_msgs.action import Displace
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class TDUNode(Node):
    """ROS2 node for TDU control."""

    def __init__(self):
        super().__init__('tdu_node')

        self._state = 0  # IDLE
        self._position = [0.0, 0.0, 0.0, 0.0]  # x, y, z, t

        if MSGS_AVAILABLE:
            self._pub = self.create_publisher(DisplacementState, '/timeos/displacement_state', 10)
            self._action = ActionServer(self, Displace, '/timeos/displace', self._execute_displace)

        self._timer = self.create_timer(0.1, self._publish_state)
        self.get_logger().info('TDU node initialized')

    def _publish_state(self) -> None:
        if not MSGS_AVAILABLE:
            return

        msg = DisplacementState()
        msg.stamp = self.get_clock().now().to_msg()
        msg.displacement_state = self._state
        msg.current_x = self._position[0]
        msg.current_y = self._position[1]
        msg.current_z = self._position[2]
        msg.current_t = self._position[3]
        msg.ready = self._state == 0
        msg.interlocks_satisfied = True

        self._pub.publish(msg)

    def _execute_displace(self, goal_handle):
        result = Displace.Result()
        result.success = True
        result.message = 'Displacement complete (simulated)'
        goal_handle.succeed()
        return result


def main(args=None):
    rclpy.init(args=args)
    node = TDUNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
