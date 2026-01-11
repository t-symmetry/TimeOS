"""TimescaleDB connector.

Provides integration with TimescaleDB for efficient time-series storage
with hypertable partitioning and continuous aggregates.

Requires: psycopg2 or psycopg (PostgreSQL adapter)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from timeos.msgs import TimelineEvent, ChronoStamp


@dataclass
class TimescaleConfig:
    """TimescaleDB connection configuration.

    Attributes:
        host: Database host
        port: Database port
        database: Database name
        user: Username
        password: Password
        schema: Schema name for TimeOS tables
        chunk_time_interval: Hypertable chunk interval (e.g., '1 day')
    """
    host: str = "localhost"
    port: int = 5432
    database: str = "timeos"
    user: str = "timeos"
    password: str = ""
    schema: str = "timeos"
    chunk_time_interval: str = "1 day"

    @property
    def connection_string(self) -> str:
        """Get PostgreSQL connection string."""
        return (
            f"host={self.host} port={self.port} "
            f"dbname={self.database} user={self.user} "
            f"password={self.password}"
        )


class TimescaleConnector:
    """Connector for TimescaleDB time-series database.

    Provides methods to store and query TimeOS events in TimescaleDB
    with proper hypertable partitioning.

    Example:
        config = TimescaleConfig(database="mydb", password="secret")
        connector = TimescaleConnector(config)
        connector.connect()
        connector.store_event(event)
        events = connector.query_range(start, end)
        connector.close()
    """

    def __init__(self, config: TimescaleConfig):
        """Initialize connector.

        Args:
            config: Database configuration
        """
        self.config = config
        self._conn = None
        self._connected = False

    def connect(self) -> None:
        """Connect to the database."""
        try:
            import psycopg2
            self._conn = psycopg2.connect(self.config.connection_string)
            self._connected = True
        except ImportError:
            try:
                import psycopg
                self._conn = psycopg.connect(self.config.connection_string)
                self._connected = True
            except ImportError:
                raise ImportError(
                    "TimescaleDB connector requires psycopg2 or psycopg. "
                    "Install with: pip install psycopg2-binary"
                )

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            self._connected = False

    def __enter__(self) -> "TimescaleConnector":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def ensure_schema(self) -> None:
        """Create schema and tables if they don't exist."""
        if not self._connected:
            raise RuntimeError("Not connected to database")

        with self._conn.cursor() as cur:
            # Create schema
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.config.schema}")

            # Create events table
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.config.schema}.events (
                    time TIMESTAMPTZ NOT NULL,
                    event_id TEXT NOT NULL,
                    frame_id TEXT NOT NULL,
                    t DOUBLE PRECISION NOT NULL,
                    t_uncertainty DOUBLE PRECISION DEFAULT 0,
                    branch_id TEXT DEFAULT 'main',
                    event_type TEXT NOT NULL,
                    author TEXT,
                    payload JSONB,
                    PRIMARY KEY (time, event_id)
                )
            """)

            # Create causal links table
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.config.schema}.causal_links (
                    time TIMESTAMPTZ NOT NULL,
                    child_id TEXT NOT NULL,
                    parent_id TEXT NOT NULL,
                    PRIMARY KEY (time, child_id, parent_id)
                )
            """)

            self._conn.commit()

    def create_hypertable(self, if_not_exists: bool = True) -> None:
        """Convert events table to hypertable.

        Args:
            if_not_exists: Don't error if already a hypertable
        """
        if not self._connected:
            raise RuntimeError("Not connected to database")

        with self._conn.cursor() as cur:
            migrate_data = "true" if if_not_exists else "false"
            cur.execute(f"""
                SELECT create_hypertable(
                    '{self.config.schema}.events',
                    'time',
                    chunk_time_interval => INTERVAL '{self.config.chunk_time_interval}',
                    if_not_exists => {if_not_exists},
                    migrate_data => {migrate_data}
                )
            """)
            self._conn.commit()

    def store_event(self, event: "TimelineEvent") -> None:
        """Store a single event.

        Args:
            event: TimelineEvent to store
        """
        if not self._connected:
            raise RuntimeError("Not connected to database")

        # Convert event time to timestamp
        # Using t as seconds since epoch for simplicity
        try:
            timestamp = datetime.fromtimestamp(event.stamp.t, tz=timezone.utc)
        except (OSError, ValueError):
            # t is out of range, use current time
            timestamp = datetime.now(tz=timezone.utc)

        # Prepare payload
        payload = {}
        if event.payload:
            try:
                payload = json.loads(event.payload.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {"raw": event.payload.hex()}

        with self._conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {self.config.schema}.events
                (time, event_id, frame_id, t, t_uncertainty, branch_id, event_type, author, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (time, event_id) DO UPDATE SET
                    t_uncertainty = EXCLUDED.t_uncertainty,
                    payload = EXCLUDED.payload
            """, (
                timestamp,
                event.event_id,
                event.stamp.frame_id,
                event.stamp.t,
                event.stamp.t_uncertainty,
                event.branch_id,
                event.event_type,
                event.author,
                json.dumps(payload),
            ))

            # Store causal links
            for parent_id in event.parents:
                cur.execute(f"""
                    INSERT INTO {self.config.schema}.causal_links
                    (time, child_id, parent_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (timestamp, event.event_id, parent_id))

            self._conn.commit()

    def store_events(self, events: List["TimelineEvent"]) -> int:
        """Store multiple events efficiently.

        Args:
            events: List of events to store

        Returns:
            Number of events stored
        """
        count = 0
        for event in events:
            self.store_event(event)
            count += 1
        return count

    def query_range(
        self,
        start: datetime,
        end: datetime,
        frame_id: Optional[str] = None,
        branch_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query events in a time range.

        Args:
            start: Start time (inclusive)
            end: End time (inclusive)
            frame_id: Optional frame filter
            branch_id: Optional branch filter

        Returns:
            List of event dictionaries
        """
        if not self._connected:
            raise RuntimeError("Not connected to database")

        conditions = ["time >= %s", "time <= %s"]
        params: list = [start, end]

        if frame_id:
            conditions.append("frame_id = %s")
            params.append(frame_id)

        if branch_id:
            conditions.append("branch_id = %s")
            params.append(branch_id)

        where_clause = " AND ".join(conditions)

        with self._conn.cursor() as cur:
            cur.execute(f"""
                SELECT time, event_id, frame_id, t, t_uncertainty,
                       branch_id, event_type, author, payload
                FROM {self.config.schema}.events
                WHERE {where_clause}
                ORDER BY time ASC
            """, params)

            columns = [desc[0] for desc in cur.description]
            results = []
            for row in cur.fetchall():
                results.append(dict(zip(columns, row)))

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
            List of event dictionaries
        """
        if not self._connected:
            raise RuntimeError("Not connected to database")

        conditions = ["t >= %s", "t <= %s"]
        params: list = [t_start, t_end]

        if frame_id:
            conditions.append("frame_id = %s")
            params.append(frame_id)

        where_clause = " AND ".join(conditions)

        with self._conn.cursor() as cur:
            cur.execute(f"""
                SELECT time, event_id, frame_id, t, t_uncertainty,
                       branch_id, event_type, author, payload
                FROM {self.config.schema}.events
                WHERE {where_clause}
                ORDER BY t ASC
            """, params)

            columns = [desc[0] for desc in cur.description]
            results = []
            for row in cur.fetchall():
                results.append(dict(zip(columns, row)))

            return results

    def get_time_bounds(self) -> tuple[datetime, datetime] | None:
        """Get the time range of stored events.

        Returns:
            Tuple of (earliest, latest) timestamps, or None if empty
        """
        if not self._connected:
            raise RuntimeError("Not connected to database")

        with self._conn.cursor() as cur:
            cur.execute(f"""
                SELECT MIN(time), MAX(time)
                FROM {self.config.schema}.events
            """)
            row = cur.fetchone()
            if row and row[0] and row[1]:
                return (row[0], row[1])
            return None

    def count_events(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> int:
        """Count events in time range.

        Args:
            start: Optional start time
            end: Optional end time

        Returns:
            Event count
        """
        if not self._connected:
            raise RuntimeError("Not connected to database")

        conditions = []
        params: list = []

        if start:
            conditions.append("time >= %s")
            params.append(start)
        if end:
            conditions.append("time <= %s")
            params.append(end)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with self._conn.cursor() as cur:
            cur.execute(f"""
                SELECT COUNT(*)
                FROM {self.config.schema}.events
                WHERE {where_clause}
            """, params)
            return cur.fetchone()[0]


def create_hypertable(
    config: TimescaleConfig,
    chunk_interval: str = "1 day",
) -> None:
    """Create TimescaleDB hypertable for TimeOS events.

    Convenience function to set up the database schema.

    Args:
        config: Database configuration
        chunk_interval: Time interval for chunks
    """
    config.chunk_time_interval = chunk_interval

    with TimescaleConnector(config) as conn:
        conn.ensure_schema()
        conn.create_hypertable()
