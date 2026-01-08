"""Walkthrough System - Step-by-step guided exploration of scenarios.

Provides educational walkthroughs that explain concepts as users
progress through demo scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class StepType(Enum):
    """Types of walkthrough steps."""
    INTRO = "intro"           # Introduction/context
    CONCEPT = "concept"       # Physics/causality concept explanation
    ACTION = "action"         # Something happens in the timeline
    OBSERVATION = "observation"  # Point out what to notice
    QUESTION = "question"     # Rhetorical question for thought
    CONSTRAINT = "constraint" # Constraint check explanation
    RESULT = "result"         # Outcome/conclusion
    QUIZ = "quiz"            # Optional quiz question


@dataclass
class WalkthroughStep:
    """A single step in a walkthrough."""
    step_type: StepType
    title: str
    content: str  # Markdown content
    highlight_events: list[str] = field(default_factory=list)  # Event names to highlight
    code_example: str = ""  # Optional code snippet
    image_hint: str = ""    # Hint for what to visualize
    quiz_answer: str = ""   # For quiz steps


@dataclass
class Walkthrough:
    """A complete walkthrough for a scenario."""
    scenario_name: str
    title: str
    difficulty: str  # "beginner", "intermediate", "advanced"
    estimated_time: str  # e.g., "5 minutes"
    prerequisites: list[str] = field(default_factory=list)
    steps: list[WalkthroughStep] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.steps)


# =============================================================================
# WALKTHROUGH DEFINITIONS
# =============================================================================

WALKTHROUGH_SIMPLE_TIMELINE = Walkthrough(
    scenario_name="simple_timeline",
    title="Your First Timeline",
    difficulty="beginner",
    estimated_time="3 minutes",
    prerequisites=[],
    steps=[
        WalkthroughStep(
            step_type=StepType.INTRO,
            title="Welcome to TimeOS",
            content="""
# Welcome to TimeOS!

In this walkthrough, you'll learn the basics of temporal event management.

**What you'll learn:**
- How events are recorded in a timeline
- The concept of **causality** (cause and effect)
- How TimeOS tracks relationships between events

Let's start with the simplest possible timeline: a linear sequence of events.
""",
        ),
        WalkthroughStep(
            step_type=StepType.CONCEPT,
            title="Events and Time",
            content="""
# Events and Time

An **event** is something that happens at a specific point in time.

In TimeOS, every event has:
- **Time (t)**: When it occurred
- **Type**: What kind of event (observation, action, decision, etc.)
- **Parents**: What events caused this one

Think of it like Git commits - each commit has a timestamp and parent commits.
""",
        ),
        WalkthroughStep(
            step_type=StepType.ACTION,
            title="The First Event",
            content="""
# Event 1: Start

Look at the first event in the timeline:

```
t=0.0: start (observation)
```

This is our **origin event** - the beginning of the timeline.
It has no parents because nothing came before it.

In the GUI, you'll see this as the leftmost point on the timeline.
""",
            highlight_events=["start"],
        ),
        WalkthroughStep(
            step_type=StepType.ACTION,
            title="Cause and Effect",
            content="""
# Event 2: Measurement

Now look at the second event:

```
t=1.0: measurement (parents: start)
```

This event **depends on** the start event. We say "start" is the **parent**
and "measurement" is the **child**.

This is **causality**: the measurement couldn't happen without the initial
observation. Effects follow causes.
""",
            highlight_events=["measurement"],
        ),
        WalkthroughStep(
            step_type=StepType.OBSERVATION,
            title="The Causal Chain",
            content="""
# Following the Chain

Notice how each event connects to the previous one:

```
start → measurement → analysis → conclusion
  t=0      t=1          t=2        t=3
```

This is a **causal chain**. Information flows forward through time,
never backward. Each step depends on what came before.

**Key insight**: Time always moves forward. Causes precede effects.
""",
            highlight_events=["start", "measurement", "analysis", "conclusion"],
        ),
        WalkthroughStep(
            step_type=StepType.RESULT,
            title="What You've Learned",
            content="""
# Congratulations!

You've learned the fundamentals:

1. **Events** are points in time with specific types
2. **Parents** show what caused an event
3. **Causality** means effects follow causes
4. **Timelines** are chains of causally-connected events

**Next step**: Try the "Timeline Branching" scenario to learn about
exploring alternative possibilities!
""",
        ),
    ],
)


WALKTHROUGH_BRANCHING = Walkthrough(
    scenario_name="branching",
    title="Exploring Alternatives",
    difficulty="beginner",
    estimated_time="5 minutes",
    prerequisites=["simple_timeline"],
    steps=[
        WalkthroughStep(
            step_type=StepType.INTRO,
            title="What If?",
            content="""
