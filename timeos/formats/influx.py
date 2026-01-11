"""InfluxDB line protocol format.

Supports reading and writing InfluxDB line protocol for
time-series data with timestamps and uncertainty metadata.

Line protocol format:
    measurement,tag1=value1,tag2=value2 field1=value1,field2=value2 timestamp

Example:
    timeos_event,frame=lab,type=observation t=10.5,uncertainty=0.001 1704067200000000000
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any, Union


@dataclass
class InfluxPoint:
    """A single InfluxDB data point.

    Attributes:
        measurement: Measurement name (like a table name)
        tags: Tag key-value pairs (indexed, string only)
        fields: Field key-value pairs (not indexed, various types)
        timestamp_ns: Timestamp in nanoseconds since Unix epoch
    """
    measurement: str
    tags: Dict[str, str] = field(default_factory=dict)
    fields: Dict[str, Union[float, int, str, bool]] = field(default_factory=dict)
    timestamp_ns: Optional[int] = None

    @property
    def timestamp(self) -> Optional[datetime]:
        """Get timestamp as datetime."""
        if self.timestamp_ns is None:
            return None
        return datetime.fromtimestamp(self.timestamp_ns / 1e9, tz=timezone.utc)

    @timestamp.setter
    def timestamp(self, dt: datetime) -> None:
        """Set timestamp from datetime."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        self.timestamp_ns = int(dt.timestamp() * 1e9)

    @classmethod
    def from_seconds(
        cls,
        measurement: str,
        timestamp_seconds: float,
        tags: Optional[Dict[str, str]] = None,
        fields: Optional[Dict[str, Any]] = None,
    ) -> InfluxPoint:
        """Create point from seconds timestamp.

        Args:
            measurement: Measurement name
            timestamp_seconds: Unix timestamp in seconds
            tags: Optional tag dictionary
            fields: Optional field dictionary

        Returns:
            InfluxPoint instance
        """
        return cls(
            measurement=measurement,
            tags=tags or {},
            fields=fields or {},
            timestamp_ns=int(timestamp_seconds * 1e9),
        )


def _escape_tag_key(s: str) -> str:
    """Escape a tag key according to line protocol."""
    return s.replace("\\", "\\\\").replace(",", "\\,").replace("=", "\\=").replace(" ", "\\ ")


def _escape_tag_value(s: str) -> str:
    """Escape a tag value according to line protocol."""
    return s.replace("\\", "\\\\").replace(",", "\\,").replace("=", "\\=").replace(" ", "\\ ")


def _escape_field_key(s: str) -> str:
    """Escape a field key according to line protocol."""
    return s.replace("\\", "\\\\").replace(",", "\\,").replace("=", "\\=").replace(" ", "\\ ")


