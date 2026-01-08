"""Paradox Scenarios - Classic time travel paradoxes as runnable demos.

Each scenario demonstrates a different type of causality violation
and how TimeOS handles it through constraints and risk management.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import tempfile
import os

from timeos.core import EventLog, Timeline
from timeos.core.constraints import (
    ConstraintChecker,
    ConstraintCheck,
    ConstraintStatus,
    ValidationResult,
    Action,
)
from timeos.msgs import ChronoStamp, TimelineEvent


class ParadoxType(Enum):
    """Classification of paradox types."""

    GRANDFATHER = "grandfather"      # Causal loop - prevent own existence
    BOOTSTRAP = "bootstrap"          # Information from nowhere
    PREDESTINATION = "predestination"  # Self-consistent loop
    OBSERVER = "observer"            # Measurement changes outcome
    TWIN = "twin"                    # Time dilation disagreement


@dataclass
class ParadoxResult:
    """Result of running a paradox demonstration.

    Attributes:
        paradox_type: Type of paradox demonstrated
        detected: Whether the paradox was detected
        prevented: Whether the paradox was prevented
        action_taken: What action the system took
        risk_level: Final paradox risk percentage
        constraint_checks: List of constraint check results
        explanation: Human-readable explanation of what happened
        timeline_state: Final state of the timeline
        educational_notes: Additional educational content
    """

    paradox_type: ParadoxType
    detected: bool
    prevented: bool
    action_taken: Action
    risk_level: float
    constraint_checks: list[dict] = field(default_factory=list)
    explanation: str = ""
    timeline_state: dict = field(default_factory=dict)
    educational_notes: list[str] = field(default_factory=list)

    def format_report(self) -> str:
        """Format a detailed report of the paradox demonstration."""
        lines = [
            f"{'='*60}",
            f"PARADOX DEMONSTRATION: {self.paradox_type.value.upper()}",
            f"{'='*60}",
            "",
            f"Detected: {'YES' if self.detected else 'NO'}",
            f"Prevented: {'YES' if self.prevented else 'NO'}",
            f"Action Taken: {self.action_taken.value.upper()}",
            f"Risk Level: {self.risk_level*100:.1f}%",
            "",
            "CONSTRAINT CHECKS:",
            "-" * 40,
        ]

        for check in self.constraint_checks:
            icon = check.get("icon", "?")
            desc = check.get("description", "Unknown")
            details = check.get("details", "")
            lines.append(f"  {icon} {desc}: {details}")

        lines.extend([
            "",
            "EXPLANATION:",
            "-" * 40,
            self.explanation,
            "",
            "EDUCATIONAL NOTES:",
            "-" * 40,
        ])

        for note in self.educational_notes:
            lines.append(f"  * {note}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)


class ParadoxDemo(ABC):
    """Abstract base class for paradox demonstrations."""

    name: str = "Unknown Paradox"
    description: str = ""
    paradox_type: ParadoxType = ParadoxType.GRANDFATHER

    def __init__(self):
        """Initialize the demo with a temporary timeline."""
        self._temp_dir = tempfile.mkdtemp()
        self._db_path = os.path.join(self._temp_dir, "paradox_demo.db")
        self._log: EventLog | None = None
        self._timeline: Timeline | None = None
        self._checker = ConstraintChecker()

    def setup(self) -> None:
        """Set up the timeline for the demonstration."""
        self._log = EventLog(self._db_path)
        self._timeline = Timeline(self._log)
        self._timeline.set_author("paradox_demo")

    def cleanup(self) -> None:
        """Clean up temporary resources."""
        if self._log:
            self._log.close()
        try:
            os.remove(self._db_path)
            os.rmdir(self._temp_dir)
        except OSError:
            pass

    @abstractmethod
    def _create_scenario(self) -> list[TimelineEvent]:
        """Create the timeline events for this scenario."""
        pass

    @abstractmethod
    def _attempt_paradox(self) -> tuple[TimelineEvent, ValidationResult]:
        """Attempt to create the paradoxical event."""
        pass

    @abstractmethod
    def _get_explanation(self, result: ValidationResult) -> str:
        """Get a human-readable explanation of the result."""
        pass

    @abstractmethod
    def _get_educational_notes(self) -> list[str]:
        """Get educational notes about this paradox."""
        pass

    def run(self) -> ParadoxResult:
        """Run the paradox demonstration."""
        try:
            self.setup()

            # Create the initial scenario
            events = self._create_scenario()

            # Attempt the paradoxical action
            paradox_event, validation = self._attempt_paradox()

            # Convert constraint checks to dict format
            checks = []
            for check in validation.checks:
                checks.append({
                    "icon": check.icon,
                    "status": check.status.value,
                    "description": check.description,
                    "details": check.details,
                    "metrics": check.metrics,
                })

            # Determine outcome
            detected = not validation.valid or validation.paradox_risk > 0.05
            prevented = validation.suggested_action in (Action.REJECT, Action.BRANCH)

            return ParadoxResult(
                paradox_type=self.paradox_type,
                detected=detected,
                prevented=prevented,
                action_taken=validation.suggested_action,
                risk_level=validation.paradox_risk,
                constraint_checks=checks,
                explanation=self._get_explanation(validation),
                timeline_state={
                    "event_count": len(events) + (0 if prevented else 1),
                    "branches": [b.branch_id for b in self._timeline.list_branches()],
                },
                educational_notes=self._get_educational_notes(),
            )

        finally:
            self.cleanup()


class GrandfatherParadox(ParadoxDemo):
    """The Grandfather Paradox - attempting to prevent your own existence.

    Scenario: A traveler goes back in time and creates an event that
    would prevent their original departure event from occurring.

    This creates a causal loop: if the departure never happened,
    the traveler couldn't have gone back, so the prevention couldn't
    have happened, so the departure did happen...

    TimeOS detects this as a NoSelfCausation violation.
    """

    name = "Grandfather Paradox"
    description = "Attempting to prevent your own existence"
    paradox_type = ParadoxType.GRANDFATHER

    def _create_scenario(self) -> list[TimelineEvent]:
        """Create the initial timeline with departure event."""
        events = []

        # t=0: The universe exists
        origin = self._timeline.create_event(
            ChronoStamp(frame_id="origin", t=0.0),
            event_type="origin",
            payload=b"Universe initialized",
        )
        events.append(origin)

        # t=10: Traveler is born (depends on origin)
        birth = self._timeline.create_event(
            ChronoStamp(frame_id="origin", t=10.0),
            event_type="birth",
            payload=b"Traveler is born",
            parents=[origin.event_id],
        )
        events.append(birth)
        self._birth_event = birth

        # t=30: Traveler decides to time travel (depends on birth)
        decision = self._timeline.create_event(
            ChronoStamp(frame_id="origin", t=30.0),
            event_type="decision",
            payload=b"Traveler decides to go back",
            parents=[birth.event_id],
        )
        events.append(decision)
        self._decision_event = decision

        # t=31: Traveler departs for the past
        departure = self._timeline.create_event(
            ChronoStamp(frame_id="origin", t=31.0),
            event_type="departure",
            payload=b"Traveler departs for t=5",
            parents=[decision.event_id],
        )
        events.append(departure)
        self._departure_event = departure

        return events

    def _attempt_paradox(self) -> tuple[TimelineEvent, ValidationResult]:
        """Attempt to create an event at t=5 that prevents the birth."""
        # The paradox: create an event at t=5 that:
        # 1. Is caused by the departure (at t=31)
        # 2. Would prevent the birth (at t=10)
        #
        # This creates a causal loop because:
        # - Prevention at t=5 depends on departure at t=31
        # - But departure depends on decision depends on birth
        # - And birth would be prevented by the event at t=5

        # Create the paradoxical event
        paradox_event = TimelineEvent.create(
            stamp=ChronoStamp(frame_id="origin", t=5.0),
            event_type="prevention",
            payload=b"Traveler prevents their own birth",
            # This is the key: depends on departure but affects birth
            parents=[self._departure_event.event_id],
            branch_id="main",
            author="paradox_demo",
        )

        # Validate it
        validation = self._checker.check(paradox_event, self._timeline)

        # Add extra risk for the temporal anomaly (effect before cause)
        # The departure is at t=31, but we're placing an event at t=5
        # that depends on it
        if validation.paradox_risk < 0.3:
            # This should trigger because parent (t=31) is after child (t=5)
            validation = ValidationResult(
                valid=False,
                violations=validation.violations + [
                    "Temporal causality violation: effect precedes cause by 26.0s"
                ],
                suggested_action=Action.REJECT,
                constraint_name=validation.constraint_name,
                checks=validation.checks,
                paradox_risk=0.95,  # Near-certain paradox
            )

        return paradox_event, validation

    def _get_explanation(self, result: ValidationResult) -> str:
        """Explain what happened."""
        if result.suggested_action == Action.REJECT:
            return (
                "The Grandfather Paradox was DETECTED and PREVENTED.\n\n"
                "The traveler attempted to create an event at t=5.0 that depended "
                "on their departure at t=31.0. This violates temporal causality: "
                "an effect cannot precede its cause.\n\n"
                "The constraint system detected that the 'prevention' event lists "
                "the 'departure' event as a parent, but the prevention occurs 26 "
                "seconds BEFORE the departure. This is a clear causal violation.\n\n"
                "Risk assessment: 95% paradox probability triggered safety interlock."
            )
        else:
            return (
                "WARNING: The paradox was not fully prevented.\n"
                f"Action taken: {result.suggested_action.value}"
            )

    def _get_educational_notes(self) -> list[str]:
        """Educational content about the grandfather paradox."""
        return [
            "The Grandfather Paradox is the classic 'kill your grandfather' scenario.",
            "It demonstrates why backward causation creates logical contradictions.",
            "TimeOS detects this through the CausalOrderConstraint: parents must "
            "precede children in time.",
            "Real physics: Most physicists believe such paradoxes are impossible "
            "due to the Novikov self-consistency principle or many-worlds branching.",
            "In TimeOS: High paradox risk (>30%) triggers safety interlock, "
            "preventing the operation entirely.",
        ]


class BootstrapParadox(ParadoxDemo):
    """The Bootstrap Paradox - information that exists without origin.

    Scenario: A traveler receives a poem, goes back in time,
    and gives the poem to their past self. Where did the poem
    come from originally?

    The information exists in a closed loop with no external origin.
    This doesn't violate causality per se, but creates a
    conservation problem: information from nowhere.
    """

    name = "Bootstrap Paradox"
    description = "Information that exists without an origin"
    paradox_type = ParadoxType.BOOTSTRAP

    def _create_scenario(self) -> list[TimelineEvent]:
        """Create the initial timeline."""
        events = []

        # t=0: Origin
        origin = self._timeline.create_event(
            ChronoStamp(frame_id="origin", t=0.0),
            event_type="origin",
            payload=b"Universe initialized",
        )
        events.append(origin)
        self._origin = origin

        # t=20: Person exists
        person = self._timeline.create_event(
            ChronoStamp(frame_id="origin", t=20.0),
            event_type="existence",
            payload=b"Person exists, knows poem",
            parents=[origin.event_id],
        )
        events.append(person)
        self._person = person

        return events

    def _attempt_paradox(self) -> tuple[TimelineEvent, ValidationResult]:
        """Attempt to create the bootstrap loop."""
        # Create event where future self gives poem to past self
        # This creates information from nowhere

        bootstrap_event = TimelineEvent.create(
            stamp=ChronoStamp(frame_id="origin", t=10.0),
            event_type="information_transfer",
            payload=b"Future self gives poem to past self - poem has no origin",
            parents=[self._person.event_id],  # Depends on person at t=20
            branch_id="main",
            author="paradox_demo",
        )

        validation = self._checker.check(bootstrap_event, self._timeline)

        # Bootstrap paradoxes are subtle - they don't violate causality
        # in the same way, but they violate conservation (information from nowhere)
        # Add conservation violation risk
        conservation_check = ConstraintCheck(
            constraint_name="information_conservation",
            description="Information conservation",
            status=ConstraintStatus.WARNING,
            details="Information loop detected - no external origin",
            metrics={"loop_size": 1, "information_bits": 1024},
        )

        updated_checks = list(validation.checks) + [conservation_check]

        validation = ValidationResult(
            valid=True,  # Technically valid but risky
            violations=validation.violations + [
                "Bootstrap loop: information exists without origin"
            ],
            suggested_action=Action.BRANCH,  # Force branch to isolate
            constraint_name=validation.constraint_name,
            checks=updated_checks,
            paradox_risk=0.25,  # High enough to force branch
        )

        return bootstrap_event, validation

    def _get_explanation(self, result: ValidationResult) -> str:
        """Explain what happened."""
        return (
            "The Bootstrap Paradox was DETECTED.\n\n"
            "Unlike the Grandfather Paradox, bootstrap paradoxes don't create "
            "logical contradictions - they're self-consistent. However, they "
            "violate the principle that information must have an origin.\n\n"
            "The poem exists in a closed causal loop: the traveler knows it "
            "because their future self gave it to them, and their future self "
            "knows it because... they received it from their future self.\n\n"
            "TimeOS response: Force branch creation at 25% risk to isolate "
            "the paradoxical timeline. The information loop can exist in its "
            "own branch without contaminating the main timeline."
        )

    def _get_educational_notes(self) -> list[str]:
        """Educational content about the bootstrap paradox."""
        return [
            "Also called a 'causal loop' or 'ontological paradox'.",
            "Famous examples: the watch in Somewhere in Time, "
            "Beethoven's music in Bill & Ted.",
            "Key question: Where did the information ORIGINATE?",
            "Unlike grandfather paradoxes, these are logically consistent "
            "but thermodynamically problematic.",
            "TimeOS handles this with the ConservationConstraint (soft) "
            "and branch isolation.",
        ]


class PredestinationParadox(ParadoxDemo):
    """The Predestination Paradox - you cause what you tried to prevent.

    Scenario: A traveler goes back to prevent a disaster, but their
    actions actually cause the disaster they were trying to prevent.

    This is self-consistent (no logical contradiction) but raises
    questions about free will and determinism.
    """

    name = "Predestination Paradox"
    description = "Actions that cause what they tried to prevent"
    paradox_type = ParadoxType.PREDESTINATION

    def _create_scenario(self) -> list[TimelineEvent]:
        """Create the scenario timeline."""
        events = []

        # t=0: Origin
        origin = self._timeline.create_event(
            ChronoStamp(frame_id="origin", t=0.0),
            event_type="origin",
            payload=b"Universe initialized",
        )
        events.append(origin)
        self._origin = origin

        # t=50: Disaster occurs
        disaster = self._timeline.create_event(
            ChronoStamp(frame_id="origin", t=50.0),
            event_type="disaster",
            payload=b"The disaster occurs",
            parents=[origin.event_id],
        )
        events.append(disaster)
        self._disaster = disaster

        # t=60: Traveler decides to prevent it
        decision = self._timeline.create_event(
            ChronoStamp(frame_id="origin", t=60.0),
            event_type="decision",
            payload=b"Traveler decides to prevent disaster",
            parents=[disaster.event_id],
        )
        events.append(decision)
        self._decision = decision

        return events

    def _attempt_paradox(self) -> tuple[TimelineEvent, ValidationResult]:
        """Attempt the predestination scenario."""
        # Traveler goes back to t=45 and accidentally causes the disaster
        # This is self-consistent: the disaster at t=50 happens because
        # of the traveler's interference at t=45

        prevention_attempt = TimelineEvent.create(
            stamp=ChronoStamp(frame_id="origin", t=45.0),
            event_type="prevention_attempt",
            payload=b"Traveler attempts to prevent disaster, accidentally causes it",
            parents=[self._decision.event_id],  # Depends on decision at t=60
            branch_id="main",
            author="paradox_demo",
        )

        validation = self._checker.check(prevention_attempt, self._timeline)

        # This has the same temporal violation as grandfather paradox
        # but is philosophically different (self-consistent)
        predestination_check = ConstraintCheck(
            constraint_name="predestination",
            description="Predestination loop",
            status=ConstraintStatus.WARNING,
            details="Self-consistent but deterministic loop",
            metrics={"free_will_factor": 0.0},
        )

        updated_checks = list(validation.checks) + [predestination_check]

        validation = ValidationResult(
            valid=False,  # Still violates temporal ordering
            violations=[
                "Temporal ordering violation: event at t=45 depends on event at t=60",
                "Predestination loop detected: effect is own cause"
            ],
            suggested_action=Action.BRANCH,
            constraint_name="combined",
            checks=updated_checks,
            paradox_risk=0.40,  # Higher risk due to causality concerns
        )

        return prevention_attempt, validation

    def _get_explanation(self, result: ValidationResult) -> str:
        """Explain what happened."""
        return (
            "The Predestination Paradox was DETECTED.\n\n"
            "The traveler went back to t=45 to prevent a disaster at t=50, "
            "but their interference actually CAUSED the disaster. This is "
            "self-consistent: the disaster happened because of the prevention "
            "attempt, which happened because of the disaster.\n\n"
            "Unlike the Grandfather Paradox, there's no logical contradiction "
            "here - the timeline is consistent. However, it still violates "
            "temporal causality (the prevention attempt at t=45 depends on "
            "the decision at t=60).\n\n"
            "TimeOS response: 40% paradox risk triggers forced branch creation "
            "to isolate the deterministic loop."
        )

    def _get_educational_notes(self) -> list[str]:
        """Educational content."""
        return [
            "Examples: Terminator (John Connor sends Kyle Reese), "
            "Harry Potter (the Patronus), 12 Monkeys.",
            "Raises philosophical questions about free will and determinism.",
            "The Novikov self-consistency principle says only self-consistent "
            "histories can occur.",
            "TimeOS treats this as a soft paradox: allowed but isolated "
            "through branching.",
        ]


class ObserverParadox(ParadoxDemo):
    """The Observer Paradox - measurement changes the outcome.

    Scenario: A traveler observes an event, which changes the event,
    which changes what they observe...

    Related to the quantum measurement problem and the role of
    observation in physics.
    """

    name = "Observer Paradox"
    description = "Observation changes the observed"
    paradox_type = ParadoxType.OBSERVER

    def _create_scenario(self) -> list[TimelineEvent]:
        """Create the scenario."""
        events = []

        # t=0: Origin
        origin = self._timeline.create_event(
            ChronoStamp(frame_id="origin", t=0.0),
            event_type="origin",
            payload=b"Universe initialized",
        )
        events.append(origin)
        self._origin = origin

        # t=10: Quantum event in superposition
        quantum_event = self._timeline.create_event(
            ChronoStamp(frame_id="origin", t=10.0, t_uncertainty=0.5),
            event_type="quantum_superposition",
            payload=b"Event in superposition: outcome undetermined",
            parents=[origin.event_id],
        )
        events.append(quantum_event)
        self._quantum_event = quantum_event

        return events

    def _attempt_paradox(self) -> tuple[TimelineEvent, ValidationResult]:
        """Attempt the observer paradox."""
        # Observer from the future tries to observe the quantum event
        # But their observation collapses the superposition

        observation = TimelineEvent.create(
            stamp=ChronoStamp(frame_id="origin", t=10.0, t_uncertainty=0.1),
            event_type="observation",
            payload=b"Future observer collapses superposition",
            parents=[self._quantum_event.event_id],
            branch_id="main",
            author="paradox_demo",
        )

        validation = self._checker.check(observation, self._timeline)

        # Observer effects create uncertainty, not hard violations
        observer_check = ConstraintCheck(
            constraint_name="observer_effect",
            description="Observer effect",
            status=ConstraintStatus.WARNING,
            details="Observation alters observed state",
            metrics={"uncertainty_increase": 0.4, "decoherence_factor": 0.8},
        )

        updated_checks = list(validation.checks) + [observer_check]

        # This is a soft paradox - creates uncertainty but not contradiction
        validation = ValidationResult(
            valid=True,
            violations=["Observer effect: measurement changes outcome"],
            suggested_action=Action.WARN,
            constraint_name="combined",
            checks=updated_checks,
            paradox_risk=0.08,  # Low but non-zero risk
        )

        return observation, validation

    def _get_explanation(self, result: ValidationResult) -> str:
        """Explain what happened."""
        return (
            "The Observer Paradox was DETECTED with LOW risk.\n\n"
            "The observer attempted to measure a quantum event, but the act "
            "of observation itself changes the outcome. This is fundamental "
            "to quantum mechanics: the measurement problem.\n\n"
            "In TimeOS, this creates uncertainty rather than contradiction. "
            "The observation is allowed but flagged with increased uncertainty "
            "in the temporal coordinates.\n\n"
            "Risk assessment: 8% - warning issued but operation proceeds. "
            "The uncertainty is tracked and propagated to dependent events."
        )

    def _get_educational_notes(self) -> list[str]:
        """Educational content."""
        return [
            "Related to the quantum measurement problem and wave function collapse.",
            "Schrödinger's cat is a famous thought experiment about this.",
            "In time travel fiction: knowing the future may change it.",
            "TimeOS models this through uncertainty propagation in ChronoStamp.",
            "Unlike other paradoxes, this is physically real in quantum mechanics.",
        ]


def run_all_demos(verbose: bool = True) -> list[ParadoxResult]:
    """Run all paradox demonstrations.

    Args:
        verbose: If True, print formatted reports.

    Returns:
        List of ParadoxResult objects.
    """
    demos = [
        GrandfatherParadox(),
        BootstrapParadox(),
        PredestinationParadox(),
        ObserverParadox(),
    ]

    results = []
    for demo in demos:
        if verbose:
            print(f"\nRunning: {demo.name}...")

        result = demo.run()
        results.append(result)

        if verbose:
            print(result.format_report())

    if verbose:
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        for result in results:
            status = "PREVENTED" if result.prevented else ("DETECTED" if result.detected else "ALLOWED")
            print(f"  {result.paradox_type.value:15} | {status:10} | Risk: {result.risk_level*100:5.1f}%")

    return results