# What If?

Science is about asking "what if?" and exploring alternatives.

In this walkthrough, you'll learn how TimeOS handles **branching timelines** -
exploring multiple possibilities from a single decision point.

Think of it like Git branches: you can try different approaches
without losing your original work.
""",
        ),
        WalkthroughStep(
            step_type=StepType.CONCEPT,
            title="The Decision Point",
            content="""
# Branching Timelines

Sometimes we reach a point where multiple paths are possible.

Instead of committing to one path, TimeOS lets you explore **both**
by creating branches. Each branch evolves independently.

This is powerful for:
- Testing hypotheses
- Exploring "what if" scenarios
- Isolating risky operations
""",
        ),
        WalkthroughStep(
            step_type=StepType.ACTION,
            title="The Fork",
            content="""
# The Fork Point

Look at the timeline structure:

```
origin → decision_point
              ├─→ [hypothesis_a] branch_a_event → branch_a_result
              └─→ [hypothesis_b] branch_b_event → branch_b_result
```

At `decision_point`, the timeline **forks** into two branches.
Each branch explores a different hypothesis.
""",
            highlight_events=["origin", "decision_point"],
        ),
        WalkthroughStep(
            step_type=StepType.OBSERVATION,
            title="Independent Evolution",
            content="""
# Branches Are Independent

Notice that both branches have events at t=2.0 and t=3.0:

**Hypothesis A:**
- branch_a_event (t=2.0)
- branch_a_result (t=3.0)

**Hypothesis B:**
- branch_b_event (t=2.0)
- branch_b_result (t=3.0)

These events exist in **parallel realities**. What happens in one
branch doesn't affect the other.
""",
            highlight_events=["branch_a_event", "branch_b_event"],
        ),
        WalkthroughStep(
            step_type=StepType.CONCEPT,
            title="Why Branch?",
            content="""
# Why Use Branches?

Branches are essential for:

1. **Hypothesis Testing**: Try different approaches, compare results
2. **Risk Isolation**: Keep dangerous experiments separate from main timeline
3. **Rollback**: If something goes wrong, the main branch is untouched
4. **Collaboration**: Different teams can work on different branches

In TimeOS, branches are also used to **quarantine paradoxes**.
""",
        ),
        WalkthroughStep(
            step_type=StepType.RESULT,
            title="Branching Mastered",
            content="""
# Well Done!

You now understand branching:

1. **Fork points** create new branches
2. Branches **evolve independently**
3. Useful for **hypothesis testing** and **risk isolation**
4. Like Git branches for spacetime!

**Next step**: Try the "Causal Chain" scenario to understand
causality constraints in more depth.
""",
        ),
    ],
)


WALKTHROUGH_GRANDFATHER = Walkthrough(
    scenario_name="grandfather_paradox",
    title="The Grandfather Paradox",
    difficulty="intermediate",
    estimated_time="7 minutes",
    prerequisites=["simple_timeline", "branching"],
    steps=[
        WalkthroughStep(
            step_type=StepType.INTRO,
            title="The Classic Paradox",
            content="""
# The Grandfather Paradox

This is the most famous time travel paradox:

> If you travel back in time and prevent your grandfather from meeting
> your grandmother, you would never be born. But if you were never born,
> you couldn't travel back to prevent them meeting...

This creates a **logical contradiction**. Let's see how TimeOS handles it.
""",
        ),
        WalkthroughStep(
            step_type=StepType.CONCEPT,
            title="Causal Loops",
            content="""
# What's Really Wrong?

The grandfather paradox is about **causal loops** - when an effect
tries to precede its own cause.

The timeline would look like:

```
prevention (t=5) ← depends on ← departure (t=31)
     ↑                              ↓
     └──────── but prevents ────────┘
```

The "prevention" event claims to be caused by "departure",
but prevention happens BEFORE departure. That's backwards!
""",
        ),
        WalkthroughStep(
            step_type=StepType.CONSTRAINT,
            title="The Causal Order Constraint",
            content="""
# How TimeOS Detects This

TimeOS has a constraint called **CausalOrderConstraint**:

> Parents must occur BEFORE their children.

When checking the paradox scenario:

```
✗ Temporal ordering: Parent occurs after child (Δt = -26.000s)
```

The constraint detects that the parent event (departure at t=31)
occurs 26 seconds AFTER its child event (prevention at t=5).

**This is impossible.** Effects cannot precede causes.
""",
        ),
        WalkthroughStep(
            step_type=StepType.OBSERVATION,
            title="Risk Assessment",
            content="""
# Paradox Risk: 95%

TimeOS calculates a **paradox risk** based on constraint violations:

