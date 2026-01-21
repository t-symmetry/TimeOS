# TimeOS

**TimeOS is a sandbox for exploring non-monotonic timelines, causality constraints, and speculative execution — inspired by how time travel would need to be *managed*, not how it would be *built*.**

*Useful for teaching temporal physics, synchronizing distributed systems, or controlling your actual time machine.*

---

Time Operating System — a modular framework for temporal event systems with causality constraints.

## What This Actually Is

You're not simulating physics. You're simulating the **operational consequences of uncertainty**:

- **Distributed systems** — consensus across conflicting timelines
- **Version control** — branching, merging, conflict resolution
- **Speculative execution** — run ahead, validate later
- **Fault tolerance** — graceful degradation under paradox
- **Provenance tracking** — every event has a causal history
- **Temporal precision** — uncertainty-aware timestamps with multi-clock fusion

All wearing a time-travel costume. Which is the best costume possible.

## Overview

TimeOS provides infrastructure for working with non-monotonic timelines, event provenance, and causal consistency. Think: Git for physics experiments, ROS for spacetime.

**Useful today for:**
- Multi-clock synchronization (GPS, PTP, NTP, TAI, proper time)
- Uncertainty-aware temporal data with rigorous error propagation
- Stream correlation and alignment across clock domains
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
# Launch GUI (recommended)
timeos gui

# Or use CLI for scripting
timeos init                    # Initialize timeline
timeos query --start 0 --end 10  # Query events
timeos branch list             # List branches
timeos validate                # Check consistency
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
│   ├── event_log.py          # Append-only storage (uncertainty-aware queries)
│   ├── timeline.py           # Branch management
│   ├── constraints.py        # Causality checking (inspectable)
│   └── annotations.py        # Narrative layer
├── physics/                   # Relativistic physics
│   ├── spacetime.py          # 4-vectors, Minkowski metric
│   ├── lorentz.py            # Lorentz transformations
│   ├── frames.py             # Reference frame management
│   └── causality.py          # Light cones, causal ordering
├── clocks/                    # Clock sources with uncertainty
│   ├── base.py               # ClockSource interface, ClockQuality
│   ├── system.py             # CLOCK_MONOTONIC, CLOCK_REALTIME, CLOCK_TAI
│   ├── ntp.py                # NTP/chrony integration
│   ├── ptp.py                # IEEE 1588 PTP (linuxptp)
│   ├── gps.py                # gpsd + PPS discipline
│   └── composite.py          # Multi-source Kalman filter fusion
├── uncertainty/               # Rigorous error mathematics
│   ├── models.py             # Drift models (linear, random walk)
│   ├── propagation.py        # Uncertainty through transformations
│   ├── allan.py              # Allan variance/deviation
│   └── confidence.py         # Confidence intervals
├── correlation/               # Stream alignment
│   ├── align.py              # Cross-correlation alignment
│   ├── interpolate.py        # Uncertainty-aware interpolation
│   ├── resample.py           # Time base conversion
│   └── sync.py               # Clock synchronization detection
├── formats/                   # Standard time formats
│   ├── iso8601.py            # ISO 8601 with uncertainty extensions
│   ├── smpte.py              # SMPTE 12M timecode
│   ├── prov.py               # W3C PROV-O provenance ontology
│   ├── hdf5_time.py          # HDF5 temporal metadata (CF conventions)
│   └── influx.py             # InfluxDB line protocol
├── connectors/                # External system integration
│   ├── timescale.py          # TimescaleDB hypertables
│   ├── influxdb.py           # InfluxDB 2.x client
│   ├── kafka.py              # Kafka timestamp handling
│   └── ros2_time.py          # ROS2 Time/Duration bridging
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
│   ├── widgets/              # Status, position, timeline, drift plot
│   └── dialogs/              # Displacement, correlation, annotations
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
- `clock_class`: Source type ("atomic", "gps", "ptp", "ntp", etc.)

### TimelineEvent
Universal envelope for any temporal event:
- `stamp`: When it occurred (ChronoStamp)
- `parents`: Causal dependencies (event IDs)
- `branch_id`: Timeline branch
- `payload`: Event-specific data

### Constraints (Inspectable)
Built-in causality checks with detailed inspection:
- **NoSelfCausation**: No causal loops — `Checked 5 ancestors`
- **CausalOrderConstraint**: Parents must precede children — `dt = +0.23s`
- **LightConeConstraint**: Relativistic causality — `Timelike (dt = +1.5s)`
- **BranchConsistency**: Cross-branch references require merges — `Deferred to branch`
- **ConservationConstraint**: Energy/momentum (soft) — `Deferred (no data)`

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

## Temporal Precision Toolkit

TimeOS includes comprehensive tools for working with real-world temporal data.

### Clock Sources

Multiple clock source integrations with quality tracking:

