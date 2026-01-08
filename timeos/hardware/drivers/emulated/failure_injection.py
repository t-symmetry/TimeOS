"""Failure Injection System - Configurable fault injection for testing.

Provides a comprehensive system for injecting failures into emulated
hardware modules for testing safety systems and recovery procedures.

Features:
- Central registry of failure scenarios
- Configurable trigger conditions (time, operations, random)
- Degradation profiles (gradual vs sudden failures)
- Recovery procedure testing
- Failure logging and statistics
"""

from __future__ import annotations

import random
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable
import uuid


class FailureSeverity(Enum):
    """Severity level of a failure."""

    INFO = "info"  # Informational, no action needed
    WARNING = "warning"  # Degraded but operational
    ERROR = "error"  # Significant impact, needs attention
    CRITICAL = "critical"  # System safety affected
    FATAL = "fatal"  # Complete system failure


class TriggerType(Enum):
    """How the failure is triggered."""

    IMMEDIATE = "immediate"  # Trigger immediately
    DELAYED = "delayed"  # Trigger after delay
    RANDOM = "random"  # Random trigger based on probability
    CONDITIONAL = "conditional"  # Trigger on condition
    SCHEDULED = "scheduled"  # Trigger at specific time
    OPERATION_COUNT = "operation_count"  # Trigger after N operations


class RecoveryType(Enum):
    """How the failure can be recovered."""

    AUTOMATIC = "automatic"  # Self-recovers after time
    MANUAL_RESET = "manual_reset"  # Requires manual reset
    RECALIBRATION = "recalibration"  # Requires recalibration
    HARDWARE_INTERVENTION = "hardware_intervention"  # Physical intervention needed
    UNRECOVERABLE = "unrecoverable"  # Cannot recover


@dataclass
class FailureScenario:
    """Definition of a failure scenario.

    Attributes:
        scenario_id: Unique identifier
        name: Human-readable name
        description: Detailed description
        severity: Failure severity level
        trigger_type: How the failure is triggered
        recovery_type: How to recover from failure
        affected_modules: List of module IDs affected
        trigger_params: Parameters for trigger (delay, probability, etc.)
        effects: Dictionary of effects to apply
        recovery_time_seconds: Time for automatic recovery
        enabled: Whether scenario is active
    """

    scenario_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    severity: FailureSeverity = FailureSeverity.ERROR
    trigger_type: TriggerType = TriggerType.IMMEDIATE
    recovery_type: RecoveryType = RecoveryType.MANUAL_RESET
    affected_modules: list[str] = field(default_factory=list)
    trigger_params: dict[str, Any] = field(default_factory=dict)
    effects: dict[str, Any] = field(default_factory=dict)
    recovery_time_seconds: float = 60.0
    enabled: bool = True

    def __post_init__(self):
        if not self.name:
            self.name = f"scenario_{self.scenario_id}"


@dataclass
class ActiveFailure:
    """An active failure instance.

    Attributes:
        failure_id: Unique instance identifier
        scenario: The failure scenario
        triggered_at: When the failure was triggered
        module_id: The affected module
        effects_applied: Effects currently applied
        recovery_started_at: When recovery began
        is_recovered: Whether failure has been recovered
    """

    failure_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scenario: FailureScenario | None = None
    triggered_at: datetime | None = None
    module_id: str = ""
    effects_applied: dict[str, Any] = field(default_factory=dict)
    recovery_started_at: datetime | None = None
    is_recovered: bool = False


@dataclass
class FailureStatistics:
    """Statistics about failure injection.

    Attributes:
        total_failures_injected: Total failures injected
        failures_by_severity: Count by severity level
        failures_by_module: Count by module
        average_recovery_time: Average time to recover
        unrecovered_failures: Current unrecovered count
    """

    total_failures_injected: int = 0
    failures_by_severity: dict[str, int] = field(default_factory=dict)
    failures_by_module: dict[str, int] = field(default_factory=dict)
    average_recovery_time: float = 0.0
    unrecovered_failures: int = 0