- **< 5%**: Nominal (green) - proceed normally
- **5-15%**: Warning (yellow) - proceed with caution
- **15-30%**: Branch required (orange) - isolate the operation
- **> 30%**: Interlock (red) - operation rejected

The grandfather paradox scores **95% risk** - way above the 30% threshold.
This triggers the safety interlock: the operation is **rejected entirely**.
""",
        ),
        WalkthroughStep(
            step_type=StepType.QUESTION,
            title="Why So Strict?",
            content="""
# Why Reject It Completely?

You might wonder: why not just branch it?

The grandfather paradox isn't just risky - it's **logically impossible**.
Unlike bootstrap paradoxes (which are weird but consistent), this one
creates a genuine contradiction.

Allowing it would break the timeline's consistency guarantees.
TimeOS takes a conservative approach: when something is definitely wrong,
stop it completely.
""",
        ),
        WalkthroughStep(
            step_type=StepType.RESULT,
            title="Paradox Prevention",
            content="""
# What You've Learned

1. **Grandfather paradoxes** create logical contradictions
2. TimeOS detects them via the **CausalOrderConstraint**
3. Parents must always precede children in time
4. High risk (>30%) triggers the **safety interlock**
5. Some paradoxes are rejected, not just branched

**The Novikov self-consistency principle** suggests the universe might
naturally prevent such paradoxes. TimeOS enforces this computationally.

**Next**: Try the Bootstrap Paradox to see a paradox that IS allowed!
""",
        ),
    ],
)


WALKTHROUGH_BOOTSTRAP = Walkthrough(
    scenario_name="bootstrap_paradox",
    title="The Bootstrap Paradox",
    difficulty="intermediate",
    estimated_time="6 minutes",
    prerequisites=["grandfather_paradox"],
    steps=[
        WalkthroughStep(
            step_type=StepType.INTRO,
            title="Information from Nowhere",
            content="""
# The Bootstrap Paradox

Also called the "ontological paradox" or "causal loop":

> A time traveler goes back and gives Shakespeare his own plays.
> Shakespeare copies them and becomes famous.
> The plays exist... but who wrote them?

Unlike the grandfather paradox, this doesn't create a logical contradiction.
But something is still deeply wrong. Let's explore.
""",
        ),
        WalkthroughStep(
            step_type=StepType.CONCEPT,
            title="Self-Consistent Loops",
            content="""
# Why It's Different

The bootstrap paradox is **self-consistent**:

```
future_self knows poem → gives to past_self → past_self learns poem
       ↑                                              ↓
       └────────── past_self becomes ─────────────────┘
```

There's no contradiction - the loop is stable. The poem exists,
the traveler knows it, they teach it to themselves.

**But where did the information ORIGINATE?**
""",
        ),
        WalkthroughStep(
            step_type=StepType.CONSTRAINT,
            title="Conservation Concerns",
            content="""
# Information Conservation

TimeOS flags this with a soft constraint:

```
⚠ Information conservation: Information loop detected - no external origin
```

The poem exists in a closed loop with no external source.
This violates **information conservation** - the idea that information
must come from somewhere.

It's not a logical impossibility, but it's thermodynamically suspicious.
""",
        ),
        WalkthroughStep(
            step_type=StepType.OBSERVATION,
            title="Risk: 25%",
            content="""
# Moderate Risk

The bootstrap paradox scores **25% risk**:

- Below 30%, so no interlock
- Above 15%, so **branch creation is forced**

TimeOS allows the operation but isolates it:

```
Action Taken: BRANCH
```

The bootstrap loop can exist, but in its own quarantined branch.
It won't contaminate the main timeline.
""",
        ),
        WalkthroughStep(
            step_type=StepType.QUESTION,
            title="Is It Real?",
            content="""
# Could Bootstrap Paradoxes Exist?

Physicists debate this:

**Pro**: They're logically consistent. Maybe the universe allows them.
The poem has always existed in the loop - there's no "before" the loop.

**Con**: They violate thermodynamics. Information should have entropy,
should degrade. A perfect loop is suspiciously perfect.

TimeOS takes the pragmatic approach: allow but isolate.
""",
        ),
        WalkthroughStep(
            step_type=StepType.RESULT,
            title="Key Takeaways",
            content="""
# What You've Learned

1. **Bootstrap paradoxes** are self-consistent but strange
2. Information exists with **no external origin**
3. TimeOS flags this as a **soft constraint** violation
4. Risk 15-30% → forced branch isolation
5. Different from grandfather: weird but not impossible

**Real examples in fiction:**
- The watch in "Somewhere in Time"
- Beethoven's music in "Bill & Ted"
- The time turner in "Harry Potter"

