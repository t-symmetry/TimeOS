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

    def query_uncertain(
        self,
        t_start: float | None = None,
        t_end: float | None = None,
        t_start_uncertainty: float = 0.0,
        t_end_uncertainty: float = 0.0,
        frame_id: str | None = None,
        branch_id: str | None = None,
        include_overlapping: bool = True,
    ) -> Iterator[TimelineEvent]:
        """Query events with uncertainty-aware time range.

        Unlike the standard query, this method considers time uncertainties
        when matching events. An event matches if its uncertainty interval
        overlaps with the query interval.

        Args:
            t_start: Start time for query range.
            t_end: End time for query range.
            t_start_uncertainty: Uncertainty on start time.
            t_end_uncertainty: Uncertainty on end time.
            frame_id: Filter by frame ID.
            branch_id: Filter by branch ID.
            include_overlapping: If True, include events whose uncertainty
                intervals overlap the query range (even if nominal time is outside).

        Yields:
            Matching events, ordered by time.

        Example:
            # Find events around t=10s ± 0.1s
            events = log.query_uncertain(
                t_start=9.9, t_end=10.1,
                t_start_uncertainty=0.01, t_end_uncertainty=0.01,
                include_overlapping=True
            )
        """
        # Expand the range to account for uncertainties
        if include_overlapping:
            # Need to fetch events that might overlap
            # An event at time t with uncertainty u overlaps if:
            # t - u <= t_end + t_end_uncertainty AND t + u >= t_start - t_start_uncertainty
            # We can't know u in the query, so we fetch a wider range
            # and filter in Python
            fetch_start = t_start - 1.0 if t_start is not None else None  # 1 second margin
            fetch_end = t_end + 1.0 if t_end is not None else None
        else:
            fetch_start = t_start
            fetch_end = t_end

        for event in self.query(
            start=fetch_start,
            end=fetch_end,
            frame_id=frame_id,
            branch_id=branch_id,
        ):
            if include_overlapping:
                # Check if event's uncertainty interval overlaps query range
                event_t = event.stamp.t
                event_u = event.stamp.t_uncertainty

                event_min = event_t - event_u
                event_max = event_t + event_u

                query_min = (t_start - t_start_uncertainty) if t_start is not None else float('-inf')
                query_max = (t_end + t_end_uncertainty) if t_end is not None else float('inf')

                # Check overlap
                if event_max >= query_min and event_min <= query_max:
                    yield event
            else:
                # Standard range check
                if t_start is not None and event.stamp.t < t_start:
                    continue
                if t_end is not None and event.stamp.t > t_end:
                    continue
                yield event

    def causal_ancestors(
        self,
        event_id: str,
        max_depth: int | None = None,
    ) -> list[TimelineEvent]:
        """Get all causal ancestors of an event.

        Traverses the causal graph backwards to find all events
        that this event depends on (directly or indirectly).

        Args:
            event_id: The event to find ancestors for.
            max_depth: Maximum depth to traverse (None = unlimited).

        Returns:
            List of ancestor events, ordered by depth (closest first).
        """
        ancestors = []
        visited: set[str] = set()
        queue = [(event_id, 0)]  # (event_id, depth)

        while queue:
            current_id, depth = queue.pop(0)

            if current_id in visited:
                continue

            if current_id != event_id:  # Don't include the starting event
                visited.add(current_id)
                event = self.get(current_id)
                if event:
                    ancestors.append(event)

            if max_depth is not None and depth >= max_depth:
                continue

            # Add parents to queue
            for parent_id in self.get_parents(current_id):
                if parent_id not in visited:
                    queue.append((parent_id, depth + 1))

        return ancestors

    def causal_descendants(
        self,
        event_id: str,
        max_depth: int | None = None,
    ) -> list[TimelineEvent]:
        """Get all causal descendants of an event.

        Traverses the causal graph forwards to find all events
        that depend on this event (directly or indirectly).

        Args:
            event_id: The event to find descendants for.
            max_depth: Maximum depth to traverse (None = unlimited).

        Returns:
            List of descendant events, ordered by depth (closest first).
        """
        descendants = []
        visited: set[str] = set()
        queue = [(event_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)

            if current_id in visited:
                continue

            if current_id != event_id:
                visited.add(current_id)
                event = self.get(current_id)
                if event:
                    descendants.append(event)

            if max_depth is not None and depth >= max_depth:
                continue

            for child_id in self.get_children(current_id):
                if child_id not in visited:
                    queue.append((child_id, depth + 1))

        return descendants

    def concurrent_with(
        self,
        event_id: str,
        frame_id: str | None = None,
    ) -> list[TimelineEvent]:
        """Find events that are concurrent (spacelike separated) with an event.

        Two events are concurrent if neither is a causal ancestor/descendant
        of the other. In relativistic terms, they are spacelike separated.

        Args:
            event_id: The reference event.
            frame_id: Filter by frame ID.

        Returns:
            List of concurrent events.
        """
        event = self.get(event_id)
        if not event:
            return []

        # Get all causally related events
        ancestors = set(e.event_id for e in self.causal_ancestors(event_id))
        descendants = set(e.event_id for e in self.causal_descendants(event_id))
        causally_related = ancestors | descendants | {event_id}

        # Find events that overlap in time but aren't causally related
        concurrent = []

        # Query events in a time window around this event
        margin = max(1.0, event.stamp.t_uncertainty * 10)
        for other in self.query(
            start=event.stamp.t - margin,
            end=event.stamp.t + margin,
            frame_id=frame_id or event.stamp.frame_id,
        ):
            if other.event_id not in causally_related:
                concurrent.append(other)

        return concurrent

    def overlapping_events(
        self,
        event_id: str,
        frame_id: str | None = None,
    ) -> list[TimelineEvent]:
        """Find events whose time uncertainty intervals overlap with an event.

        Useful for identifying events that cannot be temporally distinguished
        given their measurement uncertainties.

        Args:
            event_id: The reference event.
            frame_id: Filter by frame ID.

        Returns:
            List of events with overlapping time intervals.
        """
        event = self.get(event_id)
        if not event:
            return []

        overlapping = []

        # Search window based on uncertainty
        margin = max(1.0, event.stamp.t_uncertainty * 3)

        for other in self.query(
            start=event.stamp.t - margin,
            end=event.stamp.t + margin,
            frame_id=frame_id or event.stamp.frame_id,
        ):
            if other.event_id == event_id:
                continue

            # Check if uncertainty intervals overlap
            if event.stamp.overlaps(other.stamp):
                overlapping.append(other)

        return overlapping

    def get_causal_graph(
        self,
        branch_id: str | None = None,
    ) -> dict[str, list[str]]:
        """Get the complete causal graph as an adjacency list.

        Args:
            branch_id: Optional branch to filter by.

        Returns:
            Dictionary mapping event_id -> list of parent event_ids.
        """
        if branch_id is not None:
            events = self.query(branch_id=branch_id)
        else:
            events = self.query()

        graph = {}
        for event in events:
            graph[event.event_id] = self.get_parents(event.event_id)

        return graph

    def find_roots(
        self,
        branch_id: str | None = None,
    ) -> list[TimelineEvent]:
        """Find root events (events with no parents).

        Args:
            branch_id: Optional branch to filter by.

        Returns:
            List of root events.
        """
        roots = []

        for event in self.query(branch_id=branch_id):
            parents = self.get_parents(event.event_id)
            if not parents:
                roots.append(event)

        return roots

    def find_leaves(
        self,
        branch_id: str | None = None,
    ) -> list[TimelineEvent]:
        """Find leaf events (events with no children).

        Args:
            branch_id: Optional branch to filter by.

        Returns:
            List of leaf events.
        """
        leaves = []

        for event in self.query(branch_id=branch_id):
            children = self.get_children(event.event_id)
            if not children:
                leaves.append(event)

        return leaves

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> EventLog:
        return self

    def __exit__(self, *args) -> None:
        self.close()
