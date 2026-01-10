# TimeOS Hardware Bill of Materials

> Roughly 80% of TimeOS could be implemented today using existing industrial, laboratory, and robotics hardware. The remaining 20% is intentionally abstracted to allow experimentation without requiring speculative physics.

## Design Philosophy

TimeOS is not building time travel hardware. It is building an **instrumented control system for non-monotonic state**.

A module is considered "real" if:
- It has a physical signal
- It has measurable limits
- It can fail
- It interacts with safety logic

Under this definition, most of the TimeOS UI maps cleanly to existing hardware.

---

## Hardware Tier Definitions

| Tier | Symbol | Meaning |
|------|--------|---------|
| **REAL** | `[R]` | Direct hardware implementation with real physics |
| **PROXY** | `[P]` | Real hardware acting as stand-in for abstract concept |
| **INFRASTRUCTURE** | `[I]` | Supporting systems (compute, network, power) |
| **ABSTRACT** | `[A]` | Pure software, no hardware equivalent needed |

---

## Subsystem Buildability Summary

| Subsystem | Buildable Today | Notes |
|-----------|-----------------|-------|
| GUI / Control Software | 100% | Qt, ROS2, Python |
| Timeline / Branch Engine | 100% | Pure software |
| Causality / Risk Analysis | 100% | Graphs, constraints, policies |
| Safety / Interlocks | 95-100% | Industrial safety hardware |
| Field Module (proxy) | 80-90% | EM / power / ramp systems |
| Anchor / Reference | 95% | GPS / clocks / oscillators |
| Thermal Management | 100% | Sensors + cooling control |
| Power / Energy Budget | 100% | Meters + UPS + PSUs |
| TDU (actuation proxy) | 70-80% | Sequencer + motion control |
| Actual spacetime manipulation | 0% | Explicitly not our goal |

**Weighted Overall: ~75-85% buildable today**

---

## Bill of Materials

### 1. Core Compute & Control `[I]`

#### Control Computer
Runs ROS2, TimeOS core, and GUI.

| Spec | Requirement |
|------|-------------|
| CPU | x86_64, 8-16 cores |
| RAM | 32-64 GB |
| Network | Dual NICs |
| OS | Ubuntu 22.04/24.04 LTS |

**Examples:**
- Industrial PC (Advantech, Beckhoff)
- Workstation (Dell Precision, HP Z-series)

**Cost:** $1,200 - $3,000

**Role:** Temporal Control Computer

---

#### Network Backbone
| Component | Specification |
|-----------|---------------|
| Switch | Managed Gigabit or 10GbE |
| Features | VLAN support, QoS |

**Cost:** $150 - $600

---

### 2. Anchor Module `[R]`

The Anchor module maps to precision timing and reference systems.

#### GPS-Disciplined Oscillator (GPSDO)

| Feature | Output |
|---------|--------|
| Time Reference | PPS (1Hz pulse) |
| Data | NMEA sentences |
| Frequency | 10 MHz reference |

**Examples:**
- Trimble Thunderbolt E
- Jackson Labs Fury GPSDO
- Leo Bodnar Mini GPS Reference Clock

**Cost:** $300 - $1,500

**Role:** Anchor lock, drift measurement, jitter analysis, reference time

**Buildability:** ~95%

#### Optional: Precision Clock Upgrade

| Type | Stability |
|------|-----------|
| OCXO | 10^-9 |
| Rubidium | 10^-11 |

**Cost:** $400 - $2,000

---

### 3. Field Module `[P]`

The Field module maps to electromagnetic control systems.

#### Programmable DC Power Supply (SCPI-controlled)

| Feature | Capability |
|---------|------------|
| Control | SCPI over USB/Ethernet |
| Ramping | Programmable slew rate |
| Telemetry | V, I, P readback |

**Examples:**
- TDK Lambda Zup/Genesys series
- Keysight E36xx/N57xx series
- Delta Elektronika SM series
- Rohde & Schwarz HMP series

**Cost:** $800 - $3,000

**Role:** Field ramp-up/down, power draw monitoring

#### Electromagnet / Coil Assembly

| Type | Use Case |
|------|----------|
| Helmholtz Coils | Uniform field region |
| Large Inductor | Energy storage demo |
| Lab Electromagnet | Variable field strength |

