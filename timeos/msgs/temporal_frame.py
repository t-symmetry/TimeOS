"""TemporalFrame - Coordinate system definition."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


import msgpack


@dataclass
class TemporalFrame:
    """A temporal coordinate frame definition.

    Defines a reference frame for temporal measurements, including
    the time standard, spatial reference, and validity period.

    Attributes:
        frame_id: Unique identifier for this frame
        parent_frame_id: Parent frame for hierarchical transforms (optional)
        time_standard: Time standard used ("TAI", "UTC", "GPS", "TT", "proper_time")
        spatial_reference: Spatial reference system ("WGS84", "ICRF", "custom")
        validity_start: Start of validity period (in parent frame time)
        validity_end: End of validity period (in parent frame time)
        confidence: Confidence level for this frame definition (0.0-1.0)
        authority: Publisher/authority identity
        tags: Metadata tags ("sim", "sensor", "inferred", "historical")
    """

    frame_id: str
    parent_frame_id: str | None = None
    time_standard: str = "TAI"
    spatial_reference: str = "ICRF"
    validity_start: float = float("-inf")
    validity_end: float = float("inf")
    confidence: float = 1.0
    authority: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        d = asdict(self)
        # Handle infinity for JSON
        if d["validity_start"] == float("-inf"):
            d["validity_start"] = None
        if d["validity_end"] == float("inf"):
            d["validity_end"] = None
        return d

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def to_msgpack(self) -> bytes:
        """Serialize to MessagePack bytes."""
        return msgpack.packb(self.to_dict(), use_bin_type=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemporalFrame:
        """Create from dictionary."""
        validity_start = data.get("validity_start")
        validity_end = data.get("validity_end")
        return cls(
            frame_id=data["frame_id"],
            parent_frame_id=data.get("parent_frame_id"),
            time_standard=data.get("time_standard", "TAI"),
            spatial_reference=data.get("spatial_reference", "ICRF"),
            validity_start=float("-inf") if validity_start is None else validity_start,
            validity_end=float("inf") if validity_end is None else validity_end,
            confidence=data.get("confidence", 1.0),
            authority=data.get("authority", ""),
            tags=data.get("tags", []),
        )

    @classmethod
    def from_json(cls, json_str: str) -> TemporalFrame:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_msgpack(cls, data: bytes) -> TemporalFrame:
        """Deserialize from MessagePack bytes."""
        return cls.from_dict(msgpack.unpackb(data, raw=False))

    def is_valid_at(self, t: float) -> bool:
        """Check if frame is valid at given time."""
        return self.validity_start <= t <= self.validity_end

    def is_child_of(self, other_frame_id: str) -> bool:
        """Check if this frame is a child of another frame."""
        return self.parent_frame_id == other_frame_id
