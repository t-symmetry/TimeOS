"""Causality Monitor - Real-time paradox detection and prevention.

This module monitors causal consistency during temporal operations
and prevents (or manages) paradoxes.

Theoretical basis:
- Novikov self-consistency principle: paradoxes are impossible
- Many-worlds interpretation: paradoxes cause timeline branching
- Information-theoretic: causality violations create entropy anomalies

The causality monitor tracks causal relationships and alerts
when potential paradoxes are detected, allowing the system
to take preventive action.

Monitored conditions:
- Grandfather paradox: actions that prevent own existence
- Bootstrap paradox: information/objects with no origin
- Predestination loops: self-fulfilling prophecies
- Causal loops: A causes B causes A
- Information paradoxes: more info out than in
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from timeos.hardware.base import HardwareModule, ModuleStatus, ModuleDiagnostics
from timeos.msgs import ChronoStamp, TimelineEvent


class AlertSeverity(Enum):
    """Severity of causality alerts."""

    INFO = "info"  # Interesting but not dangerous
    WARNING = "warning"  # Potential issue, monitor closely
    CRITICAL = "critical"  # Imminent paradox, action required
    EMERGENCY = "emergency"  # Paradox in progress, abort


class ParadoxType(Enum):
    """Classification of potential paradoxes."""

    GRANDFATHER = "grandfather"  # Action prevents own existence
    BOOTSTRAP = "bootstrap"  # Object/info with no causal origin
    PREDESTINATION = "predestination"  # Self-fulfilling prophecy
    CAUSAL_LOOP = "causal_loop"  # Circular causation
    INFORMATION = "information"  # Conservation of information violation
    ENTROPY = "entropy"  # Second law violation
    ONTOLOGICAL = "ontological"  # Existence without cause
    CONSISTENCY = "consistency"  # Timeline inconsistency
    UNKNOWN = "unknown"  # Unclassified anomaly


class ResolutionStrategy(Enum):
    """Strategy for resolving paradoxes."""

    PREVENT = "prevent"  # Block the action causing paradox
    BRANCH = "branch"  # Create new timeline branch
    NOVIKOV = "novikov"  # Allow only self-consistent actions
    ABORT = "abort"  # Emergency abort of operation
    MONITOR = "monitor"  # Allow but observe closely
    ACCEPT = "accept"  # Accept the paradox (dangerous)


@dataclass
class CausalityAlert:
    """Alert for a potential causality violation.

    Attributes:
        alert_id: Unique identifier for this alert
        severity: Alert severity level
        paradox_type: Type of paradox detected
        description: Human-readable description
        timestamp: When the alert was generated
        source_event: Event that triggered the alert
        affected_events: Events that would be affected
        probability: Estimated probability of paradox (0.0 to 1.0)
        recommended_action: Suggested resolution strategy
        details: Additional diagnostic information
    """

    alert_id: str
    severity: AlertSeverity
    paradox_type: ParadoxType
    description: str
    timestamp: datetime
    source_event: str | None = None  # Event ID
    affected_events: list[str] = field(default_factory=list)
    probability: float = 0.0
    recommended_action: ResolutionStrategy = ResolutionStrategy.MONITOR
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_critical(self) -> bool:
        return self.severity in (AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY)


@dataclass
class CausalityStatus:
    """Overall causality status.

    Attributes:
        consistent: Whether timeline is currently consistent
        active_alerts: Number of unresolved alerts
        paradox_risk: Overall paradox risk (0.0 to 1.0)
        monitored_events: Number of events being tracked
        causal_depth: Depth of causal graph being analyzed
        last_check: Timestamp of last consistency check
    """

    consistent: bool = True
    active_alerts: int = 0
    paradox_risk: float = 0.0
    monitored_events: int = 0
    causal_depth: int = 0
    last_check: datetime = field(default_factory=datetime.utcnow)


class CausalityMonitor(HardwareModule):
    """Abstract interface for causality monitoring.

    The causality monitor is a critical safety system that
    tracks causal relationships and detects potential paradoxes
    before they occur (or as they're occurring).

    Integration:
    - Receives events from EventLog
    - Works with TimelineNavigator to predict consequences
    - Triggers SafetySystem on critical alerts
    - Can request displacement abort via TemporalDisplacementUnit

    Operating modes:
    - PASSIVE: Log alerts but don't intervene
    - ACTIVE: Prevent paradox-causing actions
    - STRICT: Abort on any causality anomaly
    """

    def __init__(self, module_id: str = "causality_monitor"):
        super().__init__(module_id)
        self._alerts: list[CausalityAlert] = []
        self._monitored_events: set[str] = set()
        self._resolution_strategy = ResolutionStrategy.BRANCH

    @property
    def default_strategy(self) -> ResolutionStrategy:
        """Default paradox resolution strategy."""
        return self._resolution_strategy

    @default_strategy.setter
    def default_strategy(self, strategy: ResolutionStrategy) -> None:
        self._resolution_strategy = strategy

    @abstractmethod
    def check_event(self, event: TimelineEvent) -> list[CausalityAlert]:
        """Check an event for causality violations.

        Args:
            event: Event to check.

        Returns:
            List of alerts generated (empty if none).
        """
        pass

    @abstractmethod
    def check_action(
        self, action_description: str, affected_events: list[str]
    ) -> list[CausalityAlert]:
        """Check a proposed action for causality issues.

        Args:
            action_description: Description of proposed action.
            affected_events: Events that would be affected.

        Returns:
            List of alerts for potential issues.
        """
        pass

    @abstractmethod
    def check_displacement(
        self, origin: ChronoStamp, destination: ChronoStamp
    ) -> list[CausalityAlert]:
        """Check a proposed displacement for causality issues.

        Args:
            origin: Starting point.
            destination: Target point.

        Returns:
            List of alerts for potential issues.
        """
        pass

    @abstractmethod
    def get_causal_chain(self, event_id: str, depth: int = 10) -> list[str]:
        """Get causal chain leading to an event.

        Args:
            event_id: Event to trace.
            depth: Maximum depth to trace.

        Returns:
            List of event IDs in causal order.
        """
        pass

    @abstractmethod
    def get_affected_events(self, event_id: str, depth: int = 10) -> list[str]:
        """Get events that would be affected by changing an event.

        Args:
            event_id: Event to analyze.
            depth: Maximum depth to analyze.

        Returns:
            List of affected event IDs.
        """
        pass

    @abstractmethod
    def simulate_change(
        self, event_id: str, change: dict[str, Any]
    ) -> tuple[bool, list[CausalityAlert]]:
        """Simulate changing an event and check consequences.

        Args:
            event_id: Event to modify.
            change: Proposed changes.

        Returns:
            Tuple of (is_safe, alerts).
        """
        pass

    @abstractmethod
    def get_status(self) -> CausalityStatus:
        """Get current causality status.

        Returns:
            Overall causality status.
        """
        pass

    def get_alerts(
        self,
        severity: AlertSeverity | None = None,
        unresolved_only: bool = True,
    ) -> list[CausalityAlert]:
        """Get causality alerts.

        Args:
            severity: Filter by severity (None = all).
            unresolved_only: Only return unresolved alerts.

        Returns:
            List of matching alerts.
        """
        alerts = self._alerts

        if severity is not None:
            alerts = [a for a in alerts if a.severity == severity]

        if unresolved_only:
            # In a real implementation, track resolution status
            pass

        return alerts

    def clear_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved.

        Args:
            alert_id: Alert to clear.

        Returns:
            True if alert was found and cleared.
        """
        for i, alert in enumerate(self._alerts):
            if alert.alert_id == alert_id:
                self._alerts.pop(i)
                return True
        return False
