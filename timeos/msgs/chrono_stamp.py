"""ChronoStamp - Time with uncertainty."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

import msgpack


@dataclass
class ChronoStamp:
    """A timestamp with uncertainty bounds and provenance.

    Represents a point in time within a specific reference frame,
    with explicit uncertainty and source tracking.

    Attributes:
        frame_id: Reference frame identifier (e.g., "earth_tai", "lab_clock_a")
        t: Time coordinate in the reference frame (seconds)
        t_uncertainty: Uncertainty bounds ± (seconds)
        clock_id: Identifier of the source clock
        clock_class: Type of clock ("atomic", "ntp", "gps", "proper", "sim", "inferred")
        provenance: List of event IDs used to derive this timestamp
    """

    frame_id: str
    t: float
    t_uncertainty: float = 0.0
    clock_id: str = ""
    clock_class: str = "sim"
    provenance: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def to_msgpack(self) -> bytes:
        """Serialize to MessagePack bytes."""
        return msgpack.packb(self.to_dict(), use_bin_type=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChronoStamp:
        """Create from dictionary."""
        return cls(
            frame_id=data["frame_id"],
            t=data["t"],
            t_uncertainty=data.get("t_uncertainty", 0.0),
            clock_id=data.get("clock_id", ""),
            clock_class=data.get("clock_class", "sim"),
            provenance=data.get("provenance", []),
        )

    @classmethod
    def from_json(cls, json_str: str) -> ChronoStamp:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_msgpack(cls, data: bytes) -> ChronoStamp:
        """Deserialize from MessagePack bytes."""
        return cls.from_dict(msgpack.unpackb(data, raw=False))

    def __lt__(self, other: ChronoStamp) -> bool:
        """Compare timestamps (assumes same frame)."""
        if self.frame_id != other.frame_id:
            raise ValueError(f"Cannot compare stamps from different frames: {self.frame_id} vs {other.frame_id}")
        return self.t < other.t

    def __le__(self, other: ChronoStamp) -> bool:
        if self.frame_id != other.frame_id:
            raise ValueError(f"Cannot compare stamps from different frames: {self.frame_id} vs {other.frame_id}")
        return self.t <= other.t

    def overlaps(self, other: ChronoStamp) -> bool:
        """Check if uncertainty ranges overlap (assumes same frame)."""
        if self.frame_id != other.frame_id:
            raise ValueError(f"Cannot compare stamps from different frames: {self.frame_id} vs {other.frame_id}")
        return abs(self.t - other.t) <= (self.t_uncertainty + other.t_uncertainty)
