"""Annotations - Narrative layer for timeline events.

Annotations provide a non-technical documentation layer that rides
on top of the causal system. They are:
- Markdown-formatted text
- Linked to specific events
- Not causally relevant (don't affect constraint checking)
- Useful for debugging, storytelling, and documentation

This turns TimeOS into:
- A timeline debugger
- A story generator
- A speculative lab notebook
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional
from enum import Enum


class AnnotationType(Enum):
    """Types of annotations."""

    NOTE = "note"           # General note
    HYPOTHESIS = "hypothesis"  # Scientific hypothesis
    OBSERVATION = "observation"  # Observational note
    WARNING = "warning"     # Warning or caution
    TODO = "todo"           # Action item
    QUESTION = "question"   # Question or uncertainty
    NARRATIVE = "narrative"  # Story/narrative element


@dataclass
class Annotation:
    """A narrative annotation attached to a timeline event.

    Annotations are markdown-formatted text that provide context,
    documentation, or storytelling without affecting causality.

    Attributes:
        annotation_id: Unique identifier
        event_id: The event this annotation is attached to
        content: Markdown-formatted text
        annotation_type: Classification of the annotation
        author: Who created this annotation
        created_at: When the annotation was created
        tags: Optional tags for categorization
    """

    annotation_id: str
    event_id: str
    content: str
    annotation_type: AnnotationType = AnnotationType.NOTE
    author: str = ""
    created_at: str = ""
    tags: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        event_id: str,
        content: str,
        annotation_type: AnnotationType = AnnotationType.NOTE,
        author: str = "",
        tags: list[str] | None = None,
    ) -> Annotation:
        """Create a new annotation."""
        return cls(
            annotation_id=str(uuid.uuid4()),
            event_id=event_id,
            content=content,
            annotation_type=annotation_type,
            author=author,
            created_at=datetime.now().isoformat(),
            tags=tags or [],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        d = asdict(self)
        d["annotation_type"] = self.annotation_type.value
        return d

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Annotation:
        """Create from dictionary."""
        return cls(
            annotation_id=data["annotation_id"],
            event_id=data["event_id"],
            content=data["content"],
            annotation_type=AnnotationType(data.get("annotation_type", "note")),
            author=data.get("author", ""),
            created_at=data.get("created_at", ""),
            tags=data.get("tags", []),
        )

    @classmethod
    def from_json(cls, json_str: str) -> Annotation:
        """Deserialize from JSON."""
        return cls.from_dict(json.loads(json_str))

    @property
    def icon(self) -> str:
        """Get icon for this annotation type."""
        icons = {
            AnnotationType.NOTE: "📝",
            AnnotationType.HYPOTHESIS: "🔬",
            AnnotationType.OBSERVATION: "👁",
            AnnotationType.WARNING: "⚠️",
            AnnotationType.TODO: "☐",
            AnnotationType.QUESTION: "❓",
            AnnotationType.NARRATIVE: "📖",
        }
        return icons.get(self.annotation_type, "📝")


class AnnotationStore:
    """In-memory store for annotations.

    Provides CRUD operations and queries for annotations.
    Can be extended to persist to SQLite alongside the event log.
    """

    def __init__(self):
        """Initialize empty annotation store."""
        self._annotations: dict[str, Annotation] = {}
        self._by_event: dict[str, list[str]] = {}  # event_id -> [annotation_ids]

    def add(self, annotation: Annotation) -> None:
        """Add an annotation to the store."""
        self._annotations[annotation.annotation_id] = annotation

        if annotation.event_id not in self._by_event:
            self._by_event[annotation.event_id] = []
        self._by_event[annotation.event_id].append(annotation.annotation_id)

    def get(self, annotation_id: str) -> Optional[Annotation]:
        """Get annotation by ID."""
        return self._annotations.get(annotation_id)

    def delete(self, annotation_id: str) -> bool:
        """Delete an annotation."""
        annotation = self._annotations.pop(annotation_id, None)
        if annotation:
            event_ids = self._by_event.get(annotation.event_id, [])
            if annotation_id in event_ids:
                event_ids.remove(annotation_id)
            return True
        return False

    def for_event(self, event_id: str) -> list[Annotation]:
        """Get all annotations for an event."""
        annotation_ids = self._by_event.get(event_id, [])
        return [self._annotations[aid] for aid in annotation_ids if aid in self._annotations]

    def all(self) -> list[Annotation]:
        """Get all annotations."""
        return list(self._annotations.values())

    def by_type(self, annotation_type: AnnotationType) -> list[Annotation]:
        """Get annotations by type."""
        return [a for a in self._annotations.values() if a.annotation_type == annotation_type]

    def by_tag(self, tag: str) -> list[Annotation]:
        """Get annotations by tag."""
        return [a for a in self._annotations.values() if tag in a.tags]

    def search(self, query: str) -> list[Annotation]:
        """Search annotations by content."""
        query_lower = query.lower()
        return [a for a in self._annotations.values() if query_lower in a.content.lower()]

    def export_json(self) -> str:
        """Export all annotations to JSON."""
        return json.dumps([a.to_dict() for a in self._annotations.values()], indent=2)

    def import_json(self, json_str: str) -> int:
        """Import annotations from JSON. Returns count imported."""
        data = json.loads(json_str)
        count = 0
        for item in data:
            annotation = Annotation.from_dict(item)
            self.add(annotation)
            count += 1
        return count
