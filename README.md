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

### Basic Installation (Python only)

```bash
pip install -e .
```

### Full Installation (with ROS2)

TimeOS uses two environments:
1. **timeos** - Main Python environment for GUI and core functionality
2. **timeos-ros** - Conda environment with ROS2 for hardware integration

```bash
# 1. Install the Python package
pip install -e .

# 2. Create the ROS2 conda environment (requires conda/mamba)
conda create -n timeos-ros python=3.11
conda activate timeos-ros

# Install ROS2 via robostack
conda install -c conda-forge -c robostack-staging ros-humble-desktop

# 3. Build the ROS2 workspace
cd ros2_ws
colcon build
source install/setup.bash
```

A convenience script is provided:
```bash
cd ros2_ws
source setup_ros2.sh  # Activates conda env and sources workspace
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

TimeOS follows a **digital twin** architecture where the GUI is decoupled from hardware implementation. The same interface works with simulated, emulated, or real hardware — or purely through ROS2.

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
│       ├── simulated/        # Software simulation
│       ├── emulated/         # Realistic hardware emulation
│       └── real/             # HIL drivers (NI DAQ, LabVIEW)
├── gui/                       # Mission Control UI
│   ├── main.py               # Main window
│   ├── models/
│   │   ├── machine_model.py  # Direct Python model
│   │   └── ros2_machine_model.py  # ROS2-only model
│   ├── ros2/                 # ROS2 integration
│   │   ├── ros2_bridge.py    # Subprocess-based ROS2 interface
│   │   └── ros2_manager_dialog.py  # Node/topic/service management
│   ├── widgets/              # Status, position, timeline
│   └── dialogs/              # Displacement, events, annotations
├── paradoxes/                 # Educational demos
│   ├── scenarios.py          # Classic paradoxes
│   └── walkthrough.py        # Guided tutorials
└── cli/                      # Command-line interface

ros2_ws/                       # ROS2 workspace
├── timeos_msgs/              # Message/service definitions
│   ├── msg/                  # 13 message types
│   └── srv/                  # 11 service types
└── timeos_ros/               # ROS2 nodes
    ├── nodes/                # 11 nodes
    └── launch/               # Launch files
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
timeos gui              # Normal mode
timeos gui --demo       # Demo mode with simulated activity
timeos gui --emulated   # Emulated hardware with realistic behavior
timeos gui --ros2       # ROS2 mode (connects to ROS2 nodes)
```

### GUI Modes

| Mode | Description |
|------|-------------|
| Normal | Direct Python hardware abstraction |
| Demo (`--demo`) | Simulated activity for demonstrations |
| Emulated (`--emulated`) | Realistic hardware emulation with thermal modeling, timing profiles, and failure modes |
| ROS2 (`--ros2`) | Hardware-agnostic mode using ROS2 for all state and control |

**ROS2 Mode**: The GUI auto-detects the `timeos-ros` conda environment and communicates exclusively through ROS2 topics and services. This enables true digital twin operation where the GUI is decoupled from hardware implementation.

### Features
- Real-time system status with LED indicators
- Timeline visualization with branch support
- Relativistic quantities display (γ, τ, β)
- Displacement planning with energy calculations
- Event details with inspectable constraint checks
- Paradox risk assessment
- ROS2 node management dialog (Hardware → ROS2 Management)
- Hardware-in-the-loop configuration

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

TimeOS includes a complete ROS2 package with 11 nodes, 13 message types, and 11 services.

### Setup

```bash
# Activate the ROS2 conda environment
conda activate timeos-ros

# Build the workspace
cd ros2_ws
colcon build
source install/setup.bash
```

### ROS2 Nodes

| Node | Description |
|------|-------------|
| `timeline_node` | Event pub/sub and timeline management |
| `causality_monitor_node` | Real-time causality violation detection |
| `field_generator_node` | Superconducting magnet control interface |
| `tdu_node` | Temporal Displacement Unit control |
| `safety_monitor_node` | Safety interlocks and E-STOP |
| `thermal_monitor_node` | Cryogenic temperature monitoring |
| `anchor_node` | Temporal anchor point management |
| `power_monitor_node` | Power consumption tracking |
| `sensor_aggregator_node` | Sensor data fusion |
| `data_logger_node` | Event recording (CSV, HDF5) |
| `t_symmetry_node` | T-symmetry analysis experiments |

### Launch Files

```bash
# Simulation mode (all emulated)
ros2 launch timeos_ros simulation.launch.py

# Hardware mode (real devices)
ros2 launch timeos_ros hardware.launch.py

# Mixed mode (configurable)
ros2 launch timeos_ros mixed_mode.launch.py use_real_field:=true
```

### Key Topics

| Topic | Type | Rate | Description |
|-------|------|------|-------------|
| `/timeos/field_state` | FieldState | 10 Hz | Field generator status |
| `/timeos/thermal_state` | ThermalState | 10 Hz | Temperature readings |
| `/timeos/safety_state` | SafetyState | 10 Hz | Safety interlock status |
| `/timeos/tdu_state` | TDUState | 10 Hz | Displacement unit status |
| `/timeos/timeline_events` | TimelineEvent | On event | New timeline events |

### Key Services

| Service | Description |
|---------|-------------|
| `/timeos/set_field` | Set field strength (Tesla) |
| `/timeos/arm_system` | Arm/disarm safety interlocks |
| `/timeos/trigger_estop` | Emergency stop |
| `/timeos/plan_displacement` | Plan temporal displacement |
| `/timeos/create_event` | Create timeline event |

## Hardware Emulation

The emulated mode (`--emulated`) provides hardware-accurate simulation:

### Emulated Field Generator
- Realistic ramp-up/ramp-down timing (0.1 T/s typical)
- Thermal modeling with quench risk calculation
- Power supply limitations and ripple simulation
- Sensor noise and calibration drift

### Emulated TDU
- Multi-phase displacement timing profiles
- Energy consumption curves
- Position uncertainty modeling
- Communication latency simulation

### Failure Injection

Built-in failure scenarios for testing:
```bash
timeos gui --emulated
# Hardware → Failure Injection...
```

Available failures: power fluctuation, thermal spike, sensor drift, communication timeout, field collapse, and more.

## Hardware-in-the-Loop

TimeOS supports mixing real and emulated hardware:

### Supported Interfaces
- **NI DAQ**: National Instruments data acquisition
- **LabVIEW**: TCP/IP bridge for LabVIEW systems
- **Custom drivers**: Extensible driver framework

### Configuration

```bash
timeos gui --emulated
# Hardware → HIL Configuration...
```

Select which modules use real vs. emulated drivers per-component.

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
