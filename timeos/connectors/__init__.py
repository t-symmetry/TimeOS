"""External system connectors.

Provides integration with time-series databases, message systems,
and other temporal data infrastructure.
"""

from __future__ import annotations

from timeos.connectors.timescale import (
    TimescaleConnector,
    TimescaleConfig,
    create_hypertable,
)
from timeos.connectors.influxdb import (
    InfluxDBConnector,
    InfluxDBConfig,
)
from timeos.connectors.kafka import (
    KafkaTimeExtractor,
    KafkaTimestampType,
    extract_event_time,
    extract_processing_time,
)
from timeos.connectors.ros2_time import (
    ROS2Time,
    ROS2Duration,
    ROS2Header,
    ROS2TimeBridge,
    ROS2TimeSource,
    ros2_time_to_chrono,
    chrono_to_ros2_time,
    parse_ros2_timestamp,
    format_ros2_timestamp,
)

__all__ = [
    # TimescaleDB
    "TimescaleConnector",
    "TimescaleConfig",
    "create_hypertable",
    # InfluxDB
    "InfluxDBConnector",
    "InfluxDBConfig",
    # Kafka
    "KafkaTimeExtractor",
    "KafkaTimestampType",
    "extract_event_time",
    "extract_processing_time",
    # ROS2
    "ROS2Time",
    "ROS2Duration",
    "ROS2Header",
    "ROS2TimeBridge",
    "ROS2TimeSource",
    "ros2_time_to_chrono",
    "chrono_to_ros2_time",
    "parse_ros2_timestamp",
    "format_ros2_timestamp",
]
