"""Kafka timestamp handling.

Provides utilities for working with Kafka message timestamps,
including event time vs processing time semantics and watermarks.

Requires: confluent-kafka or kafka-python
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from timeos.msgs import ChronoStamp, TimelineEvent


class KafkaTimestampType(Enum):
    """Kafka timestamp type."""
    CREATE_TIME = 0      # Producer-set timestamp (event time)
    LOG_APPEND_TIME = 1  # Broker-set timestamp (ingestion time)
    NO_TIMESTAMP = -1    # No timestamp available


@dataclass
class KafkaMessageTime:
    """Extracted time information from a Kafka message.

    Attributes:
        event_time: Event time (when the event occurred)
        processing_time: Processing time (when we processed it)
        ingestion_time: Ingestion time (when Kafka received it)
        timestamp_type: Type of Kafka timestamp
        uncertainty: Estimated uncertainty in event time
    """
    event_time: Optional[datetime] = None
    processing_time: Optional[datetime] = None
    ingestion_time: Optional[datetime] = None
    timestamp_type: KafkaTimestampType = KafkaTimestampType.NO_TIMESTAMP
    uncertainty: float = 0.0

    def to_chrono_stamp(self, frame_id: str = "kafka") -> "ChronoStamp":
        """Convert to ChronoStamp.

        Args:
            frame_id: Frame ID for the stamp

        Returns:
            ChronoStamp with appropriate time and uncertainty
        """
        from timeos.msgs import ChronoStamp

        # Prefer event time, fall back to processing time
        if self.event_time:
            t = self.event_time.timestamp()
            clock_class = "kafka_event"
        elif self.ingestion_time:
            t = self.ingestion_time.timestamp()
            clock_class = "kafka_ingestion"
        elif self.processing_time:
            t = self.processing_time.timestamp()
            clock_class = "kafka_processing"
        else:
            t = datetime.now(tz=timezone.utc).timestamp()
            clock_class = "wall_clock"

        return ChronoStamp(
            frame_id=frame_id,
            t=t,
            t_uncertainty=self.uncertainty,
            clock_class=clock_class,
        )


class KafkaTimeExtractor:
    """Extracts and manages time information from Kafka messages.

    Supports multiple time extraction strategies:
    - Kafka timestamp (CREATE_TIME or LOG_APPEND_TIME)
    - Message payload field
    - Message header
    - Custom extractor function

    Example:
        extractor = KafkaTimeExtractor(
            event_time_field="timestamp",
            default_uncertainty=0.001
        )

        msg_time = extractor.extract(message)
        chrono_stamp = msg_time.to_chrono_stamp()
    """

    def __init__(
        self,
        event_time_field: Optional[str] = None,
        event_time_header: Optional[str] = None,
        event_time_extractor: Optional[Callable[[Dict], datetime]] = None,
        default_uncertainty: float = 0.001,
        use_kafka_timestamp: bool = True,
    ):
        """Initialize extractor.

        Args:
            event_time_field: JSON field name for event time
            event_time_header: Kafka header name for event time
            event_time_extractor: Custom function to extract event time
            default_uncertainty: Default time uncertainty (seconds)
            use_kafka_timestamp: Whether to use Kafka message timestamp
        """
        self.event_time_field = event_time_field
        self.event_time_header = event_time_header
        self.event_time_extractor = event_time_extractor
        self.default_uncertainty = default_uncertainty
        self.use_kafka_timestamp = use_kafka_timestamp

    def extract(
        self,
        message: Any,
        payload: Optional[Dict] = None,
    ) -> KafkaMessageTime:
        """Extract time information from a Kafka message.

        Args:
            message: Kafka message object (confluent-kafka or kafka-python)
            payload: Parsed message payload (if already parsed)

        Returns:
            KafkaMessageTime with extracted times
        """
        result = KafkaMessageTime(
            processing_time=datetime.now(tz=timezone.utc),
            uncertainty=self.default_uncertainty,
        )

        # Extract Kafka timestamp
        if self.use_kafka_timestamp:
            kafka_ts = self._get_kafka_timestamp(message)
            if kafka_ts:
                ts_type, ts_ms = kafka_ts
                result.timestamp_type = KafkaTimestampType(ts_type)

                if ts_ms > 0:
                    ts_dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)

                    if result.timestamp_type == KafkaTimestampType.CREATE_TIME:
                        result.event_time = ts_dt
                    elif result.timestamp_type == KafkaTimestampType.LOG_APPEND_TIME:
                        result.ingestion_time = ts_dt

        # Try to extract event time from payload
        if payload and self.event_time_field:
            event_time = self._extract_from_payload(payload)
            if event_time:
                result.event_time = event_time

        # Try to extract from header
        if self.event_time_header:
            event_time = self._extract_from_header(message)
            if event_time:
                result.event_time = event_time

        # Try custom extractor
        if self.event_time_extractor and payload:
            try:
                event_time = self.event_time_extractor(payload)
                if event_time:
                    result.event_time = event_time
            except Exception:
                pass

        return result

    def _get_kafka_timestamp(self, message: Any) -> Optional[tuple[int, int]]:
        """Get Kafka message timestamp.

        Returns:
            Tuple of (timestamp_type, timestamp_ms) or None
        """
        # confluent-kafka
        if hasattr(message, 'timestamp'):
            ts = message.timestamp()
            if ts and len(ts) == 2:
                return ts

        # kafka-python
        if hasattr(message, 'timestamp') and hasattr(message, 'timestamp_type'):
            return (message.timestamp_type, message.timestamp)

        return None

    def _extract_from_payload(self, payload: Dict) -> Optional[datetime]:
        """Extract event time from payload field."""
        if not self.event_time_field or self.event_time_field not in payload:
            return None

        value = payload[self.event_time_field]

        # Handle various formats
        if isinstance(value, datetime):
            return value

        if isinstance(value, (int, float)):
            # Assume milliseconds if > 1e12, otherwise seconds
            if value > 1e12:
                value = value / 1000.0
            return datetime.fromtimestamp(value, tz=timezone.utc)

        if isinstance(value, str):
            # Try ISO format
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                pass

        return None

    def _extract_from_header(self, message: Any) -> Optional[datetime]:
        """Extract event time from Kafka header."""
        if not self.event_time_header:
            return None

        headers = None

        # confluent-kafka
        if hasattr(message, 'headers') and callable(message.headers):
            headers = message.headers()
        # kafka-python
        elif hasattr(message, 'headers'):
            headers = message.headers

        if not headers:
            return None

        for key, value in headers:
            if key == self.event_time_header:
                try:
                    if isinstance(value, bytes):
                        value = value.decode('utf-8')

                    # Try as milliseconds
                    ts_ms = int(value)
                    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
                except (ValueError, TypeError):
                    pass

        return None


def extract_event_time(
    message: Any,
    field: Optional[str] = None,
    payload: Optional[Dict] = None,
) -> Optional[datetime]:
    """Extract event time from a Kafka message.

    Convenience function for simple extraction.

    Args:
        message: Kafka message
        field: Optional payload field name
        payload: Optional pre-parsed payload

    Returns:
        Event time datetime or None
    """
    extractor = KafkaTimeExtractor(event_time_field=field)
    result = extractor.extract(message, payload)
    return result.event_time


def extract_processing_time(message: Any = None) -> datetime:
    """Get current processing time.

    Args:
        message: Unused, for API consistency

    Returns:
        Current UTC datetime
    """
    return datetime.now(tz=timezone.utc)


@dataclass
class Watermark:
    """Watermark for event time progress tracking.

    Watermarks indicate that no events with timestamps earlier than
    the watermark time should be expected (with some slack).

    Attributes:
        time: Watermark time
        slack: Allowed lateness (events up to this late are still accepted)
        source: Source identifier for this watermark
    """
    time: datetime
    slack: float = 0.0  # seconds
    source: str = ""

    def allows(self, event_time: datetime) -> bool:
        """Check if an event time is allowed by this watermark.

        Args:
            event_time: Event time to check

        Returns:
            True if event is not too late
        """
        from datetime import timedelta
        cutoff = self.time - timedelta(seconds=self.slack)
        return event_time >= cutoff


class WatermarkTracker:
    """Tracks watermarks across multiple partitions/sources.

    Maintains per-source watermarks and computes the global minimum
    watermark for windowing operations.
    """

    def __init__(self, default_slack: float = 1.0):
        """Initialize tracker.

        Args:
            default_slack: Default lateness slack (seconds)
        """
        self.default_slack = default_slack
        self._watermarks: Dict[str, Watermark] = {}

    def update(
        self,
        source: str,
        time: datetime,
        slack: Optional[float] = None,
    ) -> None:
        """Update watermark for a source.

        Args:
            source: Source identifier
            time: New watermark time
            slack: Optional custom slack
        """
        self._watermarks[source] = Watermark(
            time=time,
            slack=slack if slack is not None else self.default_slack,
            source=source,
        )

    def get_global_watermark(self) -> Optional[Watermark]:
        """Get the global (minimum) watermark.

        Returns:
            Minimum watermark across all sources, or None if no watermarks
        """
        if not self._watermarks:
            return None

        min_wm = min(self._watermarks.values(), key=lambda w: w.time)
        return Watermark(
            time=min_wm.time,
            slack=max(w.slack for w in self._watermarks.values()),
            source="global",
        )

    def is_late(self, event_time: datetime) -> bool:
        """Check if an event is late according to global watermark.

        Args:
            event_time: Event time to check

        Returns:
            True if event is late (beyond watermark + slack)
        """
        global_wm = self.get_global_watermark()
        if not global_wm:
            return False
        return not global_wm.allows(event_time)
