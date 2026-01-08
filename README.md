# TimeOS

Time Operating System — a modular framework for temporal event systems with causality constraints.

## Overview

TimeOS provides infrastructure for working with non-monotonic timelines, event provenance, and causal consistency. Think: Git for physics experiments, ROS for spacetime.

**Useful today for:**
- Multi-clock synchronization (GPS, TAI, NTP, proper time)
- Distributed systems with explicit causality
- Simulation with branching timelines
- Scientific reproducibility with provenance tracking
- Event sourcing with time-aware consistency

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
timeos/                    # Python package
├── msgs/                  # Message definitions
│   ├── chrono_stamp.py   # Timestamps with uncertainty
│   ├── temporal_frame.py # Coordinate frames
│   └── timeline_event.py # Event envelopes
├── core/
│   ├── event_log.py      # Append-only storage
│   ├── timeline.py       # Branch management
│   └── constraints.py    # Causality checking
└── cli/                  # Command-line interface

timeos_msgs/              # ROS2 message package
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

### Constraints
Built-in causality checks:
- **CausalOrderConstraint**: Parents must precede children
- **NoSelfCausation**: No causal loops
- **BranchConsistency**: Cross-branch references require merges

## ROS2 Integration

For ROS2 users, build the message package:

```bash
cd timeos_msgs
colcon build
source install/setup.bash
```

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
