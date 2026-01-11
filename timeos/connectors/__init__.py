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
]
