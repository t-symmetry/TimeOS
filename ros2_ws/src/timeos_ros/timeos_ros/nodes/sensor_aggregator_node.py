#!/usr/bin/env python3
"""Sensor Aggregator Node - Interfaces with real/emulated sensors.

Provides a unified interface for sensor data from various sources:
- Serial sensors (magnetometers, temperature)
- I2C sensors (accelerometers, magnetometers)
- Analog inputs (via NI DAQ or similar)
- Network sensors (lab instruments via SCPI/TCP)
"""

import threading
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
import json

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

# Try to import hardware interfaces
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

# Import ROS2 message types
try:
    from timeos_msgs.msg import SensorReading, ChronoStamp
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


@dataclass
class SensorConfig:
    """Configuration for a sensor."""
    sensor_id: str
    sensor_type: str
    interface: str  # serial, i2c, analog, tcp, emulated
    address: str    # port, i2c address, channel, ip:port
    sample_rate: float
    units: str
    calibration_scale: float = 1.0
    calibration_offset: float = 0.0


class SensorAggregatorNode(Node):
    """ROS2 node for sensor data aggregation.

    Publishers:
        /timeos/sensors/<sensor_id> (SensorReading): Per-sensor data

    Supports multiple sensor types:
    - Magnetometers (Hall effect, fluxgate)
    - Temperature sensors (RTD, thermocouple)
    - Position encoders
    - Current/voltage sensors
    """

    def __init__(self):
        super().__init__('sensor_aggregator_node')

        # Parameters
        self.declare_parameter('config_file', '')
        self.declare_parameter('default_sample_rate', 100.0)
        self.declare_parameter('emulate_sensors', True)

        config_file = self.get_parameter('config_file').value
        self.default_sample_rate = self.get_parameter('default_sample_rate').value
        self.emulate_sensors = self.get_parameter('emulate_sensors').value

        # State
        self._lock = threading.Lock()
        self._sensors: Dict[str, SensorConfig] = {}
        self._sensor_threads: Dict[str, threading.Thread] = {}
        self._sensor_pubs: Dict[str, Any] = {}
        self._running = True

        # Emulated sensor state
        self._emulated_values: Dict[str, float] = {}

        # Load configuration
        if config_file:
            self._load_config(config_file)
        else:
            self._setup_default_sensors()

        # Start sensor threads
        self._start_sensors()

        self.get_logger().info(f'Sensor aggregator initialized with {len(self._sensors)} sensors')

    def _load_config(self, path: str) -> None:
        """Load sensor configuration from file."""
        try:
            with open(path, 'r') as f:
                config = json.load(f)

            for sensor_cfg in config.get('sensors', []):
                sensor = SensorConfig(
                    sensor_id=sensor_cfg['id'],
                    sensor_type=sensor_cfg['type'],
                    interface=sensor_cfg.get('interface', 'emulated'),
                    address=sensor_cfg.get('address', ''),
                    sample_rate=sensor_cfg.get('sample_rate', self.default_sample_rate),
                    units=sensor_cfg.get('units', 'V'),
                    calibration_scale=sensor_cfg.get('calibration_scale', 1.0),
                    calibration_offset=sensor_cfg.get('calibration_offset', 0.0),
                )
                self._sensors[sensor.sensor_id] = sensor

        except Exception as e:
            self.get_logger().error(f'Failed to load config: {e}')
            self._setup_default_sensors()

    def _setup_default_sensors(self) -> None:
        """Set up default emulated sensors for T-symmetry research."""
        default_sensors = [
            SensorConfig(
                sensor_id='magnetometer_z',
                sensor_type='magnetometer',
                interface='emulated',
                address='',
                sample_rate=100.0,
                units='T',
            ),
            SensorConfig(
                sensor_id='magnetometer_x',
                sensor_type='magnetometer',
                interface='emulated',
                address='',
                sample_rate=100.0,
                units='T',
            ),
            SensorConfig(
                sensor_id='magnetometer_y',
                sensor_type='magnetometer',
                interface='emulated',
                address='',
                sample_rate=100.0,
                units='T',
            ),
            SensorConfig(
                sensor_id='temp_cryostat',
                sensor_type='temperature',
                interface='emulated',
                address='',
                sample_rate=10.0,
                units='K',
            ),
            SensorConfig(
                sensor_id='temp_magnet',
                sensor_type='temperature',
                interface='emulated',
                address='',
                sample_rate=10.0,
                units='K',
            ),
            SensorConfig(
                sensor_id='current_coil',
                sensor_type='current',
                interface='emulated',
                address='',
                sample_rate=50.0,
                units='A',
            ),
            SensorConfig(
                sensor_id='voltage_supply',
                sensor_type='voltage',
                interface='emulated',
                address='',
                sample_rate=50.0,
                units='V',
            ),
        ]

        for sensor in default_sensors:
            self._sensors[sensor.sensor_id] = sensor
            self._emulated_values[sensor.sensor_id] = 0.0

    def _start_sensors(self) -> None:
        """Start sensor reading threads."""
        if not MSGS_AVAILABLE:
            return

        for sensor_id, config in self._sensors.items():
            # Create publisher
            pub = self.create_publisher(
                SensorReading,
                f'/timeos/sensors/{sensor_id}',
                10
            )
            self._sensor_pubs[sensor_id] = pub

            # Start reading thread
            thread = threading.Thread(
                target=self._sensor_loop,
                args=(sensor_id,),
                daemon=True
            )
            self._sensor_threads[sensor_id] = thread
            thread.start()

    def _sensor_loop(self, sensor_id: str) -> None:
        """Main loop for reading a sensor."""
        config = self._sensors[sensor_id]
        period = 1.0 / config.sample_rate

        while self._running and rclpy.ok():
            try:
                # Read value based on interface type
                if config.interface == 'emulated' or self.emulate_sensors:
                    raw_value = self._read_emulated(sensor_id, config)
                elif config.interface == 'serial':
                    raw_value = self._read_serial(config)
                elif config.interface == 'tcp':
                    raw_value = self._read_tcp(config)
                else:
                    raw_value = 0.0

                # Apply calibration
                value = raw_value * config.calibration_scale + config.calibration_offset

                # Publish
                self._publish_reading(sensor_id, config, value, raw_value)

            except Exception as e:
                self.get_logger().error(f'Sensor {sensor_id} error: {e}')

            time.sleep(period)

    def _read_emulated(self, sensor_id: str, config: SensorConfig) -> float:
        """Generate emulated sensor reading."""
        import numpy as np

        base_value = self._emulated_values.get(sensor_id, 0.0)

        # Add realistic noise based on sensor type
        if config.sensor_type == 'magnetometer':
            noise = np.random.normal(0, 1e-6)  # 1 µT noise
            value = base_value + noise
        elif config.sensor_type == 'temperature':
            noise = np.random.normal(0, 0.01)  # 10 mK noise
            value = 4.2 + noise  # Base 4.2 K
        elif config.sensor_type == 'current':
            noise = np.random.normal(0, 0.001)  # 1 mA noise
            value = base_value + noise
        elif config.sensor_type == 'voltage':
            noise = np.random.normal(0, 0.001)  # 1 mV noise
            value = 10.0 + noise  # Base 10 V
        else:
            value = base_value + np.random.normal(0, 0.001)

        return value

    def _read_serial(self, config: SensorConfig) -> float:
        """Read from serial sensor."""
        if not SERIAL_AVAILABLE:
            return 0.0

        try:
            with serial.Serial(config.address, 9600, timeout=1) as ser:
                line = ser.readline().decode('utf-8').strip()
                return float(line)
        except Exception as e:
            self.get_logger().warn(f'Serial read failed: {e}')
            return 0.0

    def _read_tcp(self, config: SensorConfig) -> float:
        """Read from TCP/SCPI instrument."""
        import socket

        try:
            host, port = config.address.split(':')
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                s.connect((host, int(port)))
                s.sendall(b'READ?\n')
                response = s.recv(1024).decode('utf-8').strip()
                return float(response)
        except Exception as e:
            self.get_logger().warn(f'TCP read failed: {e}')
            return 0.0

    def _publish_reading(
        self,
        sensor_id: str,
        config: SensorConfig,
        value: float,
        raw_value: float
    ) -> None:
        """Publish sensor reading."""
        msg = SensorReading()
        msg.stamp = self.get_clock().now().to_msg()

        # Set ChronoStamp
        msg.chrono_stamp.stamp = msg.stamp
        msg.chrono_stamp.tau = time.time()
        msg.chrono_stamp.coordinate_time = time.time()
        msg.chrono_stamp.gamma = 1.0
        msg.chrono_stamp.reference_frame = 'lab'

        msg.sensor_id = sensor_id
        msg.sensor_type = config.sensor_type
        msg.channel = ''
        msg.value = value
        msg.uncertainty = self._get_uncertainty(config)
        msg.units = config.units
        msg.valid = True
        msg.calibrated = True
        msg.raw_value = raw_value
        msg.snr_db = 60.0  # Approximate
        msg.confidence = 0.99

        self._sensor_pubs[sensor_id].publish(msg)

    def _get_uncertainty(self, config: SensorConfig) -> float:
        """Get measurement uncertainty for sensor type."""
        uncertainties = {
            'magnetometer': 1e-6,    # 1 µT
            'temperature': 0.01,     # 10 mK
            'current': 0.001,        # 1 mA
            'voltage': 0.001,        # 1 mV
        }
        return uncertainties.get(config.sensor_type, 0.001)

    def set_emulated_value(self, sensor_id: str, value: float) -> None:
        """Set emulated sensor value (for testing/demo)."""
        with self._lock:
            self._emulated_values[sensor_id] = value

    def destroy_node(self) -> None:
        """Clean shutdown."""
        self._running = False
        for thread in self._sensor_threads.values():
            thread.join(timeout=1.0)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SensorAggregatorNode()

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
