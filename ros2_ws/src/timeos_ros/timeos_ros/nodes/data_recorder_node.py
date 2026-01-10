#!/usr/bin/env python3
"""Data Recorder Node - Records sensor data for experiments."""

import rclpy
from rclpy.node import Node
from collections import deque
import json
from pathlib import Path

try:
    from timeos_msgs.msg import SensorReading
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class DataRecorderNode(Node):
    """ROS2 node for experiment data recording."""

    def __init__(self):
        super().__init__('data_recorder_node')

        self.declare_parameter('output_dir', '/tmp/timeos_data')
        self.declare_parameter('buffer_size', 10000)

        self.output_dir = Path(self.get_parameter('output_dir').value)
        self.buffer_size = self.get_parameter('buffer_size').value

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._recording = False
        self._buffer = deque(maxlen=self.buffer_size)
        self._subs = []

        if MSGS_AVAILABLE:
            # Subscribe to all sensor topics
            self._sensor_sub = self.create_subscription(
                SensorReading,
                '/timeos/sensors/+',
                self._on_sensor,
                10
            )

        self.get_logger().info(f'Data recorder initialized, output: {self.output_dir}')

    def _on_sensor(self, msg) -> None:
        if not self._recording:
            return

        record = {
            'timestamp': msg.stamp.sec + msg.stamp.nanosec * 1e-9,
            'sensor_id': msg.sensor_id,
            'value': msg.value,
            'uncertainty': msg.uncertainty,
            'units': msg.units,
        }
        self._buffer.append(record)

    def start_recording(self) -> None:
        self._recording = True
        self._buffer.clear()
        self.get_logger().info('Recording started')

    def stop_recording(self, filename: str = None) -> str:
        self._recording = False

        if filename is None:
            import time
            filename = f'recording_{int(time.time())}.json'

        path = self.output_dir / filename

        with open(path, 'w') as f:
            json.dump(list(self._buffer), f, indent=2)

        self.get_logger().info(f'Saved {len(self._buffer)} records to {path}')
        return str(path)


def main(args=None):
    rclpy.init(args=args)
    node = DataRecorderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
