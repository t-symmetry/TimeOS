"""Timeline - Branch management for temporal event streams."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterator

from timeos.msgs import ChronoStamp, TimelineEvent
from timeos.core.event_log import EventLog


class MergePolicy(Enum):
    """Policy for handling merge conflicts."""

    FAIL = "fail"  # Abort on conflict
    KEEP_SOURCE = "keep_source"  # Prefer source branch events
    KEEP_TARGET = "keep_target"  # Prefer target branch events
    KEEP_BOTH = "keep_both"  # Include both (may create inconsistency)


@dataclass
class Branch:
    """Information about a timeline branch."""

    branch_id: str
    parent_branch: str | None
    fork_event_id: str | None
    event_count: int


class Timeline:
    """Timeline with branching support.

    Wraps an EventLog with branch management capabilities,
    supporting fork, merge, and consistent slicing operations.

    Example:
        log = EventLog("timeline.db")
        timeline = Timeline(log)

        # Create events on main branch
        event1 = timeline.create_event(stamp, "observation")

        # Fork a new branch
        timeline.branch("experiment_1", from_event=event1.event_id)

        # Add events to the new branch
        event2 = timeline.create_event(stamp2, "observation", branch_id="experiment_1")

        # List branches
        for branch in timeline.list_branches():
            print(branch.branch_id)
    """

    def __init__(self, log: EventLog):
        """Initialize timeline.

        Args:
            log: The underlying event log.
        """
        self.log = log
        self._current_branch = "main"
        self._author = ""
        self._seq_counters: dict[str, int] = {}

    @property
    def current_branch(self) -> str:
        """Get the current active branch."""
        return self._current_branch

    def set_branch(self, branch_id: str) -> None:
        """Set the current active branch.

        Args:
            branch_id: Branch to switch to.

        Raises:
            ValueError: If branch doesn't exist.
        """
        if not self._branch_exists(branch_id):
            raise ValueError(f"Branch '{branch_id}' does not exist")
        self._current_branch = branch_id

    def set_author(self, author: str) -> None:
        """Set the author for new events.

        Args:
            author: Author identifier.
        """
        self._author = author

    def _branch_exists(self, branch_id: str) -> bool:
        """Check if a branch exists."""
        row = self.log._conn.execute(
            "SELECT 1 FROM branches WHERE branch_id = ?", (branch_id,)
        ).fetchone()
        return row is not None

    def _next_seq(self) -> int:
        """Get the next sequence number for the current author."""
        if self._author not in self._seq_counters:
            # Get the max seq for this author from the log
            row = self.log._conn.execute(
                "SELECT MAX(seq) as max_seq FROM events WHERE author = ?",
                (self._author,),
            ).fetchone()
            self._seq_counters[self._author] = (row["max_seq"] or 0) + 1
        else:
            self._seq_counters[self._author] += 1
        return self._seq_counters[self._author]

    def create_event(
        self,
        stamp: ChronoStamp,
        event_type: str = "observation",
        payload: bytes = b"",
        payload_schema: str = "",
        parents: list[str] | None = None,
        branch_id: str | None = None,
    ) -> TimelineEvent:
        """Create and append a new event.

        Args:
            stamp: When the event occurred.
            event_type: Type of event.
            payload: Event-specific data.
            payload_schema: Schema reference for payload.
            parents: Parent event IDs (causal dependencies).
            branch_id: Branch to add event to (defaults to current branch).

        Returns:
            The created event.
        """
        branch = branch_id or self._current_branch

        if not self._branch_exists(branch):
            raise ValueError(f"Branch '{branch}' does not exist")

        event = TimelineEvent.create(
            stamp=stamp,
            event_type=event_type,
            payload=payload,
            payload_schema=payload_schema,
            parents=parents or [],
            branch_id=branch,
            author=self._author,
            seq=self._next_seq(),
        )

        self.log.append(event)
        return event

    def branch(self, name: str, from_event: str | None = None) -> str:
        """Create a new branch.

        Args:
            name: Name for the new branch.
            from_event: Event ID to fork from (optional).

        Returns:
            The new branch ID.

        Raises:
            ValueError: If branch already exists or event not found.
        """
        if self._branch_exists(name):
            raise ValueError(f"Branch '{name}' already exists")

        if from_event is not None:
            event = self.log.get(from_event)
            if event is None:
                raise ValueError(f"Event '{from_event}' not found")
            parent_branch = event.branch_id
        else:
            parent_branch = self._current_branch
            from_event = None

        self.log._conn.execute(
            """
            INSERT INTO branches (branch_id, parent_branch, fork_event_id)
            VALUES (?, ?, ?)
            """,
            (name, parent_branch, from_event),
        )
        self.log._conn.commit()

        return name

    def list_branches(self) -> list[Branch]:
        """List all branches.

        Returns:
            List of branch information.
        """
        rows = self.log._conn.execute("""
            SELECT b.branch_id, b.parent_branch, b.fork_event_id,
                   COUNT(e.event_id) as event_count
            FROM branches b
            LEFT JOIN events e ON e.branch_id = b.branch_id
            GROUP BY b.branch_id
            ORDER BY b.created_at
        """).fetchall()

        return [
            Branch(
                branch_id=row["branch_id"],
                parent_branch=row["parent_branch"],
                fork_event_id=row["fork_event_id"],
                event_count=row["event_count"],
            )
            for row in rows
        ]

    def get_branch(self, branch_id: str) -> Branch | None:
        """Get information about a specific branch.

        Args:
            branch_id: The branch ID.

        Returns:
            Branch information, or None if not found.
        """
        row = self.log._conn.execute(
            """
            SELECT b.branch_id, b.parent_branch, b.fork_event_id,
                   COUNT(e.event_id) as event_count
            FROM branches b
            LEFT JOIN events e ON e.branch_id = b.branch_id
            WHERE b.branch_id = ?
            GROUP BY b.branch_id
            """,
            (branch_id,),
        ).fetchone()

        if row is None:
            return None

        return Branch(
            branch_id=row["branch_id"],
            parent_branch=row["parent_branch"],
            fork_event_id=row["fork_event_id"],
            event_count=row["event_count"],
        )

    def delete_branch(self, branch_id: str, force: bool = False) -> None:
        """Delete a branch.

        Args:
            branch_id: Branch to delete.
            force: If True, delete even if branch has events.

        Raises:
            ValueError: If branch is main, doesn't exist, or has events (without force).
        """
        if branch_id == "main":
            raise ValueError("Cannot delete main branch")

        branch = self.get_branch(branch_id)
        if branch is None:
            raise ValueError(f"Branch '{branch_id}' does not exist")

        if branch.event_count > 0 and not force:
            raise ValueError(
                f"Branch '{branch_id}' has {branch.event_count} events. Use force=True to delete."
            )

        if force:
            # Delete events and their causal links
            self.log._conn.execute(
                "DELETE FROM causal_links WHERE child_id IN (SELECT event_id FROM events WHERE branch_id = ?)",
                (branch_id,),
            )
            self.log._conn.execute(
                "DELETE FROM events WHERE branch_id = ?", (branch_id,)
            )

        self.log._conn.execute(
            "DELETE FROM branches WHERE branch_id = ?", (branch_id,)
        )
        self.log._conn.commit()

        if self._current_branch == branch_id:
            self._current_branch = "main"

    def slice(
        self,
        branch_id: str | None = None,
        start: float | None = None,
        end: float | None = None,
        frame_id: str | None = None,
        include_ancestors: bool = False,
    ) -> Iterator[TimelineEvent]:
        """Get a slice of events from a branch.

        Args:
            branch_id: Branch to slice (defaults to current).
            start: Start time (inclusive).
            end: End time (inclusive).
            frame_id: Filter by frame ID.
            include_ancestors: If True, include events from parent branches.

        Yields:
            Events in the slice, ordered by time.
        """
        branch = branch_id or self._current_branch

        if include_ancestors:
            # Get branch lineage
            branches = [branch]
            current = branch
            while True:
                row = self.log._conn.execute(
                    "SELECT parent_branch FROM branches WHERE branch_id = ?",
                    (current,),
                ).fetchone()
                if row is None or row["parent_branch"] is None:
                    break
                branches.append(row["parent_branch"])
                current = row["parent_branch"]

            # Query events from all branches in lineage
            for b in reversed(branches):  # Start from oldest ancestor
                yield from self.log.query(
                    start=start,
                    end=end,
                    frame_id=frame_id,
                    branch_id=b,
                )
        else:
            yield from self.log.query(
                start=start,
                end=end,
                frame_id=frame_id,
                branch_id=branch,
            )

    def merge(
        self,
        source: str,
        target: str | None = None,
        policy: MergePolicy = MergePolicy.FAIL,
    ) -> TimelineEvent:
        """Merge one branch into another.

        Args:
            source: Source branch to merge from.
            target: Target branch to merge into (defaults to current).
            policy: How to handle conflicts.

        Returns:
            The merge event created in the target branch.

        Raises:
            ValueError: If branches don't exist or merge fails.
        """
        target = target or self._current_branch

        if not self._branch_exists(source):
            raise ValueError(f"Source branch '{source}' does not exist")
        if not self._branch_exists(target):
            raise ValueError(f"Target branch '{target}' does not exist")

        # Get the latest event from source branch
        source_events = list(self.log.query(branch_id=source))
        if not source_events:
            raise ValueError(f"Source branch '{source}' has no events")

        latest_source = source_events[-1]

        # Get the latest event from target branch (if any)
        target_events = list(self.log.query(branch_id=target))
        latest_target = target_events[-1] if target_events else None

        # Create merge event
        parents = [latest_source.event_id]
        if latest_target:
            parents.append(latest_target.event_id)

        # Use the later timestamp for the merge event
        merge_time = max(
            latest_source.stamp.t,
            latest_target.stamp.t if latest_target else float("-inf"),
        )

        merge_stamp = ChronoStamp(
            frame_id=latest_source.stamp.frame_id,
            t=merge_time,
            clock_class="inferred",
            provenance=[latest_source.event_id],
        )

        merge_event = self.create_event(
            stamp=merge_stamp,
            event_type="merge",
            payload=f"Merged {source} into {target}".encode(),
            parents=parents,
            branch_id=target,
        )

        return merge_event
