"""InfluxDB 2.x connector.

Provides integration with InfluxDB for time-series storage
with tags for metadata and uncertainty tracking.

Requires: influxdb-client
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from timeos.msgs import TimelineEvent


@dataclass
class InfluxDBConfig:
    """InfluxDB connection configuration.

    Attributes:
        url: InfluxDB server URL
        token: API token for authentication
        org: Organization name
        bucket: Bucket name for TimeOS data
        measurement: Default measurement name
    """
    url: str = "http://localhost:8086"
    token: str = ""
    org: str = "timeos"
    bucket: str = "timeos"
    measurement: str = "events"


class InfluxDBConnector:
    """Connector for InfluxDB 2.x time-series database.

    Stores TimeOS events with:
    - Tags: frame_id, branch_id, event_type, author
    - Fields: t, t_uncertainty, event_id, payload
    - Timestamp: derived from t or current time

    Example:
        config = InfluxDBConfig(token="my-token")
        connector = InfluxDBConnector(config)
        connector.connect()
        connector.write_event(event)
        connector.close()
    """

    def __init__(self, config: InfluxDBConfig):
        """Initialize connector.

        Args:
            config: InfluxDB configuration
        """
        self.config = config
        self._client = None
        self._write_api = None
        self._query_api = None
        self._connected = False

    def connect(self) -> None:
        """Connect to InfluxDB."""
        try:
            from influxdb_client import InfluxDBClient
            from influxdb_client.client.write_api import SYNCHRONOUS

            self._client = InfluxDBClient(
                url=self.config.url,
                token=self.config.token,
                org=self.config.org,
            )
            self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
            self._query_api = self._client.query_api()
            self._connected = True

        except ImportError:
            raise ImportError(
                "InfluxDB connector requires influxdb-client. "
                "Install with: pip install influxdb-client"
            )

    def close(self) -> None:
        """Close the connection."""
        if self._write_api:
            self._write_api.close()
        if self._client:
            self._client.close()
        self._client = None
        self._write_api = None
        self._query_api = None
        self._connected = False

    def __enter__(self) -> "InfluxDBConnector":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def write_event(self, event: "TimelineEvent") -> None:
        """Write a single event to InfluxDB.

        Args:
            event: TimelineEvent to write
        """
        if not self._connected:
            raise RuntimeError("Not connected to InfluxDB")

        from influxdb_client import Point

        # Convert t to timestamp
        try:
            timestamp = datetime.fromtimestamp(event.stamp.t, tz=timezone.utc)
        except (OSError, ValueError):
            timestamp = datetime.now(tz=timezone.utc)

        point = (
            Point(self.config.measurement)
            .tag("frame_id", event.stamp.frame_id)
            .tag("branch_id", event.branch_id)
            .tag("event_type", event.event_type)
            .field("event_id", event.event_id)
            .field("t", event.stamp.t)
            .field("t_uncertainty", event.stamp.t_uncertainty)
            .time(timestamp)
        )

        if event.author:
            point = point.tag("author", event.author)

        if event.payload:
            try:
                payload_str = event.payload.decode('utf-8')
                point = point.field("payload", payload_str)
            except UnicodeDecodeError:
                point = point.field("payload_hex", event.payload.hex())

        self._write_api.write(
            bucket=self.config.bucket,
            record=point,
        )

    def write_events(self, events: List["TimelineEvent"]) -> int:
        """Write multiple events to InfluxDB.

        Args:
            events: List of events to write

        Returns:
            Number of events written
        """
        if not self._connected:
            raise RuntimeError("Not connected to InfluxDB")

        from influxdb_client import Point

        points = []
        for event in events:
            try:
                timestamp = datetime.fromtimestamp(event.stamp.t, tz=timezone.utc)
            except (OSError, ValueError):
                timestamp = datetime.now(tz=timezone.utc)

            point = (
                Point(self.config.measurement)
                .tag("frame_id", event.stamp.frame_id)
                .tag("branch_id", event.branch_id)
                .tag("event_type", event.event_type)
                .field("event_id", event.event_id)
                .field("t", event.stamp.t)
                .field("t_uncertainty", event.stamp.t_uncertainty)
                .time(timestamp)
            )

            if event.author:
                point = point.tag("author", event.author)

            points.append(point)

        self._write_api.write(
            bucket=self.config.bucket,
            record=points,
        )

        return len(points)

    def query_range(
        self,
        start: datetime,
        stop: datetime,
        frame_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query events in a time range.

        Args:
            start: Start time
            stop: Stop time
            frame_id: Optional frame filter
            branch_id: Optional branch filter
            event_type: Optional event type filter

        Returns:
            List of event records
        """
        if not self._connected:
            raise RuntimeError("Not connected to InfluxDB")

        # Build Flux query
        filters = []
        if frame_id:
            filters.append(f'r.frame_id == "{frame_id}"')
        if branch_id:
            filters.append(f'r.branch_id == "{branch_id}"')
        if event_type:
            filters.append(f'r.event_type == "{event_type}"')

        filter_expr = " and ".join(filters) if filters else "true"

        query = f'''
            from(bucket: "{self.config.bucket}")
                |> range(start: {start.isoformat()}, stop: {stop.isoformat()})
                |> filter(fn: (r) => r._measurement == "{self.config.measurement}")
                |> filter(fn: (r) => {filter_expr})
                |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''

        tables = self._query_api.query(query)

        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "time": record.get_time(),
                    "event_id": record.values.get("event_id"),
                    "frame_id": record.values.get("frame_id"),
                    "branch_id": record.values.get("branch_id"),
                    "event_type": record.values.get("event_type"),
                    "t": record.values.get("t"),
                    "t_uncertainty": record.values.get("t_uncertainty"),
                    "author": record.values.get("author"),
                    "payload": record.values.get("payload"),
                })

        return results

    def query_by_t(
        self,
        t_start: float,
        t_end: float,
        frame_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query events by TimeOS t coordinate.

        Args:
            t_start: Start t value
            t_end: End t value
            frame_id: Optional frame filter

        Returns:
            List of event records
        """
        if not self._connected:
            raise RuntimeError("Not connected to InfluxDB")

        filters = [f'r.t >= {t_start}', f'r.t <= {t_end}']
        if frame_id:
            filters.append(f'r.frame_id == "{frame_id}"')

        filter_expr = " and ".join(filters)

        # Query all time, filter by t field
        query = f'''
            from(bucket: "{self.config.bucket}")
                |> range(start: 0)
                |> filter(fn: (r) => r._measurement == "{self.config.measurement}")
                |> filter(fn: (r) => r._field == "t")
                |> filter(fn: (r) => r._value >= {t_start} and r._value <= {t_end})
        '''

        tables = self._query_api.query(query)

        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "time": record.get_time(),
                    "t": record.get_value(),
                    "frame_id": record.values.get("frame_id"),
                    "branch_id": record.values.get("branch_id"),
                    "event_type": record.values.get("event_type"),
                })

        return results

    def delete_range(
        self,
        start: datetime,
        stop: datetime,
        predicate: Optional[str] = None,
    ) -> None:
        """Delete events in a time range.

        Args:
            start: Start time
            stop: Stop time
            predicate: Optional Flux predicate for filtering
        """
        if not self._connected:
            raise RuntimeError("Not connected to InfluxDB")

        delete_api = self._client.delete_api()

        pred = predicate or f'_measurement="{self.config.measurement}"'

        delete_api.delete(
            start=start,
            stop=stop,
            predicate=pred,
            bucket=self.config.bucket,
            org=self.config.org,
        )

    def write_line_protocol(self, line: str) -> None:
        """Write raw line protocol string.

        Args:
            line: InfluxDB line protocol string
        """
        if not self._connected:
            raise RuntimeError("Not connected to InfluxDB")

        self._write_api.write(
            bucket=self.config.bucket,
            record=line,
        )

    def write_line_protocol_batch(self, lines: List[str]) -> None:
        """Write multiple line protocol strings.

        Args:
            lines: List of line protocol strings
        """
        if not self._connected:
            raise RuntimeError("Not connected to InfluxDB")

        self._write_api.write(
            bucket=self.config.bucket,
            record="\n".join(lines),
        )

    def health_check(self) -> bool:
        """Check if InfluxDB is healthy.

        Returns:
            True if healthy
        """
        if not self._client:
            return False

        health = self._client.health()
        return health.status == "pass"

    def get_buckets(self) -> List[str]:
        """List available buckets.

        Returns:
            List of bucket names
        """
        if not self._connected:
            raise RuntimeError("Not connected to InfluxDB")

        buckets_api = self._client.buckets_api()
        buckets = buckets_api.find_buckets().buckets
        return [b.name for b in buckets]
