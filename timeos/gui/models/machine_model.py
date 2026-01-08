"""Qt Model wrapping the SimulatedTimeMachine or EmulatedTimeMachine."""

from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Any, Union

from PySide6.QtCore import QObject, Signal, QTimer

from timeos.hardware.drivers.simulated import SimulatedTimeMachine
from timeos.hardware.timeline_navigator import NavigationTarget
from timeos.hardware.base import ModuleStatus
from timeos.msgs import ChronoStamp, TemporalFrame
from timeos.physics import lorentz_factor

# Import emulated components (optional - may not be used)
try:
    from timeos.hardware.drivers.emulated import (
        EmulatedTimeMachine,
        MachineState,
        MachineConfig,
        SystemStatus,
    )
    EMULATED_AVAILABLE = True
except ImportError:
    EMULATED_AVAILABLE = False
    EmulatedTimeMachine = None
    MachineState = None
    MachineConfig = None


class MachineModel(QObject):
    """Qt model wrapping SimulatedTimeMachine or EmulatedTimeMachine for GUI integration.

    Provides signals for state changes and exposes machine functionality
    in a GUI-friendly way.

    Args:
        demo: Enable demo mode with simulated activity
        emulated: Use EmulatedTimeMachine with realistic hardware behavior
        parent: Parent QObject
    """

    # Signals
    state_changed = Signal()
    event_logged = Signal(dict)
    module_status_changed = Signal(str, str)  # module_name, status
    displacement_started = Signal()
    displacement_completed = Signal(bool)  # success
    error_occurred = Signal(str)

    def __init__(
        self,
        demo: bool = False,
        emulated: bool = False,
        parent: QObject | None = None,
    ):
        super().__init__(parent)

        self._machine: Union[SimulatedTimeMachine, "EmulatedTimeMachine", None] = None
        self._emulated_machine: "EmulatedTimeMachine | None" = None
        self._event_log: list[dict] = []
        self._initialized = False
        self._demo = demo
        self._emulated = emulated and EMULATED_AVAILABLE
        self._demo_timer: QTimer | None = None
        self._demo_time = 0.0

        # Update timer for emulated mode
        self._update_timer: QTimer | None = None

        # Relativistic state tracking
        self._velocity_beta = 0.0  # v/c (fraction of light speed)
        self._proper_time = 0.0    # τ (proper time accumulated)

    def initialize(self) -> bool:
        """Initialize the time machine.

        Returns:
            True if initialization succeeded.
        """
        try:
            if self._emulated and EMULATED_AVAILABLE:
                return self._initialize_emulated()
            else:
                return self._initialize_simulated()

        except Exception as e:
            self.error_occurred.emit(str(e))
            return False

    def _initialize_simulated(self) -> bool:
        """Initialize with SimulatedTimeMachine."""
        self._machine = SimulatedTimeMachine()
        success = self._machine.initialize()

        if success:
            self._initialized = True
            self._log_event("System initialized (simulated mode)")

            # Set initial anchor
            self._machine.set_anchor()
            self._log_event("Anchor point established")

            # Start demo mode if enabled
            if self._demo:
                self._start_demo()

        self.state_changed.emit()
        return success

    def _initialize_emulated(self) -> bool:
        """Initialize with EmulatedTimeMachine."""
        config = MachineConfig(
            max_field_tesla=10.0,
            field_ramp_rate_tesla_per_second=0.1,
            max_displacement_years=100.0,
            operating_temp_kelvin=4.2,
            quench_temp_kelvin=9.2,
            cooling_power_watts=50.0,
            status_publish_rate_hz=10.0,
        )

        self._emulated_machine = EmulatedTimeMachine(config)
        success = self._emulated_machine.initialize()

        if success:
            self._initialized = True
            self._log_event("System initialized (emulated hardware mode)")

            # Start background update loop
            self._emulated_machine.start()

            # Add state change callback
            self._emulated_machine.add_state_callback(self._on_emulated_state_change)
            self._emulated_machine.add_status_callback(self._on_emulated_status)

            # Start Qt update timer for GUI refresh
            self._update_timer = QTimer(self)
            self._update_timer.timeout.connect(self._emulated_update_tick)
            self._update_timer.start(100)  # 10 Hz GUI update

            self._log_event("Emulated hardware online")

            # Start demo mode if enabled
            if self._demo:
                self._start_emulated_demo()

        self.state_changed.emit()
        return success

    def _on_emulated_state_change(self, state: "MachineState") -> None:
        """Handle state change from emulated machine."""
        self._log_event(f"State: {state.value}")
        # Emit from main thread via queued connection
        QTimer.singleShot(0, self.state_changed.emit)

    def _on_emulated_status(self, status: "SystemStatus") -> None:
        """Handle status update from emulated machine."""
        # This is called frequently, we don't log every update
        pass

    def _emulated_update_tick(self) -> None:
        """Periodic update for emulated mode GUI refresh."""
        if self._emulated_machine:
            self.state_changed.emit()

    def _start_emulated_demo(self) -> None:
        """Start demo mode for emulated machine."""
        self._log_event("Demo mode activated (emulated)")
        self._demo_time = 0.0
        self._demo_tick_count = 0

        # Ramp up the field to show hardware behavior
        if self._emulated_machine:
            self._emulated_machine.set_field(5.0)
            self._log_event("Field ramp initiated: target 5.0 T")

        # Start demo timer for periodic activity
        self._demo_timer = QTimer(self)
        self._demo_timer.timeout.connect(self._emulated_demo_tick)
        self._demo_timer.start(3000)  # Every 3 seconds

    def _emulated_demo_tick(self) -> None:
        """Demo mode periodic update for emulated machine."""
        self._demo_tick_count += 1
        self._demo_time += 3.0

        if not self._emulated_machine:
            return

        # Get current status
        status = self._emulated_machine.get_status()

        # Simulate relativistic motion
        self._velocity_beta = 0.4 + 0.4 * math.sin(self._demo_tick_count * 0.3)
        if self._velocity_beta < 1.0:
            gamma = lorentz_factor(self._velocity_beta)
            self._proper_time += 3.0 / gamma

        # Log some status updates
        if self._demo_tick_count % 3 == 0:
            field_tesla = status["field"]["field_tesla"]
            temp = status["thermal"]["temperature_kelvin"]
            self._log_event(
                f"Status: B={field_tesla:.2f}T, T={temp:.2f}K"
            )

        self.state_changed.emit()

    def _start_demo(self) -> None:
        """Start demo mode simulation."""
        self._log_event("Demo mode activated")
        self._demo_time = 0.0
        self._demo_tick_count = 0
        self._demo_branches_created = False

        # Generate some initial demo events
        demo_events = [
            "Calibration sequence initiated",
            "Temporal field stabilized",
            "Causality monitor online",
            "Ready for operations",
        ]
        for msg in demo_events:
            self._log_event(msg)

        # Create initial timeline events
        if self._machine:
            timeline = self._machine.timeline
            timeline.set_author("demo")
            for i, msg in enumerate(demo_events):
                stamp = ChronoStamp(frame_id="origin", t=float(i) * 0.5)
                timeline.create_event(stamp, event_type="system", payload=msg.encode())

        # Start demo timer for periodic updates
        self._demo_timer = QTimer(self)
        self._demo_timer.timeout.connect(self._demo_tick)
        self._demo_timer.start(2000)  # Update every 2 seconds

    def _demo_tick(self) -> None:
        """Demo mode periodic update."""
        dt_coord = 1.0  # Coordinate time step (seconds)
        self._demo_time += dt_coord
        self._demo_tick_count += 1

        # Simulate relativistic motion - velocity varies over time
        # Oscillate between 0 and 0.8c to show time dilation effects
        self._velocity_beta = 0.4 + 0.4 * math.sin(self._demo_tick_count * 0.3)

        # Calculate proper time: dτ = dt / γ
        if self._velocity_beta < 1.0:
            gamma = lorentz_factor(self._velocity_beta)
            dt_proper = dt_coord / gamma
            self._proper_time += dt_proper

        # Create demo branches after a few ticks to show branch visualization
        if not self._demo_branches_created and self._demo_tick_count >= 3 and self._machine:
            self._create_demo_branches()
            self._demo_branches_created = True

        # Randomly generate events
        if random.random() < 0.4:
            demo_messages = [
                ("Temporal flux detected", "observation"),
                ("Field strength nominal", "status"),
                ("Causality check passed", "verification"),
                ("Timeline stable", "status"),
                ("Anchor signal strong", "status"),
                ("Minor quantum fluctuation", "anomaly"),
                ("Synchronization complete", "system"),
            ]
            msg, event_type = random.choice(demo_messages)
            self._log_event(msg)

            # Add to actual timeline
            if self._machine:
                timeline = self._machine.timeline
                branches = timeline.list_branches()
                # Randomly pick a branch
                branch = random.choice(branches)
                stamp = ChronoStamp(frame_id="origin", t=self._demo_time)
                try:
                    timeline.create_event(
                        stamp,
                        event_type=event_type,
                        payload=msg.encode(),
                        branch_id=branch.branch_id
                    )
                except Exception:
                    pass  # Ignore errors in demo mode

        self.state_changed.emit()

    def _create_demo_branches(self) -> None:
        """Create demo branches to showcase branch visualization."""
        if not self._machine:
            return

        timeline = self._machine.timeline
        timeline.set_author("demo")

        try:
            # Get an event to fork from
            events = list(timeline.slice(branch_id="main"))
            if len(events) >= 2:
                fork_event = events[1]

                # Create first branch
                timeline.branch("experiment-alpha", from_event=fork_event.event_id)
                self._log_event("Branch 'experiment-alpha' created", "warning")

                # Add some events to the new branch
                for i in range(3):
                    stamp = ChronoStamp(frame_id="origin", t=self._demo_time + i * 0.3)
                    timeline.create_event(
                        stamp,
                        event_type="experiment",
                        payload=f"Alpha experiment {i+1}".encode(),
                        branch_id="experiment-alpha"
                    )

            # Create second branch from a different point
            if len(events) >= 3:
                fork_event2 = events[2]
                timeline.branch("experiment-beta", from_event=fork_event2.event_id)
                self._log_event("Branch 'experiment-beta' created", "warning")

                # Add events to second branch
                for i in range(2):
                    stamp = ChronoStamp(frame_id="origin", t=self._demo_time + i * 0.4)
                    timeline.create_event(
                        stamp,
                        event_type="experiment",
                        payload=f"Beta experiment {i+1}".encode(),
                        branch_id="experiment-beta"
                    )

        except Exception as e:
            self._log_event(f"Demo branch creation: {e}", "error")

    def shutdown(self) -> None:
        """Shutdown the time machine."""
        if self._demo_timer:
            self._demo_timer.stop()
            self._demo_timer = None

        if self._update_timer:
            self._update_timer.stop()
            self._update_timer = None

        if self._emulated_machine:
            self._emulated_machine.stop()
            self._emulated_machine = None
            self._initialized = False
            self._log_event("Emulated system shutdown")
        elif self._machine:
            self._machine.shutdown()
            self._machine = None
            self._initialized = False
            self._log_event("System shutdown")

    def reset(self) -> None:
        """Reset the machine state."""
        self.shutdown()
        self._event_log.clear()
        self.state_changed.emit()

    def update(self) -> None:
        """Called periodically to update state."""
        if self._machine:
            # Any continuous updates would go here
            self.state_changed.emit()

    def get_state(self) -> dict[str, Any]:
        """Get current machine state as a dictionary.

        Returns:
            Dictionary containing all relevant state.
        """
        # Use emulated machine if available
        if self._emulated_machine:
            return self._get_emulated_state()

        if not self._machine:
            return self._default_state()

        tdu = self._machine.tdu
        field = self._machine.field_generator
        causality = self._machine.causality_monitor
        anchor = self._machine.anchor
        navigator = self._machine.navigator
        safety = self._machine.safety

        # Get module statuses
        tdu_status = tdu.status.value if tdu else "unknown"
        field_status = field.status.value if field else "unknown"
        causality_status = causality.status.value if causality else "unknown"

        # Get current position (from machine, not TDU)
        current_pos = self._machine.current_position

        # Get field state
        field_state = field.get_field_state() if field else None

        # Get causality status
        causality_status_obj = causality.get_status() if causality else None

        # Get anchor info
        anchor_point = anchor.primary_anchor if anchor else None

        return {
            # Module statuses
            "tdu_status": tdu_status,
            "field_status": field_status,
            "causality_status": causality_status,
            "safety_status": safety.status.value if safety else "unknown",
            "anchor_status": anchor.status.value if anchor else "unknown",

            # Position
            "current_time": current_pos.t if current_pos else 0.0,
            "frame": current_pos.frame_id if current_pos else "origin",
            "uncertainty": current_pos.t_uncertainty if current_pos else 0.0,

            # Field
            "field_active": field_state.active if field_state else False,
            "field_strength": field_state.actual_b_tesla if field_state else 0.0,
            "field_symmetry": field_state.configuration.t_symmetry_factor if (field_state and field_state.configuration) else 0.0,
            "power_consumption": field_state.power_watts if field_state else 0.0,

            # Causality
            "causality": "NOMINAL" if (
                causality_status_obj and causality_status_obj.consistent
            ) else "WARNING",
            "paradox_risk": causality_status_obj.paradox_risk if causality_status_obj else 0.0,
            "causal_violations": [],  # Alerts tracked separately

            # Anchor
            "anchor_connected": anchor_point is not None,
            "anchor_time": anchor_point.stamp.t if anchor_point else None,
            "anchor_strength": anchor_point.strength if anchor_point else 0.0,

            # Overall
            "initialized": self._initialized,
            "is_displacing": tdu.is_displacing if hasattr(tdu, 'is_displacing') else False,

            # Relativistic quantities
            "velocity_beta": self._velocity_beta,
            "lorentz_gamma": lorentz_factor(self._velocity_beta) if 0 < self._velocity_beta < 1 else 1.0,
            "proper_time": self._proper_time,
        }

    def _get_emulated_state(self) -> dict[str, Any]:
        """Get state from emulated machine."""
        if not self._emulated_machine:
            return self._default_state()

        status = self._emulated_machine.get_status()
        machine_state = self._emulated_machine.get_state()

        # Map emulated status to expected format
        field = status.get("field", {})
        thermal = status.get("thermal", {})
        tdu = status.get("tdu", {})
        safety = status.get("safety", {})

        # Determine module status strings based on state
        if machine_state == MachineState.STANDBY:
            tdu_status = "standby"
            field_status = "active" if field.get("active") else "standby"
        elif machine_state == MachineState.DISPLACING:
            tdu_status = "active"
            field_status = "active"
        elif machine_state == MachineState.FIELD_RAMPING:
            tdu_status = "standby"
            field_status = "active"
        elif machine_state in (MachineState.FAULT, MachineState.EMERGENCY_STOP):
            tdu_status = "error"
            field_status = "error"
        else:
            tdu_status = "standby"
            field_status = "standby"

        return {
            # Module statuses
            "tdu_status": tdu_status,
            "field_status": field_status,
            "causality_status": "active",  # Always active in emulated mode
            "safety_status": "active" if safety.get("safe_to_operate") else "error",
            "anchor_status": "active",

            # Position
            "current_time": 0.0,  # TODO: Track from TDU sim_time
            "frame": "origin",
            "uncertainty": 0.0,

            # Field
            "field_active": field.get("active", False),
            "field_strength": field.get("field_tesla", 0.0),
            "field_symmetry": 0.0,  # Not tracked in emulated mode
            "power_consumption": field.get("power_watts", 0.0),

            # Thermal (additional info from emulated mode)
            "temperature_kelvin": thermal.get("temperature_kelvin", 4.2),
            "quench_risk": thermal.get("quench_risk", 0.0),

            # Causality
            "causality": "NOMINAL" if safety.get("safe_to_operate") else "WARNING",
            "paradox_risk": thermal.get("quench_risk", 0.0),  # Use quench risk as proxy
            "causal_violations": safety.get("faults", []),

            # Anchor
            "anchor_connected": True,
            "anchor_time": 0.0,
            "anchor_strength": 1.0,

            # Overall
            "initialized": self._initialized,
            "is_displacing": tdu.get("state") == "displacing",

            # Relativistic quantities
            "velocity_beta": self._velocity_beta,
            "lorentz_gamma": lorentz_factor(self._velocity_beta) if 0 < self._velocity_beta < 1 else 1.0,
            "proper_time": self._proper_time,

            # Emulated-specific
            "machine_state": machine_state.value if machine_state else "unknown",
            "ramp_state": field.get("ramp_state", "idle"),
            "tdu_phase": tdu.get("phase", "idle"),
            "tdu_progress": tdu.get("progress", 0.0),
        }

    def _default_state(self) -> dict[str, Any]:
        """Return default state when machine is not initialized."""
        return {
            "tdu_status": "offline",
            "field_status": "offline",
            "causality_status": "offline",
            "safety_status": "offline",
            "anchor_status": "offline",
            "current_time": 0.0,
            "frame": "origin",
            "uncertainty": 0.0,
            "field_active": False,
            "field_strength": 0.0,
            "field_symmetry": 0.0,
            "power_consumption": 0.0,
            "causality": "UNKNOWN",
            "paradox_risk": 0.0,
            "causal_violations": [],
            "anchor_connected": False,
            "anchor_time": None,
            "anchor_strength": 0.0,
            "initialized": False,
            "is_displacing": False,
            "velocity_beta": 0.0,
            "lorentz_gamma": 1.0,
            "proper_time": 0.0,
        }

    def get_module_statuses(self) -> dict[str, str]:
        """Get status of all modules.

        Returns:
            Dictionary mapping module name to status string.
        """
        if self._emulated_machine:
            status = self._emulated_machine.get_status()
            machine_state = self._emulated_machine.get_state()

            # Determine statuses based on machine state
            if machine_state == MachineState.OFFLINE:
                return {
                    "TDU": "OFFLINE",
                    "Field": "OFFLINE",
                    "Thermal": "OFFLINE",
                    "Safety": "OFFLINE",
                }
            elif machine_state in (MachineState.FAULT, MachineState.EMERGENCY_STOP):
                return {
                    "TDU": "ERROR",
                    "Field": "ERROR",
                    "Thermal": "WARNING",
                    "Safety": "ERROR",
                }
            else:
                field = status.get("field", {})
                safety = status.get("safety", {})
                thermal = status.get("thermal", {})

                return {
                    "TDU": "ACTIVE" if status.get("tdu", {}).get("state") == "displacing" else "STANDBY",
                    "Field": "ACTIVE" if field.get("active") else "STANDBY",
                    "Thermal": "WARNING" if thermal.get("quench_risk", 0) > 0.1 else "NOMINAL",
                    "Safety": "NOMINAL" if safety.get("safe_to_operate") else "WARNING",
                }

        if not self._machine:
            return {
                "TDU": "OFFLINE",
                "Field": "OFFLINE",
                "Causality": "OFFLINE",
                "Anchor": "OFFLINE",
                "Safety": "OFFLINE",
            }

        return {
            "TDU": self._machine.tdu.status.value.upper(),
            "Field": self._machine.field_generator.status.value.upper(),
            "Causality": self._machine.causality_monitor.status.value.upper(),
            "Anchor": self._machine.anchor.status.value.upper(),
            "Safety": self._machine.safety.status.value.upper(),
        }

    def displace(self, target_time: float) -> bool:
        """Execute temporal displacement.

        Args:
            target_time: Target time in seconds.

        Returns:
            True if displacement succeeded.
        """
        # Handle emulated mode
        if self._emulated_machine:
            return self._displace_emulated(target_time)

        if not self._machine:
            return False

        self._log_event(f"Displacement requested: t={target_time:.3f}s")
        self.displacement_started.emit()

        try:
            # Plan the displacement
            target = NavigationTarget(
                target_stamp=ChronoStamp(frame_id="origin", t=target_time),
                target_frame=TemporalFrame(frame_id="origin"),
            )

            paths = self._machine.plan_displacement(target)
            if not paths:
                self._log_event("No valid path found", "error")
                self.displacement_completed.emit(False)
                return False

            # Execute the first (best) path
            path = paths[0]
            self._log_event(f"Executing path: {path.path_type.value}")

            result = self._machine.execute_displacement(path)

            if result.success:
                self._log_event(
                    f"Displacement complete: t={result.final_position.t:.3f}s"
                )
                self.displacement_completed.emit(True)
                return True
            else:
                self._log_event(f"Displacement failed: {result.error}", "error")
                self.displacement_completed.emit(False)
                return False

        except Exception as e:
            self._log_event(f"Displacement error: {e}", "error")
            self.error_occurred.emit(str(e))
            self.displacement_completed.emit(False)
            return False

    def _displace_emulated(self, target_time: float) -> bool:
        """Execute displacement using emulated machine."""
        if not self._emulated_machine:
            return False

        self._log_event(f"Displacement requested: t={target_time:.3f}s")
        self.displacement_started.emit()

        try:
            # Use the emulated machine's displace method
            result = self._emulated_machine.displace(
                target_seconds=target_time,
                mode="backward" if target_time < 0 else "forward",
                energy_budget=1e12,
            )

            if result.success:
                self._log_event(
                    f"Displacement complete: Δt={result.actual_displacement:.3f}s, "
                    f"energy={result.energy_consumed_joules:.2e}J"
                )
                self.displacement_completed.emit(True)
                return True
            else:
                self._log_event(f"Displacement failed: {result.error_message}", "error")
                self.displacement_completed.emit(False)
                return False

        except Exception as e:
            self._log_event(f"Displacement error: {e}", "error")
            self.error_occurred.emit(str(e))
            self.displacement_completed.emit(False)
            return False

    def return_to_anchor(self) -> bool:
        """Return to anchor point.

        Returns:
            True if return succeeded.
        """
        if not self._machine:
            return False

        self._log_event("Return to anchor initiated")

        try:
            result = self._machine.return_to_anchor()

            if result and result.success:
                self._log_event("Return complete")
                self.state_changed.emit()
                return True
            else:
                self._log_event("Return failed", "error")
                return False

        except Exception as e:
            self._log_event(f"Return error: {e}", "error")
            self.error_occurred.emit(str(e))
            return False

    def emergency_stop(self) -> bool:
        """Execute emergency stop.

        Returns:
            True if stop succeeded.
        """
        self._log_event("EMERGENCY STOP", "critical")

        if self._emulated_machine:
            self._emulated_machine.emergency_stop()
            return True
        elif self._machine:
            return self._machine.emergency_stop()
        return True

    def get_events(self) -> list[dict]:
        """Get event log.

        Returns:
            List of event dictionaries.
        """
        return list(self._event_log)

    def get_branches(self) -> list[dict]:
        """Get timeline branches.

        Returns:
            List of branch dictionaries with branch_id, parent_branch, fork_event_id.
        """
        if not self._machine:
            return [{"branch_id": "main", "parent_branch": None, "fork_event_id": None, "event_count": 0}]

        try:
            branches = self._machine.timeline.list_branches()
            return [
                {
                    "branch_id": b.branch_id,
                    "parent_branch": b.parent_branch,
                    "fork_event_id": b.fork_event_id,
                    "event_count": b.event_count,
                }
                for b in branches
            ]
        except Exception:
            return [{"branch_id": "main", "parent_branch": None, "fork_event_id": None, "event_count": 0}]

    def get_timeline_events(self) -> list[dict]:
        """Get timeline events (from actual timeline, not GUI log).

        Returns:
            List of timeline event dictionaries formatted for EventDetailsDialog.
        """
        if not self._machine:
            return []

        try:
            events = []
            for branch in self._machine.timeline.list_branches():
                for event in self._machine.timeline.slice(branch_id=branch.branch_id):
                    # Decode payload if it's bytes
                    payload = {}
                    if event.payload:
                        try:
                            payload = {"message": event.payload.decode("utf-8")}
                        except Exception:
                            payload = {"raw": str(event.payload)}

                    events.append({
                        # Keys for timeline visualization
                        "time": event.stamp.t,
                        "event_id": event.event_id,

                        # Keys for EventDetailsDialog
                        "id": event.event_id,
                        "type": event.event_type,
                        "stamp": {
                            "t": event.stamp.t,
                            "t_uncertainty": event.stamp.t_uncertainty or 0.0,
                            "frame_id": event.stamp.frame_id,
                            "clock_id": event.stamp.clock_class or "N/A",
                        },
                        "branch_id": event.branch_id,
                        "sequence": event.seq,
                        "created_at": "N/A",  # Not tracked in TimelineEvent
                        "payload": payload,
                        "causal_parents": event.parents,
                    })
            return sorted(events, key=lambda e: e["time"])
        except Exception:
            return []

    def export_log(self, path: str) -> None:
        """Export event log to file.

        Args:
            path: Path to export to.
        """
        import json
        with open(path, "w") as f:
            json.dump(self._event_log, f, indent=2, default=str)
        self._log_event(f"Log exported to {path}")

    def load_scenario(self, scenario) -> dict:
        """Load a pre-built scenario into the timeline.

        Args:
            scenario: A Scenario object from timeos.paradoxes.

        Returns:
            Dictionary mapping event names to created events.
        """
        if not self._machine:
            raise RuntimeError("Machine not initialized")

        from timeos.msgs import TimelineEvent

        timeline = self._machine.timeline
        event_map = scenario.load(timeline)

        # Log the scenario load
        self._log_event(f"Loaded scenario: {scenario.title}")
        for event_name, event in event_map.items():
            self._log_event(f"  Created: {event_name} (t={event.stamp.t:.1f})")

        self.state_changed.emit()

        # Return mapping for GUI feedback
        return event_map

    def _log_event(
        self,
        message: str,
        level: str = "info",
    ) -> None:
        """Log an event.

        Args:
            message: Event message.
            level: Log level (info, warning, error, critical).
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "level": level,
        }
        self._event_log.append(event)
        self.event_logged.emit(event)
