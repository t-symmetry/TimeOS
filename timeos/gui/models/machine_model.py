"""Qt Model wrapping the SimulatedTimeMachine."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import QObject, Signal

from timeos.hardware.drivers.simulated import SimulatedTimeMachine
from timeos.hardware.timeline_navigator import NavigationTarget
from timeos.hardware.base import ModuleStatus
from timeos.msgs import ChronoStamp, TemporalFrame


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

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        self._machine: SimulatedTimeMachine | None = None
        self._event_log: list[dict] = []
        self._initialized = False

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

            self.state_changed.emit()
            return success

        except Exception as e:
            self.error_occurred.emit(str(e))
            return False

    def shutdown(self) -> None:
        """Shutdown the time machine."""
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

        tdu = self._machine._tdu
        field = self._machine._field_generator
        causality = self._machine._causality_monitor
        anchor = self._machine._anchor
        navigator = self._machine._navigator
        safety = self._machine._safety

        # Get module statuses
        tdu_status = tdu.status.value if tdu else "unknown"
        field_status = field.status.value if field else "unknown"
        causality_status = causality.status.value if causality else "unknown"

        # Get current position
        current_pos = tdu.current_position if tdu else None

        # Get field state
        field_state = field.get_field_state() if field else None

        # Get causality analysis
        causality_analysis = causality.analyze() if causality else None

        # Get anchor info
        anchor_point = anchor.get_anchor() if anchor else None

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
            "field_active": field_state.is_active if field_state else False,
            "field_strength": field_state.field_strength if field_state else 0.0,
            "field_symmetry": field_state.t_symmetry_factor if field_state else 0.0,
            "power_consumption": field_state.power_consumption if field_state else 0.0,

            # Causality
            "causality": "NOMINAL" if (
                causality_analysis and causality_analysis.is_consistent
            ) else "WARNING",
            "paradox_risk": causality_analysis.paradox_probability if causality_analysis else 0.0,
            "causal_violations": causality_analysis.violations if causality_analysis else [],

            # Anchor
            "anchor_connected": anchor_point is not None,
            "anchor_time": anchor_point.timestamp.t if anchor_point else None,
            "anchor_strength": anchor.signal_strength if anchor else 0.0,

            # Overall
            "initialized": self._initialized,
            "is_displacing": tdu.is_displacing if tdu else False,
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
            "TDU": self._machine._tdu.status.value.upper(),
            "Field": self._machine._field_generator.status.value.upper(),
            "Causality": self._machine._causality_monitor.status.value.upper(),
            "Anchor": self._machine._anchor.status.value.upper(),
            "Safety": self._machine._safety.status.value.upper(),
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