def _escape_string_field(s: str) -> str:
    """Escape a string field value according to line protocol."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _escape_measurement(s: str) -> str:
    """Escape measurement name according to line protocol."""
    return s.replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ")


def format_influx_line(point: InfluxPoint) -> str:
    """Format an InfluxPoint as line protocol string.

    Args:
        point: The data point to format

    Returns:
        Line protocol string

    Raises:
        ValueError: If point has no fields
    """
    if not point.fields:
        raise ValueError("InfluxPoint must have at least one field")

    parts = []

    # Measurement
    parts.append(_escape_measurement(point.measurement))

    # Tags (comma-separated, sorted for determinism)
    if point.tags:
        tag_parts = []
        for key in sorted(point.tags.keys()):
            value = point.tags[key]
            tag_parts.append(f"{_escape_tag_key(key)}={_escape_tag_value(value)}")
        parts[0] += "," + ",".join(tag_parts)

    # Fields (space after measurement/tags)
    field_parts = []
    for key in sorted(point.fields.keys()):
        value = point.fields[key]
        escaped_key = _escape_field_key(key)

        if isinstance(value, bool):
            field_parts.append(f"{escaped_key}={'true' if value else 'false'}")
        elif isinstance(value, int):
            field_parts.append(f"{escaped_key}={value}i")
        elif isinstance(value, float):
            field_parts.append(f"{escaped_key}={value}")
        elif isinstance(value, str):
            field_parts.append(f"{escaped_key}={_escape_string_field(value)}")
        else:
            # Convert to string
            field_parts.append(f"{escaped_key}={_escape_string_field(str(value))}")

    parts.append(",".join(field_parts))

    # Timestamp (optional)
    if point.timestamp_ns is not None:
        parts.append(str(point.timestamp_ns))

    return " ".join(parts)


def parse_influx_line(line: str) -> InfluxPoint:
    """Parse a line protocol string to InfluxPoint.

    Args:
        line: Line protocol string

    Returns:
        Parsed InfluxPoint

    Raises:
        ValueError: If line is invalid
    """
    line = line.strip()
    if not line or line.startswith("#"):
        raise ValueError("Empty or comment line")

    # Split into parts: measurement[,tags] fields [timestamp]
    # This is tricky because spaces can be escaped

    # State machine for parsing
    parts = []
    current = []
    i = 0
    in_quotes = False

    while i < len(line):
        c = line[i]

        if c == "\\" and i + 1 < len(line):
            # Escaped character
            current.append(line[i:i+2])
            i += 2
            continue

        if c == '"':
            in_quotes = not in_quotes
            current.append(c)
            i += 1
            continue

        if c == " " and not in_quotes:
            if current:
                parts.append("".join(current))
                current = []
            i += 1
            continue

        current.append(c)
        i += 1

    if current:
        parts.append("".join(current))

    if len(parts) < 2:
        raise ValueError(f"Invalid line protocol: {line}")

    # Parse measurement and tags
    measurement_tags = parts[0]

    # Split by unescaped commas
    mt_parts = _split_unescaped(measurement_tags, ",")

    measurement = _unescape(mt_parts[0])
    tags = {}

    for tag_str in mt_parts[1:]:
        key_val = _split_unescaped(tag_str, "=", max_split=1)
        if len(key_val) == 2:
            tags[_unescape(key_val[0])] = _unescape(key_val[1])

    # Parse fields
    fields_str = parts[1]
    field_parts = _split_unescaped(fields_str, ",")
    fields: Dict[str, Union[float, int, str, bool]] = {}

    for field_str in field_parts:
        key_val = _split_unescaped(field_str, "=", max_split=1)
        if len(key_val) != 2:
            continue

        key = _unescape(key_val[0])
        value_str = key_val[1]

        # Determine type
        if value_str.startswith('"') and value_str.endswith('"'):
            # String
            fields[key] = _unescape_string(value_str[1:-1])
        elif value_str.lower() in ("true", "t"):
            fields[key] = True
        elif value_str.lower() in ("false", "f"):
            fields[key] = False
        elif value_str.endswith("i"):
            # Integer
            try:
                fields[key] = int(value_str[:-1])
            except ValueError:
                fields[key] = value_str
        else:
            # Float
            try:
                fields[key] = float(value_str)
            except ValueError:
                fields[key] = value_str

    # Parse timestamp
    timestamp_ns = None
    if len(parts) >= 3:
        try:
            timestamp_ns = int(parts[2])
        except ValueError:
            pass

    return InfluxPoint(
        measurement=measurement,
        tags=tags,
        fields=fields,
        timestamp_ns=timestamp_ns,
    )


def _split_unescaped(s: str, delimiter: str, max_split: int = -1) -> List[str]:
    """Split string by unescaped delimiter."""
    parts = []
    current = []
    i = 0
    splits = 0

    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            current.append(s[i:i+2])
            i += 2
            continue

        if s[i] == delimiter and (max_split < 0 or splits < max_split):
            parts.append("".join(current))
            current = []
            splits += 1
            i += 1
            continue

        current.append(s[i])
        i += 1

    if current:
        parts.append("".join(current))

    return parts


def _unescape(s: str) -> str:
    """Remove escape characters."""
    result = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            result.append(s[i + 1])
            i += 2
        else:
            result.append(s[i])
            i += 1
    return "".join(result)


def _unescape_string(s: str) -> str:
    """Unescape a string field value."""
    return s.replace('\\"', '"').replace("\\\\", "\\")


def format_events_influx(
    events: List[Any],
    measurement: str = "timeos_event",
) -> str:
    """Format TimeOS events as InfluxDB line protocol.

    Args:
        events: List of TimelineEvent objects
        measurement: Measurement name to use

    Returns:
        Multi-line string of line protocol
    """
    lines = []

    for event in events:
        # Create tags from event metadata
        tags = {
            "frame": event.stamp.frame_id,
            "type": event.event_type,
            "branch": event.branch_id,
        }

        if event.author:
            tags["author"] = event.author

        # Create fields from event data
        fields: Dict[str, Any] = {
            "t": event.stamp.t,
            "uncertainty": event.stamp.t_uncertainty,
        }

        # Add event_id as field (too high cardinality for tag)
        fields["event_id"] = event.event_id

        # Use event time as timestamp (convert to nanoseconds)
        # Note: This uses t directly, which may be relative to a reference
        # In practice, you'd want to convert to absolute time
        timestamp_ns = int(event.stamp.t * 1e9) if event.stamp.t >= 0 else None

        point = InfluxPoint(
            measurement=measurement,
            tags=tags,
            fields=fields,
            timestamp_ns=timestamp_ns,
        )

        lines.append(format_influx_line(point))

    return "\n".join(lines)


def parse_influx_batch(data: str) -> List[InfluxPoint]:
    """Parse multiple lines of line protocol.

    Args:
        data: Multi-line line protocol string

    Returns:
        List of InfluxPoint objects
    """
    points = []

    for line in data.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            try:
                points.append(parse_influx_line(line))
            except ValueError:
                continue  # Skip invalid lines

    return points