**Next**: Try the risk escalation scenarios to see how thresholds work!
""",
        ),
    ],
)


WALKTHROUGH_RISK_LEVELS = Walkthrough(
    scenario_name="risk_escalation",
    title="Understanding Risk Levels",
    difficulty="beginner",
    estimated_time="5 minutes",
    prerequisites=[],
    steps=[
        WalkthroughStep(
            step_type=StepType.INTRO,
            title="The Risk System",
            content="""
# Paradox Risk Assessment

TimeOS doesn't just detect paradoxes - it quantifies them.

Every operation gets a **paradox risk score** from 0% to 100%.
Different risk levels trigger different responses.

This makes TimeOS practical: minor issues get warnings,
serious problems get blocked.
""",
        ),
        WalkthroughStep(
            step_type=StepType.CONCEPT,
            title="The Thresholds",
            content="""
# Risk Thresholds

TimeOS uses four risk levels:

| Risk Level | Color | Response |
|------------|-------|----------|
| < 5%       | Green | Nominal - proceed normally |
| 5-15%      | Yellow | Warning - proceed with caution |
| 15-30%     | Orange | Force branch - isolate the operation |
| > 30%      | Red | Interlock - reject entirely |

These thresholds are configurable, but the defaults are conservative.
""",
        ),
        WalkthroughStep(
            step_type=StepType.ACTION,
            title="Low Risk (< 5%)",
            content="""
# Green Zone: Nominal

Load the `low_risk` scenario to see a clean timeline:

All events have proper causal ordering, no loops, no violations.

```
✔ No self-parent: Checked 3 ancestors
✔ Temporal ordering: Δt = +1.000s (correct)
✔ Light-cone ordering: Timelike (Δt = +1.000s)
✔ Branch coherence: Branch 'main' consistent
```

Risk: ~2%. Everything is nominal.
""",
        ),
        WalkthroughStep(
            step_type=StepType.ACTION,
            title="Medium Risk (5-15%)",
            content="""
# Yellow Zone: Warning

The `medium_risk` scenario has uncertain causality:

```
⚠ Uncertainty: High temporal uncertainty (±0.5s)
```

Risk: ~10%. A warning banner appears but operation proceeds.

This is appropriate for:
- Preliminary data
- Speculative operations
- Known approximations
""",
        ),
        WalkthroughStep(
            step_type=StepType.ACTION,
            title="High Risk (15-30%)",
            content="""
# Orange Zone: Branch Required

The `high_risk` scenario has significant concerns:

```
⚠ Causal loop potential: Suspicious parent chain
```

Risk: ~25%. TimeOS forces branch creation.

The operation can proceed, but in an isolated branch.
If it turns out to be a real paradox, the main timeline is protected.
""",
        ),
        WalkthroughStep(
            step_type=StepType.ACTION,
            title="Critical Risk (> 30%)",
            content="""
# Red Zone: Interlock

The `critical_risk` scenario (or grandfather paradox) triggers interlock:

```
✗ Temporal ordering: VIOLATION - effect precedes cause
```

Risk: >30%. **Operation rejected.**

This is the E-STOP of causality. When something is definitely wrong,
TimeOS refuses to proceed. No branch, no warning - just stop.
""",
        ),
        WalkthroughStep(
            step_type=StepType.RESULT,
            title="Risk Management",
            content="""
# Summary

| Scenario | Risk | Response |
|----------|------|----------|
| low_risk | 2% | Proceed |
| medium_risk | 10% | Warn |
| high_risk | 25% | Branch |
| critical_risk | 50%+ | Reject |

The risk system makes TimeOS practical:
- Minor weirdness → proceed with awareness
- Moderate concerns → isolate and monitor
- Serious violations → stop immediately

**This is why E-STOP matters** - at high risk, it triggers automatically.
""",
        ),
    ],
)


# =============================================================================
# WALKTHROUGH REGISTRY
# =============================================================================

ALL_WALKTHROUGHS: list[Walkthrough] = [
    WALKTHROUGH_SIMPLE_TIMELINE,
    WALKTHROUGH_BRANCHING,
    WALKTHROUGH_GRANDFATHER,
    WALKTHROUGH_BOOTSTRAP,
    WALKTHROUGH_RISK_LEVELS,
]

WALKTHROUGHS_BY_SCENARIO: dict[str, Walkthrough] = {
    w.scenario_name: w for w in ALL_WALKTHROUGHS
}


def get_walkthrough(scenario_name: str) -> Walkthrough | None:
    """Get walkthrough for a scenario."""
    return WALKTHROUGHS_BY_SCENARIO.get(scenario_name)


def list_walkthroughs() -> list[Walkthrough]:
    """List all available walkthroughs."""
    return ALL_WALKTHROUGHS