**Cost:** $300 - $1,500

**Role:** Physical B-field generation (proxy for "temporal field")

#### Hall-Effect Magnetic Sensor

| Type | Range |
|------|-------|
| Hall Effect | mT to T range |
| Gaussmeter probe | Precision measurement |

**Examples:**
- Honeywell SS49E
- Allegro A1302
- Lake Shore 475 DSP Gaussmeter (high-end)

**Cost:** $30 - $150 (sensor) / $2,000+ (precision gaussmeter)

**Role:** Real B-field feedback to control loop

---

### 4. Thermal Module `[R]`

#### Temperature Sensors

| Type | Range | Accuracy |
|------|-------|----------|
| RTD (PT100/PT1000) | -200 to +850°C | ±0.1°C |
| Thermocouple (K-type) | -200 to +1350°C | ±1°C |
| Thermistor | -40 to +125°C | ±0.1°C |

**Interface:** MAX31865 (RTD), MAX31855 (thermocouple)

**Cost:** $50 - $200

**Role:** Coil temperature, ambient monitoring, cryostat simulation

#### Cooling System

| Type | Capacity |
|------|----------|
| Industrial fans | 100-500 CFM |
| Liquid cooling loop | 500W-2kW |
| Recirculating chiller | 1kW-10kW |

**Cost:** $100 - $800 (fans/liquid) / $2,000+ (chiller)

---

### 5. Power & Energy Budget `[R]`

#### Power Meter / Analyzer

| Feature | Capability |
|---------|------------|
| Measurement | V, I, P, E, PF |
| Interface | Modbus, REST API, MQTT |

**Examples:**
- IoTaWatt (DIY-friendly)
- OpenEnergyMonitor
- Schneider PowerLogic
- Dent ELITEpro

**Cost:** $150 - $600

**Role:** Real-time power draw, integrated energy, budget tracking

#### UPS with Telemetry

| Feature | Capability |
|---------|------------|
| Capacity | 1-3 kVA |
| Interface | SNMP, USB, network card |
| Telemetry | Load %, battery %, runtime |

**Examples:**
- APC Smart-UPS
- CyberPower PR series
- Eaton 5P/5PX

**Cost:** $400 - $1,200

**Role:** Brownout protection, power quality monitoring

---

### 6. TDU (Temporal Displacement Unit) `[P]`

The TDU is a sequencer/state machine, not a physics device.

#### Industrial Controller or PLC

| Feature | Capability |
|---------|------------|
| I/O | Digital + Analog |
| Protocols | EtherCAT, Modbus, PROFINET |
| Programming | IEC 61131-3, ladder, structured text |

**Examples:**
- Beckhoff CX-series (EtherCAT)
- Siemens LOGO! / S7-1200
- WAGO PFC200
- Allen-Bradley Micro800

**Cost:** $300 - $1,500

**Role:** Displacement sequencing, interlocks, execution state machine

#### Optional: Motion System (Visual Feedback)

| Component | Purpose |
|-----------|---------|
| Linear actuator | "Something moves" |
| Stepper/servo | Precise positioning |
| LED indicators | Status visualization |

**Cost:** $200 - $800

**Role:** Physical indication that "displacement is occurring"

---

### 7. Safety Module `[R]`

**This is the most realistic part of the system.**

#### E-STOP Button (Hardwired)

| Type | Features |
|------|----------|
| Mushroom head | Red, twist-release |
| Contacts | NC (normally closed) |
| Mounting | Panel or enclosure |

**Cost:** $25 - $75

#### Safety Relay / Safety PLC

| Feature | Capability |
|---------|------------|
| Channels | Dual-channel redundant |
| Certification | SIL 2/3, PLd/e |
| Monitoring | Cross-fault detection |

**Examples:**
- Pilz PNOZ
- Sick Flexi Soft
- Allen-Bradley Guardmaster
- Siemens 3SK1

**Cost:** $150 - $600

**Role:** Interlocks, fault latching, safe state enforcement

#### Keyed Arm/Disarm Switch

| Type | Purpose |
|------|---------|
| Key switch | Arm/disarm system |
| Selector | Mode selection |

