#!/usr/bin/env python3
"""Experiment Controller Node - Orchestrates research experiments."""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer

try:
    from timeos_msgs.msg import ExperimentConfig
    from timeos_msgs.srv import StartExperiment, StopExperiment
    from timeos_msgs.action import RunExperiment
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class ExperimentControllerNode(Node):
    """ROS2 node for experiment orchestration."""

    def __init__(self):
        super().__init__('experiment_controller_node')

        self._running = False
        self._experiment_id = None

        if MSGS_AVAILABLE:
            self._start_srv = self.create_service(
                StartExperiment, '/timeos/start_experiment', self._handle_start
            )
            self._stop_srv = self.create_service(
                StopExperiment, '/timeos/stop_experiment', self._handle_stop
            )

        self.get_logger().info('Experiment controller node initialized')

    def _handle_start(self, request, response):
        import uuid
        self._experiment_id = str(uuid.uuid4())[:8]
        self._running = True
        response.success = True
        response.experiment_id = self._experiment_id
        response.message = f'Experiment {self._experiment_id} started'
        return response

    def _handle_stop(self, request, response):
        self._running = False
        response.success = True
        response.data_saved = True
        response.message = 'Experiment stopped'
        return response


def main(args=None):
    rclpy.init(args=args)
    node = ExperimentControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
