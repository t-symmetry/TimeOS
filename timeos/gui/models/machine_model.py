"""Qt Model wrapping the SimulatedTimeMachine."""

from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Any

from PySide6.QtCore import QObject, Signal, QTimer

from timeos.hardware.drivers.simulated import SimulatedTimeMachine
from timeos.hardware.timeline_navigator import NavigationTarget
from timeos.hardware.base import ModuleStatus
from timeos.msgs import ChronoStamp, TemporalFrame
from timeos.physics import lorentz_factor


class MachineModel(QObject):
    """Qt model wrapping SimulatedTimeMachine for GUI integration.

    Provides signals for state changes and exposes machine functionality
    in a GUI-friendly way.
    """

    # Signals
    state_changed = Signal()
    event_logged = Signal(dict)
    module_status_changed = Signal(str, str)  # module_name, status
    displacement_started = Signal()
    displacement_completed = Signal(bool)  # success
    error_occurred = Signal(str)

    def __init__(self, demo: bool = False, parent: QObject | None = None):
        super().__init__(parent)

        self._machine: SimulatedTimeMachine | None = None
        self._event_log: list[dict] = []
        self._initialized = False
        self._demo = demo
        self._demo_timer: QTimer | None = None
        self._demo_time = 0.0

        # Relativistic state tracking
        self._velocity_beta = 0.0  # v/c (fraction of light speed)
        self._proper_time = 0.0    # τ (proper time accumulated)

    def initialize(self) -> bool:
        """Initialize the time machine.

        Returns:
            True if initialization succeeded.
        """
        try:
            self._machine = SimulatedTimeMachine()
            success = self._machine.initialize()

            if success:
                self._initialized = True
                self._log_event("System initialized")

                # Set initial anchor
                self._machine.set_anchor()
                self._log_event("Anchor point established")

                # Start demo mode if enabled
                if self._demo:
                    self._start_demo()

            self.state_changed.emit()
            return success

        except Exception as e:
            self.error_occurred.emit(str(e))
            return False

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

        if self._machine:
            self._machine.shutdown()
            self._initialized = False
            self._log_event("System shutdown")

    def reset(self) -> None:
        """Reset the machine state."""
        if self._machine:
            self._machine.shutdown()
        self._machine = None
        self._initialized = False
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

        if self._machine:
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
            List of timeline event dictionaries.
        """
        if not self._machine:
            return []

        try:
            events = []
            for branch in self._machine.timeline.list_branches():
                for event in self._machine.timeline.slice(branch_id=branch.branch_id):
                    events.append({
                        "event_id": event.event_id,
                        "time": event.stamp.t,
                        "frame_id": event.stamp.frame_id,
                        "event_type": event.event_type,
                        "branch_id": event.branch_id,
                        "parents": event.parents,
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