# Pre-defined failure scenarios for common hardware issues
BUILTIN_SCENARIOS = [
    FailureScenario(
        scenario_id="quench_sudden",
        name="Sudden Quench",
        description="Immediate superconducting quench with rapid field collapse",
        severity=FailureSeverity.CRITICAL,
        trigger_type=TriggerType.IMMEDIATE,
        recovery_type=RecoveryType.HARDWARE_INTERVENTION,
        effects={"quench": True, "field_collapse_rate": 100.0},
        recovery_time_seconds=3600.0,  # 1 hour cooldown
    ),
    FailureScenario(
        scenario_id="quench_thermal",
        name="Thermal Quench",
        description="Quench due to gradual temperature rise",
        severity=FailureSeverity.CRITICAL,
        trigger_type=TriggerType.CONDITIONAL,
        recovery_type=RecoveryType.RECALIBRATION,
        trigger_params={"condition": "temperature > 8.5"},
        effects={"quench": True, "temperature_spike": 50.0},
        recovery_time_seconds=1800.0,
    ),
    FailureScenario(
        scenario_id="power_supply_trip",
        name="Power Supply Trip",
        description="Power supply overcurrent protection triggered",
        severity=FailureSeverity.ERROR,
        trigger_type=TriggerType.RANDOM,
        recovery_type=RecoveryType.MANUAL_RESET,
        trigger_params={"probability_per_hour": 0.001},
        effects={"power_off": True, "current_zero": True},
        recovery_time_seconds=60.0,
    ),
    FailureScenario(
        scenario_id="cooling_degraded",
        name="Cooling System Degraded",
        description="Cryocooler performance reduced by 50%",
        severity=FailureSeverity.WARNING,
        trigger_type=TriggerType.DELAYED,
        recovery_type=RecoveryType.AUTOMATIC,
        trigger_params={"delay_seconds": 300.0},
        effects={"cooling_factor": 0.5},
        recovery_time_seconds=600.0,
    ),
    FailureScenario(
        scenario_id="sensor_drift",
        name="Sensor Calibration Drift",
        description="Field sensor showing systematic offset",
        severity=FailureSeverity.WARNING,
        trigger_type=TriggerType.OPERATION_COUNT,
        recovery_type=RecoveryType.RECALIBRATION,
        trigger_params={"operation_count": 100},
        effects={"field_offset_tesla": 0.01},
        recovery_time_seconds=120.0,
    ),
    FailureScenario(
        scenario_id="sensor_noise",
        name="Sensor Noise Increase",
        description="Increased noise in field measurements",
        severity=FailureSeverity.INFO,
        trigger_type=TriggerType.RANDOM,
        recovery_type=RecoveryType.AUTOMATIC,
        trigger_params={"probability_per_hour": 0.01},
        effects={"noise_multiplier": 3.0},
        recovery_time_seconds=300.0,
    ),
    FailureScenario(
        scenario_id="communication_timeout",
        name="Communication Timeout",
        description="Lost communication with module",
        severity=FailureSeverity.ERROR,
        trigger_type=TriggerType.RANDOM,
        recovery_type=RecoveryType.AUTOMATIC,
        trigger_params={"probability_per_hour": 0.0001},
        effects={"communication_lost": True},
        recovery_time_seconds=10.0,
    ),
    FailureScenario(
        scenario_id="interlock_trip",
        name="Safety Interlock Trip",
        description="Safety interlock triggered unexpectedly",
        severity=FailureSeverity.ERROR,
        trigger_type=TriggerType.CONDITIONAL,
        recovery_type=RecoveryType.MANUAL_RESET,
        trigger_params={"condition": "paradox_risk > 0.25"},
        effects={"interlock_engaged": True, "operations_blocked": True},
        recovery_time_seconds=0.0,  # Manual only
    ),
    FailureScenario(
        scenario_id="timing_drift",
        name="Timing System Drift",
        description="Gradual drift in timing calibration",
        severity=FailureSeverity.WARNING,
        trigger_type=TriggerType.DELAYED,
        recovery_type=RecoveryType.RECALIBRATION,
        trigger_params={"delay_seconds": 3600.0},  # After 1 hour
        effects={"timing_offset_seconds": 1e-6},
        recovery_time_seconds=300.0,
    ),
    FailureScenario(
        scenario_id="energy_overflow",
        name="Energy Storage Overflow",
        description="Capacitor bank voltage exceeds limit",
        severity=FailureSeverity.CRITICAL,
        trigger_type=TriggerType.CONDITIONAL,
        recovery_type=RecoveryType.HARDWARE_INTERVENTION,
        trigger_params={"condition": "energy > 0.95 * max_energy"},
        effects={"capacitor_discharge": True, "system_shutdown": True},
        recovery_time_seconds=7200.0,
    ),
]


