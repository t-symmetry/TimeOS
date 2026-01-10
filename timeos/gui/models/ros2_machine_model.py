"""ROS2 Machine Model - Pure ROS2 interface for GUI.

This model gets all state from ROS2 topics and executes actions via ROS2 services.
It's a drop-in replacement for MachineModel when running in ROS2 mode.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Signal, QTimer

from timeos.gui.ros2.ros2_bridge import ROS2Bridge, STATE_TOPICS


class ROS2MachineModel(QObject):
    """Machine model that uses ROS2 exclusively for state and control.

    This provides the same interface as MachineModel but all data comes
    from ROS2 topics and all actions go through ROS2 services.

    Signals match MachineModel for drop-in compatibility.
    """

    # Signals (matching MachineModel)
    state_changed = Signal()
    event_logged = Signal(dict)
    module_status_changed = Signal(str, str)  # module_name, status
    displacement_started = Signal()
    displacement_completed = Signal(bool)  # success
    error_occurred = Signal(str)

    def __init__(
        self,
        bridge: Optional[ROS2Bridge] = None,
        parent: QObject | None = None,
    ):
        """Initialize ROS2 machine model.

        Args:
            bridge: Existing ROS2Bridge instance. If None, creates one.
            parent: Parent QObject.
        """
        super().__init__(parent)

        # Use provided bridge or create new one
        self._bridge = bridge if bridge else ROS2Bridge(self)
        self._owns_bridge = bridge is None

        self._event_log: List[Dict] = []
        self._initialized = False

        # Connect bridge signals
        self._bridge.state_updated.connect(self._on_state_updated)
        self._bridge.service_response.connect(self._on_service_response)
        self._bridge.error_occurred.connect(self._on_error)

        # Pending service calls
        self._pending_displacement = False

    @property
    def bridge(self) -> ROS2Bridge:
        """Access to the underlying ROS2Bridge."""
        return self._bridge

    def initialize(self) -> bool:
        """Initialize the ROS2 connection.

        Returns:
            True if ROS2 is available.
        """
        if not self._bridge.ros2_available:
            self._log_event("ROS2 not available", "error")
            return False

        self._initialized = True
        self._log_event(f"ROS2 connection established ({self._bridge.ros2_source})")

        # Start state polling
        self._bridge.start_state_polling(500)  # 2 Hz
        self._bridge.start_refresh(2000)  # Node list refresh

        self._log_event("State polling started")
        self.state_changed.emit()

        return True

    def shutdown(self) -> None:
        """Shutdown the model."""
        self._bridge.stop_state_polling()
        self._bridge.stop_refresh()

        if self._owns_bridge:
            self._bridge.shutdown()

        self._initialized = False
        self._log_event("ROS2 connection closed")

    def reset(self) -> None:
        """Reset the model state."""
        self.shutdown()
        self._event_log.clear()
        self.state_changed.emit()

    def update(self) -> None:
        """Called periodically to update state.

        In ROS2 mode, state updates come from the bridge's polling,
        so this is a no-op.
        """
        # State updates are handled by bridge polling
        pass

    def get_state(self) -> Dict[str, Any]:
        """Get current machine state.

        Returns:
            Dictionary containing all machine state from ROS2.
        """
        if not self._initialized:
            return self._default_state()

        return self._bridge.get_machine_state()

    def _default_state(self) -> Dict[str, Any]:
        """Return default state when not initialized."""
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

    def get_module_statuses(self) -> Dict[str, str]:
        """Get status of all modules.

        Returns:
            Dictionary mapping module name to status string.
        """
        if not self._initialized:
            return {
                "TDU": "OFFLINE",
                "Field": "OFFLINE",
                "Thermal": "OFFLINE",
                "Safety": "OFFLINE",
                "Causality": "OFFLINE",
            }

        state = self._bridge.get_machine_state()
        return {
            "TDU": state.get("tdu_status", "unknown").upper(),
            "Field": state.get("field_status", "unknown").upper(),
            "Thermal": "WARNING" if state.get("quench_risk", 0) > 0.1 else "NOMINAL",
            "Safety": state.get("safety_status", "unknown").upper(),
            "Causality": state.get("causality_status", "unknown").upper(),
        }

    def displace(self, target_time: float) -> bool:
        """Execute temporal displacement via ROS2 service.

        Args:
            target_time: Target time in seconds.

        Returns:
            True if request was sent (actual result comes async).
        """
        if not self._initialized:
            return False

        self._log_event(f"Displacement requested: t={target_time:.3f}s")
        self.displacement_started.emit()
        self._pending_displacement = True

        # Call the displacement service
        # Note: Actual displacement service would be /timeos/plan_displacement
        # For now, log that this would be a service call
        self._log_event("Displacement service call (simulated)")

        # Simulate async completion
        QTimer.singleShot(1000, lambda: self._complete_displacement(True))

        return True

    def _complete_displacement(self, success: bool) -> None:
        """Complete a pending displacement."""
        self._pending_displacement = False
        if success:
            self._log_event("Displacement complete")
        else:
            self._log_event("Displacement failed", "error")
        self.displacement_completed.emit(success)

    def emergency_stop(self) -> bool:
        """Execute emergency stop via ROS2 service.

        Returns:
            True if request was sent.
        """
        self._log_event("EMERGENCY STOP", "critical")

        if not self._initialized:
            return True

        # Call E-stop service
        self._bridge.call_service(
            '/timeos/trigger_estop',
            'timeos_msgs/srv/TriggerEstop',
            {'reason': 'GUI emergency stop'}
        )

        return True

    def set_field(self, strength: float, ramp_rate: float = 0.1) -> bool:
        """Set field strength via ROS2 service.

        Args:
            strength: Target field strength in Tesla.
            ramp_rate: Ramp rate in T/s.

        Returns:
            True if request was sent.
        """
        if not self._initialized:
            return False

        self._log_event(f"Set field: {strength:.2f} T at {ramp_rate:.3f} T/s")

        self._bridge.call_service(
            '/timeos/set_field',
            'timeos_msgs/srv/SetField',
            {
                'field_strength_tesla': strength,
                'ramp_rate_tesla_per_sec': ramp_rate,
            }
        )

        return True

    def arm_system(self, arm: bool = True, operator: str = "gui") -> bool:
        """Arm or disarm the system via ROS2 service.

        Args:
            arm: True to arm, False to disarm.
            operator: Operator identifier.

        Returns:
            True if request was sent.
        """
        if not self._initialized:
            return False

        action = "Arming" if arm else "Disarming"
        self._log_event(f"{action} system")

        self._bridge.call_service(
            '/timeos/arm_system',
            'timeos_msgs/srv/ArmSystem',
            {
                'arm': arm,
                'operator_id': operator,
            }
        )

        return True

    def get_events(self) -> List[Dict]:
        """Get event log.

        Returns:
            List of event dictionaries.
        """
        return list(self._event_log)

    def get_branches(self) -> List[Dict]:
        """Get timeline branches.

        Note: Would need to query timeline node for real data.

        Returns:
            List of branch dictionaries.
        """
        # This would query the timeline node
        return [{"branch_id": "main", "parent_branch": None, "fork_event_id": None, "event_count": 0}]

    def get_timeline_events(self) -> List[Dict]:
        """Get timeline events.

        Note: Would need to query timeline node for real data.

        Returns:
            List of timeline event dictionaries.
        """
        # This would query the timeline node
        return []

    def _on_state_updated(self, state: Dict[str, Any]) -> None:
        """Handle state update from bridge."""
        self.state_changed.emit()

    def _on_service_response(self, service: str, success: bool, response: str) -> None:
        """Handle service response from bridge."""
        if 'estop' in service:
            if success:
                self._log_event("E-stop acknowledged")
            else:
                self._log_event(f"E-stop failed: {response}", "error")
        elif 'set_field' in service:
            if success:
                self._log_event("Field command acknowledged")
            else:
                self._log_event(f"Field command failed: {response}", "error")
        elif 'arm' in service:
            if success:
                self._log_event("Arm/disarm acknowledged")
            else:
                self._log_event(f"Arm/disarm failed: {response}", "error")

    def _on_error(self, error: str) -> None:
        """Handle error from bridge."""
        self._log_event(f"ROS2 error: {error}", "error")
        self.error_occurred.emit(error)

    def _log_event(self, message: str, level: str = "info") -> None:
        """Log an event.

        Args:
            message: Event message.
            level: Log level.
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "level": level,
        }
        self._event_log.append(event)
        self.event_logged.emit(event)

    # Properties and methods for compatibility with MachineModel

    @property
    def is_emulated(self) -> bool:
        """Return True if running in emulated mode (ROS2 is always 'real')."""
        return False

    @property
    def is_demo(self) -> bool:
        """Return True if running in demo mode."""
        return False

    @property
    def is_ros2(self) -> bool:
        """Return True - this is the ROS2 model."""
        return True

    # Module enable/disable controls (compatibility stubs)
    # In ROS2 mode, modules are controlled via ROS2 services, not locally

    def get_module_enabled(self, module: str) -> bool:
        """Get whether a module is enabled.

        In ROS2 mode, all modules are considered enabled if ROS2 is available.

        Args:
            module: Module name.

        Returns:
            True if enabled.
        """
        return self._initialized

    def set_module_enabled(self, module: str, enabled: bool) -> None:
        """Enable or disable a module.

        In ROS2 mode, this would need to call a ROS2 service.

        Args:
            module: Module name.
            enabled: True to enable.
        """
        action = "enabled" if enabled else "disabled"
        self._log_event(f"Module {module} {action} (ROS2 - no-op)")
        self.module_status_changed.emit(module, action)

    def get_available_modules(self) -> List[str]:
        """Get list of available module names.

        Returns:
            List of module names.
        """
        return ["field_generator", "tdu", "causality", "safety", "thermal"]

    def return_to_anchor(self) -> bool:
        """Return to anchor point.

        Returns:
            True if request was sent.
        """
        self._log_event("Return to anchor requested")
        # Would call a ROS2 service
        return True

    def load_scenario(self, scenario) -> Dict:
        """Load a scenario.

        In ROS2 mode, scenarios would be loaded via timeline node.

        Args:
            scenario: Scenario to load.

        Returns:
            Empty dict (not implemented in ROS2 mode).
        """
        self._log_event(f"Scenario loading not implemented in ROS2 mode")
        return {}

    def export_log(self, path: str) -> None:
        """Export event log to file.

        Args:
            path: Path to export to.
        """
        import json
        with open(path, "w") as f:
            json.dump(self._event_log, f, indent=2, default=str)
        self._log_event(f"Log exported to {path}")
