"""Constraints - Causality checking for temporal events."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from timeos.core.timeline import Timeline
    from timeos.msgs import TimelineEvent


class Action(Enum):
    """Suggested action for constraint violations."""

    ACCEPT = "accept"  # Allow the event
    REJECT = "reject"  # Reject the event
    BRANCH = "branch"  # Create a new branch for the event
    WARN = "warn"  # Accept but log a warning


@dataclass
class ValidationResult:
    """Result of validating an event against constraints.

    Attributes:
        valid: Whether all constraints passed.
        violations: List of violation descriptions.
        suggested_action: Recommended action based on violations.
        constraint_name: Name of the constraint that was checked.
    """

    valid: bool
    violations: list[str] = field(default_factory=list)
    suggested_action: Action = Action.ACCEPT
    constraint_name: str = ""

    def __bool__(self) -> bool:
        return self.valid

    @classmethod
    def ok(cls, constraint_name: str = "") -> ValidationResult:
        """Create a passing result."""
        return cls(valid=True, constraint_name=constraint_name)

    @classmethod
    def fail(
        cls,
        violation: str,
        action: Action = Action.REJECT,
        constraint_name: str = "",
    ) -> ValidationResult:
        """Create a failing result."""
        return cls(
            valid=False,
            violations=[violation],
            suggested_action=action,
            constraint_name=constraint_name,
        )


class Constraint(ABC):
    """Abstract base class for causality constraints.

    Subclass this to implement custom constraint logic.

    Example:
        class MyConstraint(Constraint):
            name = "my_constraint"

            def validate(self, event, timeline):
                if some_condition(event):
                    return ValidationResult.fail("Condition not met")
                return ValidationResult.ok()
    """

    name: str = "unnamed"

    @abstractmethod
    def validate(
        self, event: TimelineEvent, timeline: Timeline
    ) -> ValidationResult:
        """Validate an event against this constraint.

        Args:
            event: The event to validate.
            timeline: The timeline context.

        Returns:
            Validation result indicating success or failure.
        """
        pass


class CausalOrderConstraint(Constraint):
    """Constraint: Parent events must occur before child events.

    Ensures that all events listed in an event's `parents` field
    have timestamps that precede the event's timestamp.
    """

    name = "causal_order"

    def validate(
        self, event: TimelineEvent, timeline: Timeline
    ) -> ValidationResult:
        if not event.parents:
            return ValidationResult.ok(self.name)

        for parent_id in event.parents:
            parent = timeline.log.get(parent_id)

            if parent is None:
                return ValidationResult.fail(
                    f"Parent event '{parent_id}' not found",
                    Action.REJECT,
                    self.name,
                )

            # Check if frames are compatible (same frame for now)
            if parent.stamp.frame_id != event.stamp.frame_id:
                # TODO: Implement frame transformation
                return ValidationResult.fail(
                    f"Parent event '{parent_id}' is in different frame "
                    f"({parent.stamp.frame_id} vs {event.stamp.frame_id})",
                    Action.WARN,
                    self.name,
                )

            # Check temporal ordering
            if parent.stamp.t > event.stamp.t:
                return ValidationResult.fail(
                    f"Parent event '{parent_id}' (t={parent.stamp.t}) "
                    f"occurs after child (t={event.stamp.t})",
                    Action.REJECT,
                    self.name,
                )

            # Check uncertainty overlap
            if not parent.stamp.overlaps(event.stamp) and parent.stamp.t >= event.stamp.t:
                return ValidationResult.fail(
                    f"Parent event '{parent_id}' may not precede child "
                    f"within uncertainty bounds",
                    Action.WARN,
                    self.name,
                )

        return ValidationResult.ok(self.name)


class NoSelfCausation(Constraint):
    """Constraint: An event cannot be its own ancestor.

    Detects causal loops by traversing the parent graph.
    """

    name = "no_self_causation"

    def __init__(self, max_depth: int = 100):
        """Initialize constraint.

        Args:
            max_depth: Maximum depth to search for cycles.
        """
        self.max_depth = max_depth

    def validate(
        self, event: TimelineEvent, timeline: Timeline
    ) -> ValidationResult:
        if not event.parents:
            return ValidationResult.ok(self.name)

        # BFS to find if event_id appears in its own ancestor chain
        visited: set[str] = set()
        queue = list(event.parents)
        depth = 0

        while queue and depth < self.max_depth:
            current_id = queue.pop(0)

            if current_id == event.event_id:
                return ValidationResult.fail(
                    f"Event '{event.event_id}' is its own ancestor (causal loop detected)",
                    Action.REJECT,
                    self.name,
                )

            if current_id in visited:
                continue

            visited.add(current_id)
            parent_event = timeline.log.get(current_id)

            if parent_event is not None:
                queue.extend(parent_event.parents)
                depth += 1

        return ValidationResult.ok(self.name)


class BranchConsistency(Constraint):
    """Constraint: No cross-branch causal references without merge.

    Events can only reference parents from the same branch or
    from an ancestor branch that was properly merged.
    """

    name = "branch_consistency"

    def validate(
        self, event: TimelineEvent, timeline: Timeline
    ) -> ValidationResult:
        if not event.parents:
            return ValidationResult.ok(self.name)

        # Get the branch lineage for this event's branch
        branch_lineage = self._get_branch_lineage(event.branch_id, timeline)

        for parent_id in event.parents:
            parent = timeline.log.get(parent_id)

            if parent is None:
                # Parent not found is handled by CausalOrderConstraint
                continue

            # Check if parent is in same branch or an ancestor branch
            if parent.branch_id not in branch_lineage:
                # Check if there's a merge event connecting the branches
                if not self._is_merged(parent.branch_id, event.branch_id, timeline):
                    return ValidationResult.fail(
                        f"Parent event '{parent_id}' is in branch '{parent.branch_id}' "
                        f"which is not an ancestor of '{event.branch_id}' "
                        f"and has not been merged",
                        Action.BRANCH,
                        self.name,
                    )

        return ValidationResult.ok(self.name)

    def _get_branch_lineage(self, branch_id: str, timeline: Timeline) -> set[str]:
        """Get all ancestor branches including the current branch."""
        lineage = {branch_id}
        current = branch_id

        while True:
            row = timeline.log._conn.execute(
                "SELECT parent_branch FROM branches WHERE branch_id = ?",
                (current,),
            ).fetchone()

            if row is None or row["parent_branch"] is None:
                break

            lineage.add(row["parent_branch"])
            current = row["parent_branch"]

        return lineage

    def _is_merged(self, source: str, target: str, timeline: Timeline) -> bool:
        """Check if source branch has been merged into target branch lineage."""
        target_lineage = self._get_branch_lineage(target, timeline)

        # Look for a merge event from source into any branch in target's lineage
        for branch in target_lineage:
            merge_events = list(
                timeline.log.query(branch_id=branch, event_type="merge")
            )
            for merge_event in merge_events:
                # Check if this merge references the source branch
                for parent_id in merge_event.parents:
                    parent = timeline.log.get(parent_id)
                    if parent and parent.branch_id == source:
                        return True

        return False


class ConstraintChecker:
    """Validates events against multiple constraints.

    Example:
        checker = ConstraintChecker([
            CausalOrderConstraint(),
            NoSelfCausation(),
            BranchConsistency(),
        ])

        result = checker.check(event, timeline)
        if not result.valid:
            print(f"Violations: {result.violations}")
    """

    def __init__(self, constraints: list[Constraint] | None = None):
        """Initialize checker.

        Args:
            constraints: List of constraints to check.
                Defaults to all built-in constraints.
        """
        if constraints is None:
            constraints = [
                CausalOrderConstraint(),
                NoSelfCausation(),
                BranchConsistency(),
            ]
        self.constraints = constraints

    def check(
        self, event: TimelineEvent, timeline: Timeline
    ) -> ValidationResult:
        """Check event against all constraints.

        Args:
            event: The event to validate.
            timeline: The timeline context.

        Returns:
            Combined validation result.
        """
        all_violations: list[str] = []
        worst_action = Action.ACCEPT
        action_priority = {
            Action.ACCEPT: 0,
            Action.WARN: 1,
            Action.BRANCH: 2,
            Action.REJECT: 3,
        }

        for constraint in self.constraints:
            result = constraint.validate(event, timeline)

            if not result.valid:
                all_violations.extend(result.violations)

                if action_priority[result.suggested_action] > action_priority[worst_action]:
                    worst_action = result.suggested_action

        if all_violations:
            return ValidationResult(
                valid=False,
                violations=all_violations,
                suggested_action=worst_action,
                constraint_name="combined",
            )

        return ValidationResult.ok("combined")

    def check_all(
        self, timeline: Timeline, branch_id: str | None = None
    ) -> list[tuple[TimelineEvent, ValidationResult]]:
        """Check all events in a timeline.

        Args:
            timeline: The timeline to check.
            branch_id: Optional branch to filter by.

        Returns:
            List of (event, result) tuples for events with violations.
        """
        violations = []

        for event in timeline.log.query(branch_id=branch_id):
            result = self.check(event, timeline)
            if not result.valid:
                violations.append((event, result))

        return violations