class FailureInjector:
    """Central failure injection system.

    Manages failure scenarios, triggers failures based on conditions,
    and tracks recovery status.

    Usage:
        injector = FailureInjector()

        # Register a module
        injector.register_module("field_gen", field_generator.inject_fault)

        # Add custom scenario
        injector.add_scenario(FailureScenario(...))

        # Trigger failure
        injector.trigger_failure("quench_sudden", "field_gen")

        # Check status
        active = injector.get_active_failures()

        # Recover
        injector.recover_failure(failure_id)
    """

    def __init__(self, enable_builtin: bool = True):
        """Initialize failure injector.

        Args:
            enable_builtin: Whether to load built-in scenarios
        """
        self._scenarios: dict[str, FailureScenario] = {}
        self._active_failures: dict[str, ActiveFailure] = {}
        self._module_callbacks: dict[str, Callable[[str, dict], None]] = {}
        self._operation_counts: dict[str, int] = {}
        self._statistics = FailureStatistics()

        # Thread safety
        self._lock = threading.Lock()

        # Background thread for time-based triggers
        self._running = False
        self._update_thread: threading.Thread | None = None
        self._start_time = time.monotonic()

        # Load built-in scenarios
        if enable_builtin:
            for scenario in BUILTIN_SCENARIOS:
                self._scenarios[scenario.scenario_id] = scenario

    def start(self) -> None:
        """Start the failure injection system."""
        self._running = True
        self._start_time = time.monotonic()
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()

    def stop(self) -> None:
        """Stop the failure injection system."""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=1.0)

    def register_module(
        self,
        module_id: str,
        callback: Callable[[str, dict], None],
    ) -> None:
        """Register a module for failure injection.

        Args:
            module_id: Module identifier
            callback: Function to call with (fault_name, effects)
        """
        with self._lock:
            self._module_callbacks[module_id] = callback
            self._operation_counts[module_id] = 0

    def unregister_module(self, module_id: str) -> None:
        """Unregister a module."""
        with self._lock:
            self._module_callbacks.pop(module_id, None)
            self._operation_counts.pop(module_id, None)

    def add_scenario(self, scenario: FailureScenario) -> None:
        """Add a failure scenario."""
        with self._lock:
            self._scenarios[scenario.scenario_id] = scenario

    def remove_scenario(self, scenario_id: str) -> None:
        """Remove a failure scenario."""
        with self._lock:
            self._scenarios.pop(scenario_id, None)

    def get_scenarios(self) -> list[FailureScenario]:
        """Get all registered scenarios."""
        with self._lock:
            return list(self._scenarios.values())

    def get_scenario(self, scenario_id: str) -> FailureScenario | None:
        """Get a specific scenario."""
        return self._scenarios.get(scenario_id)

    def enable_scenario(self, scenario_id: str, enabled: bool = True) -> None:
        """Enable or disable a scenario."""
        if scenario_id in self._scenarios:
            self._scenarios[scenario_id].enabled = enabled

    def trigger_failure(
        self,
        scenario_id: str,
        module_id: str | None = None,
        custom_effects: dict[str, Any] | None = None,
    ) -> str | None:
        """Manually trigger a failure scenario.

        Args:
            scenario_id: Scenario to trigger
            module_id: Target module (or first affected if None)
            custom_effects: Override effects

        Returns:
            Failure ID if triggered, None if failed
        """
        scenario = self._scenarios.get(scenario_id)
        if not scenario or not scenario.enabled:
            return None

        # Determine target module
        if module_id is None:
            if scenario.affected_modules:
                module_id = scenario.affected_modules[0]
            else:
                # Apply to first registered module
                if not self._module_callbacks:
                    return None
                module_id = next(iter(self._module_callbacks.keys()))

        # Check module is registered
        if module_id not in self._module_callbacks:
            return None

        # Create active failure
        failure = ActiveFailure(
            scenario=scenario,
            triggered_at=datetime.utcnow(),
            module_id=module_id,
            effects_applied=custom_effects or scenario.effects.copy(),
        )

        with self._lock:
            self._active_failures[failure.failure_id] = failure

            # Update statistics
            self._statistics.total_failures_injected += 1
            severity_key = scenario.severity.value
            self._statistics.failures_by_severity[severity_key] = \
                self._statistics.failures_by_severity.get(severity_key, 0) + 1
            self._statistics.failures_by_module[module_id] = \
                self._statistics.failures_by_module.get(module_id, 0) + 1
            self._statistics.unrecovered_failures += 1

        # Invoke callback
        callback = self._module_callbacks[module_id]
        callback(scenario.name, failure.effects_applied)

        return failure.failure_id

    def recover_failure(self, failure_id: str) -> bool:
        """Attempt to recover from a failure.

        Args:
            failure_id: The failure to recover

        Returns:
            True if recovery succeeded
        """
        with self._lock:
            failure = self._active_failures.get(failure_id)
            if not failure or failure.is_recovered:
                return False

            scenario = failure.scenario
            if scenario is None:
                return False

            # Check recovery type
            if scenario.recovery_type == RecoveryType.UNRECOVERABLE:
                return False

            if scenario.recovery_type == RecoveryType.AUTOMATIC:
                # Automatic recovery happens in background
                return False

            # Mark as recovered
            failure.is_recovered = True
            failure.recovery_started_at = datetime.utcnow()
            self._statistics.unrecovered_failures -= 1

            # Update average recovery time
            if failure.triggered_at:
                recovery_time = (datetime.utcnow() - failure.triggered_at).total_seconds()
                total_recovered = self._statistics.total_failures_injected - self._statistics.unrecovered_failures
                if total_recovered > 0:
                    self._statistics.average_recovery_time = (
                        (self._statistics.average_recovery_time * (total_recovered - 1) + recovery_time)
                        / total_recovered
                    )

        return True

    def get_active_failures(self, module_id: str | None = None) -> list[ActiveFailure]:
        """Get active (unrecovered) failures.

        Args:
            module_id: Filter by module (None = all modules)

        Returns:
            List of active failures
        """
        with self._lock:
            failures = [f for f in self._active_failures.values() if not f.is_recovered]
            if module_id:
                failures = [f for f in failures if f.module_id == module_id]
            return failures

    def get_statistics(self) -> FailureStatistics:
        """Get failure injection statistics."""
        return self._statistics

    def increment_operation_count(self, module_id: str) -> None:
        """Increment operation count for operation-count triggers.

        Call this from modules after each operation.
        """
        with self._lock:
            self._operation_counts[module_id] = self._operation_counts.get(module_id, 0) + 1

    def check_condition(self, module_id: str, conditions: dict[str, Any]) -> None:
        """Check conditions for conditional triggers.

        Args:
            module_id: Module to check
            conditions: Current condition values
        """
        with self._lock:
            for scenario in self._scenarios.values():
                if not scenario.enabled:
                    continue
                if scenario.trigger_type != TriggerType.CONDITIONAL:
                    continue
                if module_id not in scenario.affected_modules and scenario.affected_modules:
                    continue

                # Simple condition evaluation
                condition = scenario.trigger_params.get("condition", "")
                if self._evaluate_condition(condition, conditions):
                    # Don't trigger if already active for this module
                    already_active = any(
                        f.scenario and f.scenario.scenario_id == scenario.scenario_id
                        and f.module_id == module_id
                        and not f.is_recovered
                        for f in self._active_failures.values()
                    )
                    if not already_active:
                        self.trigger_failure(scenario.scenario_id, module_id)

    def clear_all(self) -> None:
        """Clear all active failures and reset statistics."""
        with self._lock:
            self._active_failures.clear()
            self._operation_counts = {k: 0 for k in self._operation_counts}
            self._statistics = FailureStatistics()

    def _update_loop(self) -> None:
        """Background update loop for time-based triggers."""
        last_update = time.monotonic()

        while self._running:
            try:
                now = time.monotonic()
                dt = now - last_update
                last_update = now

                self._check_triggers(dt)
                self._check_automatic_recovery()

                time.sleep(0.1)  # 10 Hz update rate
            except Exception:
                pass

    def _check_triggers(self, dt: float) -> None:
        """Check for triggered scenarios."""
        elapsed = time.monotonic() - self._start_time
        hours = elapsed / 3600.0

        with self._lock:
            for scenario in self._scenarios.values():
                if not scenario.enabled:
                    continue

                # Check each registered module
                for module_id in self._module_callbacks:
                    if scenario.affected_modules and module_id not in scenario.affected_modules:
                        continue

                    # Check if already active
                    already_active = any(
                        f.scenario and f.scenario.scenario_id == scenario.scenario_id
                        and f.module_id == module_id
                        and not f.is_recovered
                        for f in self._active_failures.values()
                    )
                    if already_active:
                        continue

                    should_trigger = False

                    if scenario.trigger_type == TriggerType.DELAYED:
                        delay = scenario.trigger_params.get("delay_seconds", 0)
                        if elapsed > delay:
                            should_trigger = True

                    elif scenario.trigger_type == TriggerType.RANDOM:
                        prob_per_hour = scenario.trigger_params.get("probability_per_hour", 0)
                        prob_per_dt = prob_per_hour * (dt / 3600.0)
                        if random.random() < prob_per_dt:
                            should_trigger = True

                    elif scenario.trigger_type == TriggerType.OPERATION_COUNT:
                        target_count = scenario.trigger_params.get("operation_count", 0)
                        current_count = self._operation_counts.get(module_id, 0)
                        if current_count >= target_count:
                            should_trigger = True

                    if should_trigger:
                        # Release lock before triggering
                        self._lock.release()
                        try:
                            self.trigger_failure(scenario.scenario_id, module_id)
                        finally:
                            self._lock.acquire()

    def _check_automatic_recovery(self) -> None:
        """Check for automatic recovery of failures."""
        now = datetime.utcnow()

        with self._lock:
            for failure in self._active_failures.values():
                if failure.is_recovered:
                    continue

                scenario = failure.scenario
                if scenario is None or scenario.recovery_type != RecoveryType.AUTOMATIC:
                    continue

                if failure.triggered_at:
                    elapsed = (now - failure.triggered_at).total_seconds()
                    if elapsed >= scenario.recovery_time_seconds:
                        failure.is_recovered = True
                        failure.recovery_started_at = now
                        self._statistics.unrecovered_failures -= 1

    def _evaluate_condition(self, condition: str, values: dict[str, Any]) -> bool:
        """Evaluate a simple condition string.

        Supports: var > val, var < val, var == val
        """
        if not condition:
            return False

        # Simple parser for "var op val" format
        for op in [">", "<", "==", ">=", "<="]:
            if op in condition:
                parts = condition.split(op)
                if len(parts) != 2:
                    return False

                var_name = parts[0].strip()
                try:
                    threshold = float(parts[1].strip())
                except ValueError:
                    return False

                value = values.get(var_name)
                if value is None:
                    return False

                if op == ">":
                    return value > threshold
                elif op == "<":
                    return value < threshold
                elif op == ">=":
                    return value >= threshold
                elif op == "<=":
                    return value <= threshold
                elif op == "==":
                    return value == threshold

        return False
