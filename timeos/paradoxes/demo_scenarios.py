"""Demo Scenarios - Pre-built timeline configurations for educational demonstrations.

These scenarios can be loaded into the GUI to demonstrate TimeOS features
without having to set up events manually.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from timeos.msgs import ChronoStamp, TimelineEvent
from timeos.core.event_log import EventLog
from timeos.core.timeline import Timeline


class ScenarioCategory(Enum):
    """Categories of demo scenarios."""
    BASICS = "basics"
    BRANCHING = "branching"
    CAUSALITY = "causality"
    PARADOXES = "paradoxes"
    PHYSICS = "physics"


@dataclass
class ScenarioEvent:
    """Event definition for a scenario."""
    name: str  # Human-readable name
    t: float  # Time coordinate
    event_type: str = "observation"
    frame_id: str = "lab"
    branch_id: str = "main"
    parent_names: list[str] = field(default_factory=list)  # Names of parent events
    payload: str = ""
    description: str = ""


@dataclass
class Scenario:
    """A pre-built demonstration scenario."""
    name: str
    title: str
    category: ScenarioCategory
    description: str
    events: list[ScenarioEvent]
    branches: list[str] = field(default_factory=list)  # Branches to create
    learning_objectives: list[str] = field(default_factory=list)
    expected_risk: float = 0.0  # Expected paradox risk level

    def load(self, timeline: Timeline) -> dict[str, TimelineEvent]:
        """Load this scenario into a timeline.

        Returns mapping of event names to created events.
        """
        event_map: dict[str, TimelineEvent] = {}

        # Create branches first
        for branch in self.branches:
            if branch != "main":
                try:
                    timeline.branch(branch)
                except ValueError:
                    pass  # Branch may already exist

        # Create events
        for event_def in self.events:
            # Resolve parent references
            parents = []
            for parent_name in event_def.parent_names:
                if parent_name in event_map:
                    parents.append(event_map[parent_name].event_id)

            stamp = ChronoStamp(
                frame_id=event_def.frame_id,
                t=event_def.t,
                clock_class="sim",
            )

            payload = event_def.payload.encode() if event_def.payload else b""

            event = timeline.create_event(
                stamp=stamp,
                event_type=event_def.event_type,
                payload=payload,
                parents=parents,
                branch_id=event_def.branch_id,
            )

            event_map[event_def.name] = event

        return event_map


# =============================================================================
# BASIC SCENARIOS
# =============================================================================

SCENARIO_SIMPLE_TIMELINE = Scenario(
    name="simple_timeline",
    title="Simple Timeline",
    category=ScenarioCategory.BASICS,
    description="A basic sequence of events demonstrating linear causality.",
    learning_objectives=[
        "Events are ordered by time",
        "Each event can have parent events",
        "Causality flows forward in time",
    ],
    events=[
        ScenarioEvent(
            name="start",
            t=0.0,
            event_type="observation",
            description="Initial observation",
        ),
        ScenarioEvent(
            name="measurement",
            t=1.0,
            event_type="measurement",
            parent_names=["start"],
            description="First measurement",
        ),
        ScenarioEvent(
            name="analysis",
            t=2.0,
            event_type="computation",
            parent_names=["measurement"],
            description="Analyze measurements",
        ),
        ScenarioEvent(
            name="conclusion",
            t=3.0,
            event_type="decision",
            parent_names=["analysis"],
            description="Draw conclusions",
        ),
    ],
)


SCENARIO_BRANCHING = Scenario(
    name="branching",
    title="Timeline Branching",
    category=ScenarioCategory.BRANCHING,
    description="Demonstrates timeline branching for exploring alternative paths.",
    branches=["hypothesis_a", "hypothesis_b"],
    learning_objectives=[
        "Timelines can branch at any point",
        "Branches evolve independently",
        "Useful for exploring 'what if' scenarios",
    ],
    events=[
        ScenarioEvent(
            name="origin",
            t=0.0,
            event_type="observation",
            description="Common origin point",
        ),
        ScenarioEvent(
            name="decision_point",
            t=1.0,
            event_type="decision",
            parent_names=["origin"],
            description="Point where timeline branches",
        ),
        # Branch A events
        ScenarioEvent(
            name="branch_a_event",
            t=2.0,
            event_type="action",
            branch_id="hypothesis_a",
            parent_names=["decision_point"],
            description="Event in hypothesis A branch",
        ),
        ScenarioEvent(
            name="branch_a_result",
            t=3.0,
            event_type="observation",
            branch_id="hypothesis_a",
            parent_names=["branch_a_event"],
            description="Outcome of hypothesis A",
        ),
        # Branch B events
        ScenarioEvent(
            name="branch_b_event",
            t=2.0,
            event_type="action",
            branch_id="hypothesis_b",
            parent_names=["decision_point"],
            description="Event in hypothesis B branch",
        ),
        ScenarioEvent(
            name="branch_b_result",
            t=3.0,
            event_type="observation",
            branch_id="hypothesis_b",
            parent_names=["branch_b_event"],
            description="Outcome of hypothesis B",
        ),
    ],
)


# =============================================================================
# CAUSALITY SCENARIOS
# =============================================================================

SCENARIO_CAUSAL_CHAIN = Scenario(
    name="causal_chain",
    title="Causal Chain",
    category=ScenarioCategory.CAUSALITY,
    description="A clear chain of cause and effect relationships.",
    learning_objectives=[
        "Every effect must have a cause",
        "Causes must precede effects",
        "TimeOS enforces causal ordering",
    ],
    events=[
        ScenarioEvent(
            name="cause_1",
            t=0.0,
            event_type="action",
            description="Initial cause",
        ),
        ScenarioEvent(
            name="effect_1",
            t=1.0,
            event_type="observation",
            parent_names=["cause_1"],
            description="First effect (becomes cause of next)",
        ),
        ScenarioEvent(
            name="effect_2",
            t=2.0,
            event_type="observation",
            parent_names=["effect_1"],
            description="Second effect",
        ),
        ScenarioEvent(
            name="effect_3",
            t=3.0,
            event_type="observation",
            parent_names=["effect_2"],
            description="Third effect",
        ),
    ],
)


SCENARIO_MULTIPLE_CAUSES = Scenario(
    name="multiple_causes",
    title="Multiple Causes",
    category=ScenarioCategory.CAUSALITY,
    description="An event with multiple causal parents.",
    learning_objectives=[
        "Events can have multiple parents",
        "All parents must precede the child event",
        "Useful for modeling complex dependencies",
    ],
    events=[
        ScenarioEvent(
            name="cause_a",
            t=0.0,
            event_type="observation",
            description="First causal factor",
        ),
        ScenarioEvent(
            name="cause_b",
            t=0.5,
            event_type="observation",
            description="Second causal factor",
        ),
        ScenarioEvent(
            name="cause_c",
            t=1.0,
            event_type="observation",
            description="Third causal factor",
        ),
        ScenarioEvent(
            name="combined_effect",
            t=2.0,
            event_type="computation",
            parent_names=["cause_a", "cause_b", "cause_c"],
            description="Effect with three causes",
        ),
    ],
)


# =============================================================================
# RISK ESCALATION SCENARIOS
# =============================================================================

SCENARIO_LOW_RISK = Scenario(
    name="low_risk",
    title="Low Risk (< 5%)",
    category=ScenarioCategory.PARADOXES,
    description="Timeline with minimal paradox risk - all constraints satisfied.",
    expected_risk=0.02,
    learning_objectives=[
        "Well-formed timelines have low paradox risk",
        "Risk < 5% is considered nominal",
        "Green status indicates safe operation",
    ],
    events=[
        ScenarioEvent(
            name="event_1",
            t=0.0,
            event_type="observation",
        ),
        ScenarioEvent(
            name="event_2",
            t=1.0,
            parent_names=["event_1"],
            event_type="observation",
        ),
        ScenarioEvent(
            name="event_3",
            t=2.0,
            parent_names=["event_2"],
            event_type="observation",
        ),
    ],
)


SCENARIO_MEDIUM_RISK = Scenario(
    name="medium_risk",
    title="Medium Risk (5-15%)",
    category=ScenarioCategory.PARADOXES,
    description="Timeline with elevated paradox risk - triggers warning.",
    expected_risk=0.10,
    learning_objectives=[
        "Risk 5-15% triggers a warning banner",
        "Operations can proceed but require attention",
        "Yellow status indicates caution",
    ],
    events=[
        ScenarioEvent(
            name="origin",
            t=0.0,
            event_type="observation",
        ),
        ScenarioEvent(
            name="uncertain_event",
            t=1.0,
            parent_names=["origin"],
            event_type="speculation",
            payload="uncertainty_high",
            description="Event with uncertain causality",
        ),
        ScenarioEvent(
            name="dependent",
            t=2.0,
            parent_names=["uncertain_event"],
            event_type="decision",
            description="Decision based on uncertain data",
        ),
    ],
)


SCENARIO_HIGH_RISK = Scenario(
    name="high_risk",
    title="High Risk (15-30%)",
    category=ScenarioCategory.PARADOXES,
    description="Timeline with high paradox risk - forces branch creation.",
    expected_risk=0.25,
    branches=["quarantine"],
    learning_objectives=[
        "Risk 15-30% forces branch isolation",
        "Risky operations are quarantined",
        "Orange status indicates significant concern",
    ],
    events=[
        ScenarioEvent(
            name="safe_origin",
            t=0.0,
            event_type="observation",
        ),
        ScenarioEvent(
            name="risky_operation",
            t=1.0,
            parent_names=["safe_origin"],
            branch_id="quarantine",
            event_type="action",
            payload="high_risk_operation",
            description="Operation isolated to quarantine branch",
        ),
    ],
)


SCENARIO_CRITICAL_RISK = Scenario(
    name="critical_risk",
    title="Critical Risk (> 30%)",
    category=ScenarioCategory.PARADOXES,
    description="Scenario demonstrating safety interlock at critical risk.",
    expected_risk=0.50,
    learning_objectives=[
        "Risk > 30% triggers safety interlock",
        "Operation is rejected entirely",
        "Red status indicates danger",
        "E-STOP becomes meaningful at this level",
    ],
    events=[
        ScenarioEvent(
            name="safe_event",
            t=0.0,
            event_type="observation",
            description="This event is safe",
        ),
        # Note: A truly paradoxical event would be rejected,
        # so we just describe what would happen
    ],
)


# =============================================================================
# PHYSICS SCENARIOS
# =============================================================================

SCENARIO_TIME_DILATION = Scenario(
    name="time_dilation",
    title="Time Dilation",
    category=ScenarioCategory.PHYSICS,
    description="Events demonstrating time dilation between reference frames.",
    learning_objectives=[
        "Moving clocks run slower (time dilation)",
        "γ = 1/√(1 - v²/c²)",
        "Events are frame-dependent",
    ],
    events=[
        ScenarioEvent(
            name="lab_start",
            t=0.0,
            frame_id="lab",
            event_type="observation",
            description="Lab frame start",
        ),
        ScenarioEvent(
            name="ship_start",
            t=0.0,
            frame_id="ship",
            event_type="observation",
            description="Ship frame start (synchronized)",
        ),
        ScenarioEvent(
            name="lab_end",
            t=10.0,
            frame_id="lab",
            parent_names=["lab_start"],
            event_type="observation",
            description="Lab frame: 10 seconds elapsed",
        ),
        ScenarioEvent(
            name="ship_end",
            t=8.0,  # γ ≈ 1.25 at v = 0.6c
            frame_id="ship",
            parent_names=["ship_start"],
            event_type="observation",
            description="Ship frame: 8 seconds elapsed (time dilation)",
        ),
    ],
)


SCENARIO_LIGHT_CONE = Scenario(
    name="light_cone",
    title="Light Cone Causality",
    category=ScenarioCategory.PHYSICS,
    description="Events demonstrating timelike and spacelike separation.",
    learning_objectives=[
        "Timelike: causally connected (inside light cone)",
        "Spacelike: causally disconnected (outside light cone)",
        "Nothing travels faster than light",
    ],
    events=[
        ScenarioEvent(
            name="origin_event",
            t=0.0,
            event_type="emission",
            description="Origin of light cone",
        ),
        ScenarioEvent(
            name="timelike_event",
            t=2.0,
            parent_names=["origin_event"],
            event_type="observation",
            description="Inside light cone (causally connected)",
        ),
        ScenarioEvent(
            name="lightlike_event",
            t=1.0,
            event_type="observation",
            description="On light cone surface (c = distance/time)",
        ),
        ScenarioEvent(
            name="spacelike_event",
            t=0.5,
            event_type="observation",
            description="Outside light cone (causally disconnected)",
        ),
    ],
)


# =============================================================================
# SCENARIO REGISTRY
# =============================================================================

ALL_SCENARIOS: list[Scenario] = [
    # Basics
    SCENARIO_SIMPLE_TIMELINE,
    SCENARIO_BRANCHING,
    # Causality
    SCENARIO_CAUSAL_CHAIN,
    SCENARIO_MULTIPLE_CAUSES,
    # Risk escalation
    SCENARIO_LOW_RISK,
    SCENARIO_MEDIUM_RISK,
    SCENARIO_HIGH_RISK,
    SCENARIO_CRITICAL_RISK,
    # Physics
    SCENARIO_TIME_DILATION,
    SCENARIO_LIGHT_CONE,
]

SCENARIOS_BY_NAME: dict[str, Scenario] = {s.name: s for s in ALL_SCENARIOS}
SCENARIOS_BY_CATEGORY: dict[ScenarioCategory, list[Scenario]] = {}

for scenario in ALL_SCENARIOS:
    if scenario.category not in SCENARIOS_BY_CATEGORY:
        SCENARIOS_BY_CATEGORY[scenario.category] = []
    SCENARIOS_BY_CATEGORY[scenario.category].append(scenario)


def get_scenario(name: str) -> Scenario | None:
    """Get a scenario by name."""
    return SCENARIOS_BY_NAME.get(name)


def list_scenarios(category: ScenarioCategory | None = None) -> list[Scenario]:
    """List all scenarios, optionally filtered by category."""
    if category:
        return SCENARIOS_BY_CATEGORY.get(category, [])
    return ALL_SCENARIOS


def load_scenario(name: str, db_path: str = ":memory:") -> tuple[Timeline, dict[str, TimelineEvent]]:
    """Load a scenario into a new timeline.

    Args:
        name: Scenario name
        db_path: Database path (default: in-memory)

    Returns:
        Tuple of (timeline, event_map)

    Raises:
        ValueError: If scenario not found
    """
    scenario = get_scenario(name)
    if not scenario:
        raise ValueError(f"Unknown scenario: {name}")

    log = EventLog(db_path)
    timeline = Timeline(log)
    event_map = scenario.load(timeline)

    return timeline, event_map
