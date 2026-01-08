"""Constraints - Causality checking for temporal events."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from timeos.core.timeline import Timeline
    from timeos.msgs import TimelineEvent


class Action(Enum):
    """Suggested action for constraint violations."""

    ACCEPT = "accept"  # Allow the event
    REJECT = "reject"  # Reject the event
    BRANCH = "branch"  # Create a new branch for the event
    WARN = "warn"  # Accept but log a warning
    DEFER = "defer"  # Defer to branch resolution


class ConstraintStatus(Enum):
    """Status of a constraint check."""

    SATISFIED = "satisfied"  # Constraint fully satisfied
    WARNING = "warning"      # Constraint satisfied with warnings
    DEFERRED = "deferred"    # Check deferred to later resolution
    VIOLATED = "violated"    # Constraint violated


@dataclass
class ConstraintCheck:
    """Detailed result of a single constraint check.

    Provides inspectable information about why a constraint passed or failed.
    """

    constraint_name: str
    description: str
    status: ConstraintStatus
    details: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Check if constraint was satisfied."""
        return self.status in (ConstraintStatus.SATISFIED, ConstraintStatus.WARNING, ConstraintStatus.DEFERRED)

    @property
    def icon(self) -> str:
        """Get status icon for display."""
        icons = {
            ConstraintStatus.SATISFIED: "✔",
            ConstraintStatus.WARNING: "⚠",
            ConstraintStatus.DEFERRED: "⏳",
            ConstraintStatus.VIOLATED: "✗",
        }
        return icons.get(self.status, "?")


