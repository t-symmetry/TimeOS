# TimeOS

**TimeOS is a sandbox for exploring non-monotonic timelines, causality constraints, and speculative execution — inspired by how time travel would need to be *managed*, not how it would be *built*.**

---

Time Operating System — a modular framework for temporal event systems with causality constraints.

## What This Actually Is

You're not simulating physics. You're simulating the **operational consequences of uncertainty**:

- **Distributed systems** — consensus across conflicting timelines
- **Version control** — branching, merging, conflict resolution
- **Speculative execution** — run ahead, validate later
- **Fault tolerance** — graceful degradation under paradox
- **Provenance tracking** — every event has a causal history

All wearing a time-travel costume. Which is the best costume possible.

## Overview

TimeOS provides infrastructure for working with non-monotonic timelines, event provenance, and causal consistency. Think: Git for physics experiments, ROS for spacetime.

**Useful today for:**
- Multi-clock synchronization (GPS, TAI, NTP, proper time)
- Distributed systems with explicit causality
- Simulation with branching timelines
- Scientific reproducibility with provenance tracking
- Event sourcing with time-aware consistency
- STEM education and interactive physics exploration

## Installation

```bash
pip install -e .
```

## Quick Start

### Python API

```python
from timeos import ChronoStamp, TimelineEvent
from timeos.core import EventLog, Timeline

# Create a timeline
log = EventLog("experiment.db")
timeline = Timeline(log)

# Create events
stamp = ChronoStamp(frame_id="lab_clock", t=0.0, t_uncertainty=0.001)
event = timeline.create_event(stamp, event_type="observation")

# Branch for alternative analysis
timeline.branch("hypothesis_1", from_event=event.event_id)
timeline.set_branch("hypothesis_1")

# Add events to the branch
stamp2 = ChronoStamp(frame_id="lab_clock", t=1.0)
event2 = timeline.create_event(stamp2, parents=[event.event_id])

# Query events
for e in timeline.slice(branch_id="hypothesis_1"):
    print(f"{e.stamp.t}: {e.event_type}")
```

### CLI

```bash
# Initialize a timeline
timeos init

# Add an event
echo '{"stamp": {"frame_id": "lab", "t": 0.0}, "event_type": "observation"}' > event.json
timeos log event.json

# Query events
timeos query --start 0 --end 10

# Manage branches
timeos branch create experiment_1
timeos branch list

# Validate consistency
timeos validate

# Export/import
timeos export backup.json
timeos import backup.json
```

## Architecture

```
timeos/                        # Python package
├── msgs/                      # Message definitions
│   ├── chrono_stamp.py       # Timestamps with uncertainty
│   ├── temporal_frame.py     # Coordinate frames
│   └── timeline_event.py     # Event envelopes
├── core/
│   ├── event_log.py          # Append-only storage
│   ├── timeline.py           # Branch management
│   ├── constraints.py        # Causality checking (inspectable)
│   └── annotations.py        # Narrative layer
├── physics/                   # Relativistic physics
│   ├── spacetime.py          # 4-vectors, Minkowski metric
│   ├── lorentz.py            # Lorentz transformations
│   ├── frames.py             # Reference frame management
│   └── causality.py          # Light cones, causal ordering
├── hardware/                  # Hardware abstraction
│   ├── base.py               # Module interfaces
│   ├── field_generator.py    # Field control
│   ├── temporal_displacement.py
│   └── drivers/
│       └── simulated/        # Software simulation
├── gui/                       # Mission Control UI
│   ├── main.py               # Main window
│   ├── widgets/              # Status, position, timeline
│   └── dialogs/              # Displacement, events, annotations
└── cli/                      # Command-line interface

timeos_msgs/                  # ROS2 message package
└── msg/
    ├── ChronoStamp.msg
    ├── TemporalFrame.msg
    ├── TimelineEvent.msg
    └── CausalityConstraint.msg
```

## Core Concepts

### ChronoStamp
A timestamp with explicit uncertainty and provenance:
- `frame_id`: Reference frame (e.g., "earth_tai", "spacecraft_proper")
- `t`: Time coordinate
- `t_uncertainty`: Error bounds
- `clock_class`: Source type ("atomic", "gps", "sim", etc.)

### TimelineEvent
Universal envelope for any temporal event:
- `stamp`: When it occurred (ChronoStamp)
- `parents`: Causal dependencies (event IDs)
- `branch_id`: Timeline branch
- `payload`: Event-specific data

### Constraints (Inspectable)
Built-in causality checks with detailed inspection:
- **NoSelfCausation**: No causal loops — `✔ Checked 5 ancestors`
- **CausalOrderConstraint**: Parents must precede children — `✔ Δt = +0.23s`
- **LightConeConstraint**: Relativistic causality — `✔ Timelike (Δt = +1.5s)`
- **BranchConsistency**: Cross-branch references require merges — `⏳ Deferred to branch`
- **ConservationConstraint**: Energy/momentum (soft) — `⏳ Deferred (no data)`

### Soft Paradoxes
Risk thresholds that make E-STOP meaningful:
- **< 5%**: Nominal — proceed
- **5-15%**: Warning banner — proceed with caution
- **15-30%**: Force branch — isolate the timeline
- **> 30%**: Safety interlock — halt operations

### Annotations
Narrative layer for documentation and storytelling:
```python
from timeos.core.annotations import Annotation, AnnotationType

note = Annotation.create(
    event_id=event.event_id,
    content="**Hypothesis**: The field fluctuation at t=3.2s suggests...",
    annotation_type=AnnotationType.HYPOTHESIS,
    tags=["field", "anomaly"]
)
```

## GUI - Mission Control

Launch the graphical interface:
```bash
timeos gui          # Normal mode
timeos gui --demo   # Demo mode with simulated activity
```

Features:
- Real-time system status with LED indicators
- Timeline visualization with branch support
- Relativistic quantities display (γ, τ, β)
- Displacement planning with energy calculations
- Event details with inspectable constraint checks
- Paradox risk assessment

## Physics Layer

Real relativistic physics for spacetime calculations:
```python
from timeos.physics import (
    FourVector, Event, SpacetimeInterval,
    lorentz_factor, LorentzBoost,
    InertialFrame, FrameRegistry,
    LightCone, CausalRelation
)

# Calculate time dilation
gamma = lorentz_factor(0.6)  # 1.25 at 60% c

# Check causality
interval = SpacetimeInterval.between(event_a, event_b)
if interval.interval_type == IntervalType.SPACELIKE:
    print("Causally disconnected!")
```

## ROS2 Integration

For ROS2 users, build the message package:

```bash
cd timeos_msgs
colcon build
source install/setup.bash
```

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