**Cost:** $40 - $100

---

### 8. DAQ / I/O Backbone `[R]`

#### Data Acquisition Module

| Type | Interface |
|------|-----------|
| NI USB DAQ | USB, high sample rate |
| EtherCAT terminals | Distributed I/O |
| CAN interface | Industrial sensors |
| GPIO expander | Simple digital I/O |

**Examples:**
- NI USB-6001/6009
- Beckhoff EL-series terminals
- PEAK CAN interface
- LabJack U3/T7

**Cost:** $200 - $1,500

**Role:** Sensor aggregation, signal conditioning, analog I/O

---

### 9. Rack & Physical Presentation `[I]`

#### 19" Rack Enclosure

| Size | Use Case |
|------|----------|
| 12U | Desktop/bench |
| 24U | Floor-standing |
| 42U | Full-height |

**Cost:** $300 - $1,000

#### Accessories

- Blank panels with custom labels
- LED panel meters
- Rack-mount power strips
- Cable management

**Cost:** $100 - $500

---

## Cost Summary

### Lab / Demo Build
**$3,000 - $6,000**

- Quiet, desk-safe, credible
- Basic sensors and control
- Single power supply + coil
- Raspberry Pi or mini-PC

### Rack-Mounted "Serious" Build
**$7,000 - $15,000**

- Looks exactly like the UI implies
- Industrial controller (PLC)
- Real safety systems
- Multiple sensor channels
- Proper rack presentation

### Maximalist / Museum-Grade
**$20,000+**

- Precision timing (Rubidium clock)
- High-end power supplies
- Motion systems
- Chiller/cryogenic simulation
- Full safety certification

---

## Module-to-Hardware Mapping

| TimeOS Module | Hardware Category | Tier | Primary Components |
|---------------|-------------------|------|-------------------|
| `FieldGenerator` | Electromagnetics | `[P]` | Power supply, coil, Hall sensor |
| `TemporalDisplacementUnit` | Sequencer | `[P]` | PLC, motion controller |
| `CausalityMonitor` | Software | `[A]` | (pure computation) |
| `Anchor` | Timing | `[R]` | GPSDO, OCXO |
| `SafetyInterlocks` | Safety | `[R]` | E-stop, safety relay, PLC |
| `ThermalSystem` | Thermal | `[R]` | RTDs, cooling, PID |
| `PowerManager` | Power | `[R]` | Meters, UPS, PDU |
| `DataLogger` | DAQ | `[R]` | NI DAQ, EtherCAT I/O |

---

## What's NOT Buildable (And That's Okay)

Only one thing is truly non-existent:

> **A device that physically violates causal ordering in spacetime.**

TimeOS explicitly avoids claiming this capability. Everything else is:
- Instrumentation
- Coordination
- Control
- Safety
- Simulation

This is why TimeOS is **defensible**.

---

## Vendor Quick Reference

| Category | Vendors |
|----------|---------|
| Power Supplies | TDK Lambda, Keysight, Delta, R&S |
| PLCs | Beckhoff, Siemens, Allen-Bradley, WAGO |
| Safety | Pilz, Sick, Allen-Bradley, Siemens |
| DAQ | National Instruments, Beckhoff, LabJack |
| Timing | Trimble, Jackson Labs, Stanford Research |
| Sensors | Honeywell, Allegro, Lake Shore |

---

## Appendix: Example Configurations

### Minimal Demo (Budget: ~$500)

- Raspberry Pi 4 (8GB)
- Arduino + relay shield
- USB power meter
- LED indicators
- E-stop button
- 3D-printed enclosure

### Bench Setup (Budget: ~$3,000)

- Intel NUC or mini-PC
- NI USB-6001 DAQ
- TDK Lambda Z+ power supply
- RTD temperature sensors
- GPS module (u-blox)
- Industrial E-stop
- Pelican case enclosure

### Rack System (Budget: ~$10,000)

- Industrial PC (Advantech)
- Beckhoff CX8190 + EL terminals
- Delta SM power supply (2kW)
- Helmholtz coil pair
- Lake Shore gaussmeter
- Jackson Labs Fury GPSDO
- Pilz PNOZ safety relay
- 12U rack with custom panels
