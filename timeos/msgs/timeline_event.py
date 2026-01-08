"""TimelineEvent - Universal event envelope."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any
import base64

import msgpack

from timeos.msgs.chrono_stamp import ChronoStamp


@dataclass
class TimelineEvent:
    """A universal envelope for temporal events.

    Wraps any event with temporal metadata, causal links,
    and provenance information.

    Attributes:
        event_id: Unique identifier (UUID)
        stamp: When the event occurred (ChronoStamp)
        event_type: Type of event ("observation", "actuation", "annotation", "constraint")
        payload: Event-specific data (bytes)
        payload_schema: Schema reference for payload (e.g., "timeos/SensorReading@1")
        parents: Event IDs this event causally depends on
        branch_id: Timeline branch this event belongs to
        author: Identity of event creator
        seq: Sequence number (per-author, for ordering)
    """

    event_id: str
    stamp: ChronoStamp
    event_type: str = "observation"
    payload: bytes = b""
    payload_schema: str = ""
    parents: list[str] = field(default_factory=list)
    branch_id: str = "main"
    author: str = ""
    seq: int = 0

    @classmethod
    def create(
        cls,
        stamp: ChronoStamp,
        event_type: str = "observation",
        payload: bytes = b"",
        payload_schema: str = "",
        parents: list[str] | None = None,
        branch_id: str = "main",
        author: str = "",
        seq: int = 0,
    ) -> TimelineEvent:
        """Create a new event with auto-generated ID."""
        return cls(
            event_id=str(uuid.uuid4()),
            stamp=stamp,
            event_type=event_type,
            payload=payload,
            payload_schema=payload_schema,
            parents=parents or [],
            branch_id=branch_id,
            author=author,
            seq=seq,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        d = asdict(self)
        # Convert stamp to nested dict
        d["stamp"] = self.stamp.to_dict()
        # Base64 encode payload for JSON compatibility
        d["payload"] = base64.b64encode(self.payload).decode("ascii")
        return d

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def to_msgpack(self) -> bytes:
        """Serialize to MessagePack bytes."""
        d = asdict(self)
        d["stamp"] = self.stamp.to_dict()
        # Keep payload as raw bytes for msgpack
        d["payload"] = self.payload
        return msgpack.packb(d, use_bin_type=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineEvent:
        """Create from dictionary."""
        stamp_data = data["stamp"]
        stamp = ChronoStamp.from_dict(stamp_data) if isinstance(stamp_data, dict) else stamp_data

        # Handle base64 encoded payload (from JSON)
        payload = data.get("payload", b"")
        if isinstance(payload, str):
            payload = base64.b64decode(payload)

        return cls(
            event_id=data["event_id"],
            stamp=stamp,
            event_type=data.get("event_type", "observation"),
            payload=payload,
            payload_schema=data.get("payload_schema", ""),
            parents=data.get("parents", []),
            branch_id=data.get("branch_id", "main"),
            author=data.get("author", ""),
            seq=data.get("seq", 0),
        )

    @classmethod
    def from_json(cls, json_str: str) -> TimelineEvent:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_msgpack(cls, data: bytes) -> TimelineEvent:
        """Deserialize from MessagePack bytes."""
        return cls.from_dict(msgpack.unpackb(data, raw=False))

    def depends_on(self, event_id: str) -> bool:
        """Check if this event directly depends on another event."""
        return event_id in self.parents

    def is_root(self) -> bool:
        """Check if this event has no parents (root event)."""
        return len(self.parents) == 0
