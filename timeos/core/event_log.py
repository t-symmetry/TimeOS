"""EventLog - Append-only temporal event storage."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterator

import msgpack

from timeos.msgs import ChronoStamp, TimelineEvent


class EventLog:
    """Append-only storage for TimelineEvents.

    Stores events in SQLite with msgpack serialization for efficiency.
    Supports querying by time range, event ID, and branch.

    Example:
        log = EventLog("timeline.db")
        event = TimelineEvent.create(
            stamp=ChronoStamp(frame_id="lab", t=0.0),
            event_type="observation"
        )
        log.append(event)
        events = list(log.query(start=0.0, end=10.0, frame_id="lab"))
    """

    def __init__(self, path: str | Path = ":memory:"):
        """Initialize event log.

        Args:
            path: Path to SQLite database, or ":memory:" for in-memory store.
        """
        self.path = Path(path) if path != ":memory:" else path
        self._conn = sqlite3.connect(
            str(self.path) if isinstance(self.path, Path) else self.path,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                frame_id TEXT NOT NULL,
                t REAL NOT NULL,
                branch_id TEXT NOT NULL DEFAULT 'main',
                event_type TEXT NOT NULL,
                author TEXT,
                seq INTEGER,
                data BLOB NOT NULL,
                created_at REAL DEFAULT (julianday('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_events_frame_time
                ON events(frame_id, t);

            CREATE INDEX IF NOT EXISTS idx_events_branch
                ON events(branch_id, t);

            CREATE INDEX IF NOT EXISTS idx_events_author
                ON events(author, seq);

            CREATE TABLE IF NOT EXISTS causal_links (
                child_id TEXT NOT NULL,
                parent_id TEXT NOT NULL,
                PRIMARY KEY (child_id, parent_id),
                FOREIGN KEY (child_id) REFERENCES events(event_id),
                FOREIGN KEY (parent_id) REFERENCES events(event_id)
            );

            CREATE INDEX IF NOT EXISTS idx_causal_parents
                ON causal_links(parent_id);

            CREATE TABLE IF NOT EXISTS branches (
                branch_id TEXT PRIMARY KEY,
                parent_branch TEXT,
                fork_event_id TEXT,
                created_at REAL DEFAULT (julianday('now')),
                FOREIGN KEY (fork_event_id) REFERENCES events(event_id)
            );

            INSERT OR IGNORE INTO branches (branch_id, parent_branch)
                VALUES ('main', NULL);
        """)
        self._conn.commit()

    def append(self, event: TimelineEvent) -> None:
        """Append an event to the log.

        Args:
            event: The event to append.

        Raises:
            ValueError: If event ID already exists.
        """
        data = event.to_msgpack()

        try:
            self._conn.execute(
                """
                INSERT INTO events (event_id, frame_id, t, branch_id, event_type, author, seq, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.stamp.frame_id,
                    event.stamp.t,
                    event.branch_id,
                    event.event_type,
                    event.author,
                    event.seq,
                    data,
                ),
            )

            # Insert causal links
            for parent_id in event.parents:
                self._conn.execute(
                    "INSERT OR IGNORE INTO causal_links (child_id, parent_id) VALUES (?, ?)",
                    (event.event_id, parent_id),
                )

            self._conn.commit()
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Event {event.event_id} already exists") from e

    def get(self, event_id: str) -> TimelineEvent | None:
        """Get an event by ID.

        Args:
            event_id: The event ID to look up.

        Returns:
            The event, or None if not found.
        """
        row = self._conn.execute(
            "SELECT data FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()

        if row is None:
            return None

        return TimelineEvent.from_msgpack(row["data"])

    def query(
        self,
        start: float | None = None,
        end: float | None = None,
        frame_id: str | None = None,
        branch_id: str | None = None,
        event_type: str | None = None,
        author: str | None = None,
        limit: int | None = None,
    ) -> Iterator[TimelineEvent]:
        """Query events by various criteria.

        Args:
            start: Minimum time (inclusive).
            end: Maximum time (inclusive).
            frame_id: Filter by frame ID.
            branch_id: Filter by branch ID.
            event_type: Filter by event type.
            author: Filter by author.
            limit: Maximum number of results.

        Yields:
            Matching events, ordered by time.
        """
        conditions = []
        params: list = []

        if start is not None:
            conditions.append("t >= ?")
            params.append(start)
        if end is not None:
            conditions.append("t <= ?")
            params.append(end)
        if frame_id is not None:
            conditions.append("frame_id = ?")
            params.append(frame_id)
        if branch_id is not None:
            conditions.append("branch_id = ?")
            params.append(branch_id)
        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type)
        if author is not None:
            conditions.append("author = ?")
            params.append(author)

        where = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT data FROM events WHERE {where} ORDER BY t ASC"

        if limit is not None:
            query += f" LIMIT {limit}"

        for row in self._conn.execute(query, params):
            yield TimelineEvent.from_msgpack(row["data"])

    def get_parents(self, event_id: str) -> list[str]:
        """Get parent event IDs for an event.

        Args:
            event_id: The event ID.

        Returns:
            List of parent event IDs.
        """
        rows = self._conn.execute(
            "SELECT parent_id FROM causal_links WHERE child_id = ?", (event_id,)
        ).fetchall()
        return [row["parent_id"] for row in rows]

    def get_children(self, event_id: str) -> list[str]:
        """Get child event IDs for an event.

        Args:
            event_id: The event ID.

        Returns:
            List of child event IDs.
        """
        rows = self._conn.execute(
            "SELECT child_id FROM causal_links WHERE parent_id = ?", (event_id,)
        ).fetchall()
        return [row["child_id"] for row in rows]

    def count(self, branch_id: str | None = None) -> int:
        """Count events in the log.

        Args:
            branch_id: Optional branch to filter by.

        Returns:
            Number of events.
        """
        if branch_id is not None:
            row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM events WHERE branch_id = ?", (branch_id,)
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) as cnt FROM events").fetchone()
        return row["cnt"]

    def export_json(self, path: str | Path) -> None:
        """Export all events to JSON file.

        Args:
            path: Output file path.
        """
        events = [event.to_dict() for event in self.query()]
        with open(path, "w") as f:
            json.dump({"events": events}, f, indent=2)

    def import_json(self, path: str | Path) -> int:
        """Import events from JSON file.

        Args:
            path: Input file path.

        Returns:
            Number of events imported.
        """
        with open(path) as f:
            data = json.load(f)

        count = 0
        for event_data in data.get("events", []):
            event = TimelineEvent.from_dict(event_data)
            try:
                self.append(event)
                count += 1
            except ValueError:
                pass  # Skip duplicates

        return count

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> EventLog:
        return self

    def __exit__(self, *args) -> None:
        self.close()