```python
from timeos.clocks import SystemClock, NTPClock, GPSClock, PTPClock, CompositeClock

# System clocks
sys_clock = SystemClock(clock_type="monotonic")  # or "realtime", "tai"

# NTP/chrony integration
ntp_clock = NTPClock()
offset, uncertainty = ntp_clock.get_offset()

# GPS with PPS discipline
gps_clock = GPSClock(gpsd_host="localhost")

# IEEE 1588 PTP
ptp_clock = PTPClock(interface="eth0")

# Multi-source fusion with automatic failover
composite = CompositeClock()
composite.add_source(gps_clock, priority=1)
composite.add_source(ptp_clock, priority=2)
composite.add_source(ntp_clock, priority=3)
stamp = composite.now()  # Best available time with uncertainty
```

### Uncertainty Mathematics

Rigorous error propagation and clock stability analysis:

```python
from timeos.uncertainty import (
    DriftModel, RandomWalkModel,
    propagate_uncertainty, combine_uncertainties,
    allan_deviation
)

# Clock drift modeling
drift = DriftModel(offset=1e-6, drift_rate=1e-9)
uncertainty_after_1h = drift.uncertainty_at(3600)

# Allan deviation for stability analysis
taus, adevs = allan_deviation(phase_data, rate=1.0)
```

### Stream Correlation

Align data streams from different clock domains:

```python
from timeos.correlation import find_offset, align_streams, resample_to_rate
from timeos.correlation.align import TimeSeries

# Find optimal time offset between streams
series1 = TimeSeries(times=times1, values=values1)
series2 = TimeSeries(times=times2, values=values2)

result = find_offset(series1, series2, max_offset=1.0)
print(f"Offset: {result.offset:.6f}s +/- {result.offset_uncertainty:.6f}s")
print(f"Correlation: {result.correlation:.4f}")

# Align and resample to common time base
_, aligned = align_streams(series1, series2, result)
resampled = resample_to_rate(aligned, target_rate=100.0)
```

### Standard Formats

Import/export in industry-standard formats:

```python
from timeos.formats import (
    parse_iso8601_uncertain, format_iso8601_uncertain,
    parse_smpte_timecode, format_smpte_timecode,
    export_prov_turtle, export_prov_jsonld,
    to_influx_line
)

# ISO 8601 with uncertainty
stamp = parse_iso8601_uncertain("2024-01-15T10:30:00.000+/-0.001Z")
formatted = format_iso8601_uncertain(stamp)  # "2024-01-15T10:30:00.000+/-0.001Z"

# SMPTE timecode (film/broadcast)
tc = parse_smpte_timecode("01:23:45:12", fps=24)

# W3C PROV-O provenance
turtle = export_prov_turtle(timeline)

# InfluxDB line protocol
line = to_influx_line(event, measurement="timeline_events")
```

### External Connectors

Integration with time-series databases and message systems:

```python
from timeos.connectors import (
    TimescaleDBConnector,
    InfluxDBConnector,
    KafkaTimestampHandler,
    ROS2TimeBridge
)

# TimescaleDB hypertables
ts = TimescaleDBConnector(connection_string)
ts.create_hypertable("events", "stamp_t")
ts.insert_event(event)

# InfluxDB with uncertainty as tags
influx = InfluxDBConnector(url, token, org, bucket)
influx.write_event(event)

# ROS2 Time bridging (without rclpy dependency)
bridge = ROS2TimeBridge()
chrono = bridge.ros2_to_chrono(ros_time, uncertainty=1e-6)
ros_time = bridge.chrono_to_ros2(chrono)
```

## GUI - Mission Control

Launch the graphical interface:
```bash
timeos gui    # Opens mode selector, then launches
```

On startup, a mode selector dialog lets you choose:

| Mode | Description |
|------|-------------|
| **Demo** | Simulated activity for demonstrations (default) |
| **Emulated** | Realistic hardware emulation with thermal modeling, timing profiles, and failure modes |
| **Normal** | Direct Python hardware abstraction |
| **ROS2** | Hardware-agnostic mode using ROS2 for all state and control |

You can also skip the selector with flags: `timeos gui --demo`, `--emulated`, `--ros2`

Switch modes anytime from **Hardware -> Mode** in the menu.

### Features
- Real-time system status with LED indicators
- Timeline visualization with uncertainty bands
- Clock status panel with quality indicators
- Drift plot for multi-source clock visualization
- Correlation dialog for interactive stream alignment
- Relativistic quantities display (gamma, tau, beta)
- Displacement planning with energy calculations
- Event details with inspectable constraint checks
- Paradox risk assessment
- ROS2 node management dialog (Hardware -> ROS2 Management)
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
# Hardware -> Failure Injection...
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
# Hardware -> HIL Configuration...
```

Select which modules use real vs. emulated drivers per-component.

## License

Copyright (c) 2024-2026 Skylark Software LLC. All Rights Reserved.

See [LICENSE](LICENSE) for details.