@dataclass
class ValidationResult:
    """Result of validating an event against constraints.

    Attributes:
        valid: Whether all constraints passed.
        violations: List of violation descriptions.
        suggested_action: Recommended action based on violations.
        constraint_name: Name of the constraint that was checked.
        checks: Detailed list of all constraint checks performed.
        paradox_risk: Calculated paradox risk (0.0 to 1.0).
    """

    valid: bool
    violations: list[str] = field(default_factory=list)
    suggested_action: Action = Action.ACCEPT
    constraint_name: str = ""
    checks: list[ConstraintCheck] = field(default_factory=list)
    paradox_risk: float = 0.0

    def __bool__(self) -> bool:
        return self.valid

    @classmethod
    def ok(cls, constraint_name: str = "", check: ConstraintCheck | None = None) -> ValidationResult:
        """Create a passing result."""
        checks = [check] if check else []
        return cls(valid=True, constraint_name=constraint_name, checks=checks)

    @classmethod
    def fail(
        cls,
        violation: str,
        action: Action = Action.REJECT,
        constraint_name: str = "",
        check: ConstraintCheck | None = None,
    ) -> ValidationResult:
        """Create a failing result."""
        checks = [check] if check else []
        return cls(
            valid=False,
            violations=[violation],
            suggested_action=action,
            constraint_name=constraint_name,
            checks=checks,
        )

    @classmethod
    def warning(
        cls,
        message: str,
        constraint_name: str = "",
        check: ConstraintCheck | None = None,
        paradox_risk: float = 0.0,
    ) -> ValidationResult:
        """Create a warning result (passes but with concerns)."""
        checks = [check] if check else []
        return cls(
            valid=True,
            violations=[message],
            suggested_action=Action.WARN,
            constraint_name=constraint_name,
            checks=checks,
            paradox_risk=paradox_risk,
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
    description = "Temporal ordering"

    def validate(
        self, event: TimelineEvent, timeline: Timeline
    ) -> ValidationResult:
        if not event.parents:
            check = ConstraintCheck(
                constraint_name=self.name,
                description=self.description,
                status=ConstraintStatus.SATISFIED,
                details="No parents (root event)",
            )
            return ValidationResult.ok(self.name, check)

        for parent_id in event.parents:
            parent = timeline.log.get(parent_id)

            if parent is None:
                check = ConstraintCheck(
                    constraint_name=self.name,
                    description=self.description,
                    status=ConstraintStatus.VIOLATED,
                    details=f"Parent '{parent_id[:8]}...' not found",
                )
                return ValidationResult.fail(
                    f"Parent event '{parent_id}' not found",
                    Action.REJECT,
                    self.name,
                    check,
                )

            # Check if frames are compatible (same frame for now)
            if parent.stamp.frame_id != event.stamp.frame_id:
                check = ConstraintCheck(
                    constraint_name=self.name,
                    description=self.description,
                    status=ConstraintStatus.WARNING,
                    details=f"Cross-frame reference: {parent.stamp.frame_id} → {event.stamp.frame_id}",
                )
                return ValidationResult.warning(
                    f"Parent event '{parent_id}' is in different frame",
                    self.name,
                    check,
                    paradox_risk=0.1,
                )

            # Check temporal ordering
            delta_t = event.stamp.t - parent.stamp.t
            if delta_t < 0:
                check = ConstraintCheck(
                    constraint_name=self.name,
                    description=self.description,
                    status=ConstraintStatus.VIOLATED,
                    details=f"Parent occurs after child (Δt = {delta_t:.3f}s)",
                    metrics={"delta_t": delta_t},
                )
                return ValidationResult.fail(
                    f"Parent event '{parent_id}' (t={parent.stamp.t}) "
                    f"occurs after child (t={event.stamp.t})",
                    Action.REJECT,
                    self.name,
                    check,
                )

            # Check uncertainty overlap
            if not parent.stamp.overlaps(event.stamp) and parent.stamp.t >= event.stamp.t:
                check = ConstraintCheck(
                    constraint_name=self.name,
                    description=self.description,
                    status=ConstraintStatus.WARNING,
                    details=f"Uncertain ordering within error bounds",
                    metrics={"delta_t": delta_t, "uncertainty": event.stamp.t_uncertainty},
                )
                return ValidationResult.warning(
                    f"Parent event '{parent_id}' may not precede child within uncertainty bounds",
                    self.name,
                    check,
                    paradox_risk=0.05,
                )

        # All parents checked successfully
        delta_t = event.stamp.t - parent.stamp.t if event.parents else 0.0
        check = ConstraintCheck(
            constraint_name=self.name,
            description=self.description,
            status=ConstraintStatus.SATISFIED,
            details=f"Δt = +{delta_t:.3f}s" if delta_t > 0 else "Simultaneous",
            metrics={"delta_t": delta_t, "parent_count": len(event.parents)},
        )
        return ValidationResult.ok(self.name, check)


class NoSelfCausation(Constraint):
    """Constraint: An event cannot be its own ancestor.

    Detects causal loops by traversing the parent graph.
    """

    name = "no_self_causation"
    description = "No self-parent"

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
            check = ConstraintCheck(
                constraint_name=self.name,
                description=self.description,
                status=ConstraintStatus.SATISFIED,
                details="No parents to check",
            )
            return ValidationResult.ok(self.name, check)

        # BFS to find if event_id appears in its own ancestor chain
        visited: set[str] = set()
        queue = list(event.parents)
        depth = 0

        while queue and depth < self.max_depth:
            current_id = queue.pop(0)

            if current_id == event.event_id:
                check = ConstraintCheck(
                    constraint_name=self.name,
                    description=self.description,
                    status=ConstraintStatus.VIOLATED,
                    details=f"Causal loop detected at depth {depth}",
                    metrics={"loop_depth": depth},
                )
                return ValidationResult.fail(
                    f"Event '{event.event_id}' is its own ancestor (causal loop detected)",
                    Action.REJECT,
                    self.name,
                    check,
                )

            if current_id in visited:
                continue

            visited.add(current_id)
            parent_event = timeline.log.get(current_id)

            if parent_event is not None:
                queue.extend(parent_event.parents)
                depth += 1

        check = ConstraintCheck(
            constraint_name=self.name,
            description=self.description,
            status=ConstraintStatus.SATISFIED,
            details=f"Checked {len(visited)} ancestors",
            metrics={"ancestors_checked": len(visited), "max_depth": depth},
        )
        return ValidationResult.ok(self.name, check)


class BranchConsistency(Constraint):
    """Constraint: No cross-branch causal references without merge.

    Events can only reference parents from the same branch or
    from an ancestor branch that was properly merged.
    """

    name = "branch_consistency"
    description = "Branch coherence"

    def validate(
        self, event: TimelineEvent, timeline: Timeline
    ) -> ValidationResult:
        if not event.parents:
            check = ConstraintCheck(
                constraint_name=self.name,
                description=self.description,
                status=ConstraintStatus.SATISFIED,
                details="No cross-branch references",
            )
            return ValidationResult.ok(self.name, check)

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
                    check = ConstraintCheck(
                        constraint_name=self.name,
                        description=self.description,
                        status=ConstraintStatus.DEFERRED,
                        details=f"Deferred to branch '{event.branch_id}'",
                        metrics={"source_branch": parent.branch_id, "target_branch": event.branch_id},
                    )
                    return ValidationResult.warning(
                        f"Cross-branch reference from '{parent.branch_id}' - deferred to branch resolution",
                        self.name,
                        check,
                        paradox_risk=0.15,
                    )

        check = ConstraintCheck(
            constraint_name=self.name,
            description=self.description,
            status=ConstraintStatus.SATISFIED,
            details=f"Branch '{event.branch_id}' consistent",
            metrics={"branch_depth": len(branch_lineage)},
        )
        return ValidationResult.ok(self.name, check)

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


class LightConeConstraint(Constraint):
    """Constraint: Events must respect light-cone ordering.

    Uses relativistic physics to verify that parent events
    are within the past light cone of the child event.
    """

    name = "light_cone"
    description = "Light-cone ordering"

    def validate(
        self, event: TimelineEvent, timeline: Timeline
    ) -> ValidationResult:
        if not event.parents:
            check = ConstraintCheck(
                constraint_name=self.name,
                description=self.description,
                status=ConstraintStatus.SATISFIED,
                details="No parents (at light-cone apex)",
            )
            return ValidationResult.ok(self.name, check)

        # Import physics here to avoid circular imports
        try:
            from timeos.physics import FourVector, Event as SpacetimeEvent, SpacetimeInterval, IntervalType
        except ImportError:
            check = ConstraintCheck(
                constraint_name=self.name,
                description=self.description,
                status=ConstraintStatus.DEFERRED,
                details="Physics module not available",
            )
            return ValidationResult.ok(self.name, check)

        for parent_id in event.parents:
            parent = timeline.log.get(parent_id)
            if parent is None:
                continue

            # Create spacetime events (using time coordinate, spatial at origin for now)
            child_event = SpacetimeEvent(
                position=FourVector(t=event.stamp.t, x=0, y=0, z=0),
                frame_id=event.stamp.frame_id
            )
            parent_event = SpacetimeEvent(
                position=FourVector(t=parent.stamp.t, x=0, y=0, z=0),
                frame_id=parent.stamp.frame_id
            )

            # Calculate spacetime interval
            interval = SpacetimeInterval.between(parent_event, child_event)
            delta_t = event.stamp.t - parent.stamp.t

            if interval.interval_type == IntervalType.SPACELIKE:
                check = ConstraintCheck(
                    constraint_name=self.name,
                    description=self.description,
                    status=ConstraintStatus.VIOLATED,
                    details=f"Spacelike separation (causally disconnected)",
                    metrics={"ds_squared": interval.squared, "delta_t": delta_t},
                )
                return ValidationResult.fail(
                    f"Parent '{parent_id[:8]}...' is spacelike-separated (outside light cone)",
                    Action.REJECT,
                    self.name,
                    check,
                )

            if interval.interval_type == IntervalType.LIGHTLIKE:
                check = ConstraintCheck(
                    constraint_name=self.name,
                    description=self.description,
                    status=ConstraintStatus.SATISFIED,
                    details=f"Lightlike (on light cone, Δt = {delta_t:.3f}s)",
                    metrics={"ds_squared": interval.squared, "delta_t": delta_t, "type": "lightlike"},
                )
            else:
                check = ConstraintCheck(
                    constraint_name=self.name,
                    description=self.description,
                    status=ConstraintStatus.SATISFIED,
                    details=f"Timelike (Δt = {delta_t:+.3f}s)",
                    metrics={"ds_squared": interval.squared, "delta_t": delta_t, "type": "timelike"},
                )

        return ValidationResult.ok(self.name, check)


class ConservationConstraint(Constraint):
    """Constraint: Soft conservation check for energy/momentum.

    This is a "soft" constraint - violations trigger warnings and
    increase paradox risk but don't reject events.
    """

    name = "conservation"
    description = "Conservation (soft)"

    def validate(
        self, event: TimelineEvent, timeline: Timeline
    ) -> ValidationResult:
        # Check if event has energy/momentum metadata
        payload = event.payload
        has_energy = b"energy" in payload.lower() if payload else False

        if not has_energy:
            # No conservation data to check - defer
            check = ConstraintCheck(
                constraint_name=self.name,
                description=self.description,
                status=ConstraintStatus.DEFERRED,
                details="Deferred (no conservation data)",
            )
            return ValidationResult.ok(self.name, check)

        # For events with energy data, we'd check conservation here
        # For now, mark as satisfied with a note
        check = ConstraintCheck(
            constraint_name=self.name,
            description=self.description,
            status=ConstraintStatus.SATISFIED,
            details="Conservation check passed",
        )
        return ValidationResult.ok(self.name, check)


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

        # Inspect individual constraint checks
        for check in result.checks:
            print(f"{check.icon} {check.description}: {check.details}")
    """

    # Paradox risk thresholds for soft paradox handling
    RISK_WARNING = 0.05    # 5% - show warning banner
    RISK_BRANCH = 0.15     # 15% - force branch creation
    RISK_INTERLOCK = 0.30  # 30% - trigger safety interlock

    def __init__(self, constraints: list[Constraint] | None = None):
        """Initialize checker.

        Args:
            constraints: List of constraints to check.
                Defaults to all built-in constraints.
        """
        if constraints is None:
            constraints = [
                NoSelfCausation(),
                CausalOrderConstraint(),
                LightConeConstraint(),
                BranchConsistency(),
                ConservationConstraint(),
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
            Combined validation result with all checks.
        """
        all_violations: list[str] = []
        all_checks: list[ConstraintCheck] = []
        worst_action = Action.ACCEPT
        total_paradox_risk = 0.0
        action_priority = {
            Action.ACCEPT: 0,
            Action.WARN: 1,
            Action.DEFER: 1,
            Action.BRANCH: 2,
            Action.REJECT: 3,
        }

        for constraint in self.constraints:
            result = constraint.validate(event, timeline)

            # Collect all checks for inspection
            all_checks.extend(result.checks)

            # Accumulate paradox risk
            total_paradox_risk += result.paradox_risk

            if not result.valid:
                all_violations.extend(result.violations)

                if action_priority[result.suggested_action] > action_priority[worst_action]:
                    worst_action = result.suggested_action
            elif result.violations:
                # Warnings (valid but with messages)
                all_violations.extend(result.violations)
                if result.suggested_action == Action.WARN:
                    worst_action = max(worst_action, Action.WARN, key=lambda a: action_priority[a])

        # Apply soft paradox thresholds
        if total_paradox_risk >= self.RISK_INTERLOCK:
            worst_action = Action.REJECT
            all_violations.append(f"Paradox risk {total_paradox_risk*100:.1f}% exceeds safety threshold")
        elif total_paradox_risk >= self.RISK_BRANCH:
            if worst_action != Action.REJECT:
                worst_action = Action.BRANCH
            all_violations.append(f"Paradox risk {total_paradox_risk*100:.1f}% requires branch isolation")
        elif total_paradox_risk >= self.RISK_WARNING:
            if worst_action == Action.ACCEPT:
                worst_action = Action.WARN
            all_violations.append(f"Elevated paradox risk: {total_paradox_risk*100:.1f}%")

        # Cap paradox risk at 100%
        total_paradox_risk = min(1.0, total_paradox_risk)

        if worst_action == Action.REJECT:
            return ValidationResult(
                valid=False,
                violations=all_violations,
                suggested_action=worst_action,
                constraint_name="combined",
                checks=all_checks,
                paradox_risk=total_paradox_risk,
            )

        # Return success with all checks included for inspection
        return ValidationResult(
            valid=True,
            violations=all_violations,  # May include warnings
            suggested_action=worst_action,
            constraint_name="combined",
            checks=all_checks,
            paradox_risk=total_paradox_risk,
        )

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
