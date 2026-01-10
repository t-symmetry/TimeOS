#!/usr/bin/env python3
"""Causality Monitor Node - ROS2 node for real-time causality checking.

This node provides:
- Causality status publishing
- Event validation via /causality/validate service
- Light cone analysis
- Paradox risk assessment
"""

from __future__ import annotations

import time
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

from std_msgs.msg import Float64, Bool

# TimeOS imports
try:
    from timeos.physics.causality import (
        LightCone,
        CausalRelation,
        check_causal_ordering,
    )
    from timeos.physics.spacetime import SpacetimeEvent
    from timeos.core.constraints import (
        LightConeConstraint,
        ConstraintCheck,
        ConstraintStatus,
    )
    TIMEOS_PHYSICS_AVAILABLE = True
except ImportError:
    TIMEOS_PHYSICS_AVAILABLE = False

# Message imports
from timeos_msgs.msg import TimelineEvent

# Service imports
from timeos_ros.srv import ValidateCausality, GetStatus


class CausalityMonitorNode(Node):
    """ROS2 node for real-time causality monitoring.

    Subscribes:
        /timeline/events (TimelineEvent): Timeline events to monitor

    Publishes:
        /causality/risk (Float64): Current paradox risk (0.0-1.0)
        /causality/valid (Bool): Whether causality is currently preserved

    Services:
        /causality/validate (ValidateCausality): Validate proposed events
        /causality/get_status (GetStatus): Get detailed status
    """

    def __init__(self):
        super().__init__("causality_monitor_node")

        # Parameters
        self.declare_parameter("risk_threshold_warning", 0.05)
        self.declare_parameter("risk_threshold_branch", 0.15)
        self.declare_parameter("risk_threshold_reject", 0.30)
        self.declare_parameter("publish_rate_hz", 10.0)

        self._warn_threshold = self.get_parameter("risk_threshold_warning").value
        self._branch_threshold = self.get_parameter("risk_threshold_branch").value
        self._reject_threshold = self.get_parameter("risk_threshold_reject").value
        publish_rate = self.get_parameter("publish_rate_hz").value

        # State
        self._current_risk = 0.0
        self._causality_valid = True
        self._recent_events: list[dict] = []
        self._violations: list[str] = []
        self._max_recent = 100

        # Subscriber for timeline events
        self._event_sub = self.create_subscription(
            TimelineEvent,
            "/timeline/events",
            self._on_event,
            10,
        )

        # Publishers
        self._risk_pub = self.create_publisher(Float64, "/causality/risk", 10)
        self._valid_pub = self.create_publisher(Bool, "/causality/valid", 10)

        # Services
        self._validate_srv = self.create_service(
            ValidateCausality,
            "/causality/validate",
            self._handle_validate,
        )

        self._status_srv = self.create_service(
            GetStatus,
            "/causality/get_status",
            self._handle_get_status,
        )

        # Timer
        self._timer = self.create_timer(1.0 / publish_rate, self._publish_status)

        self.get_logger().info(
            f"Causality monitor started (physics available: {TIMEOS_PHYSICS_AVAILABLE})"
        )

    def _on_event(self, msg: TimelineEvent):
        """Handle incoming timeline event."""
        # Store for analysis
        event_data = {
            "event_id": msg.event_id,
            "t": msg.stamp.t,
            "frame_id": msg.stamp.frame_id,
            "parents": list(msg.parents),
            "event_type": msg.event_type,
            "timestamp": time.time(),
        }

        self._recent_events.append(event_data)
        if len(self._recent_events) > self._max_recent:
            self._recent_events.pop(0)

        # Check causality
        self._check_event_causality(event_data)

    def _check_event_causality(self, event: dict):
        """Check causality constraints for an event."""
        if not TIMEOS_PHYSICS_AVAILABLE:
            return

        # Simple check: parents should have earlier timestamps
        for parent_id in event["parents"]:
            parent = next(
                (e for e in self._recent_events if e["event_id"] == parent_id),
                None,
            )
            if parent and parent["t"] > event["t"]:
                violation = (
                    f"Causal violation: {event['event_id']} (t={event['t']:.3f}) "
                    f"has parent {parent_id} (t={parent['t']:.3f})"
                )
                self._violations.append(violation)
                self._current_risk = min(1.0, self._current_risk + 0.1)
                self.get_logger().warn(violation)

        # Decay risk over time
        self._current_risk = max(0.0, self._current_risk - 0.01)
        self._causality_valid = self._current_risk < self._reject_threshold

    def _publish_status(self):
        """Publish current causality status."""
        risk_msg = Float64()
        risk_msg.data = self._current_risk
        self._risk_pub.publish(risk_msg)

        valid_msg = Bool()
        valid_msg.data = self._causality_valid
        self._valid_pub.publish(valid_msg)

    def _handle_validate(
        self,
        request: ValidateCausality.Request,
        response: ValidateCausality.Response,
    ) -> ValidateCausality.Response:
        """Handle ValidateCausality service request."""
        try:
            # Get parameters from request
            if request.proposed_event.event_id:
                proposed_t = request.proposed_event.stamp.t
                proposed_frame = request.proposed_event.stamp.frame_id
                proposed_parents = list(request.proposed_event.parents)
            else:
                proposed_t = request.proposed_t
                proposed_frame = request.proposed_frame_id
                proposed_parents = list(request.proposed_parents)

            # Initialize response
            response.valid = True
            response.risk_level = 0.0
            response.check_names = []
            response.check_passed = []
            response.check_messages = []
            response.check_risk_contributions = []

            # Check 1: Temporal ordering
            check_name = "temporal_ordering"
            check_passed = True
            check_msg = "Parents precede event"
            check_risk = 0.0

            for parent_id in proposed_parents:
                parent = next(
                    (e for e in self._recent_events if e["event_id"] == parent_id),
                    None,
                )
                if parent and parent["t"] > proposed_t:
                    check_passed = False
                    check_msg = f"Parent {parent_id} has later timestamp"
                    check_risk = 0.3

            response.check_names.append(check_name)
            response.check_passed.append(check_passed)
            response.check_messages.append(check_msg)
            response.check_risk_contributions.append(check_risk)
            response.risk_level += check_risk

            # Check 2: Light cone (if physics available)
            if TIMEOS_PHYSICS_AVAILABLE:
                check_name = "light_cone"
                check_passed = True
                check_msg = "Within light cone"
                check_risk = 0.0

                # For demonstration, assume spatial origin
                proposed_event = SpacetimeEvent(proposed_t, 0, 0, 0)

                for parent_id in proposed_parents:
                    parent = next(
                        (e for e in self._recent_events if e["event_id"] == parent_id),
                        None,
                    )
                    if parent:
                        parent_event = SpacetimeEvent(parent["t"], 0, 0, 0)
                        relation = check_causal_ordering(parent_event, proposed_event)

                        if relation == CausalRelation.SPACELIKE:
                            check_passed = False
                            check_msg = f"Spacelike separated from parent {parent_id}"
                            check_risk = 0.2

                        # Light cone info
                        interval = proposed_event.interval_to(parent_event)
                        response.spacetime_interval = interval

                        # Determine light cone position
                        if relation == CausalRelation.FUTURE_TIMELIKE:
                            response.in_future_light_cone = True
                        elif relation == CausalRelation.PAST_TIMELIKE:
                            response.in_past_light_cone = True

                response.check_names.append(check_name)
                response.check_passed.append(check_passed)
                response.check_messages.append(check_msg)
                response.check_risk_contributions.append(check_risk)
                response.risk_level += check_risk

            # Check 3: Self-causation
            check_name = "no_self_causation"
            check_passed = True
            check_msg = "No self-causation"
            check_risk = 0.0

            # Would need event_id to check properly
            if request.proposed_event.event_id:
                if request.proposed_event.event_id in proposed_parents:
                    check_passed = False
                    check_msg = "Event is its own ancestor"
                    check_risk = 0.5

            response.check_names.append(check_name)
            response.check_passed.append(check_passed)
            response.check_messages.append(check_msg)
            response.check_risk_contributions.append(check_risk)
            response.risk_level += check_risk

            # Overall validity
            response.valid = all(response.check_passed)
            response.violated_constraints = [
                name for name, passed in zip(response.check_names, response.check_passed)
                if not passed
            ]

        except Exception as e:
            response.valid = False
            response.error_message = str(e)
            self.get_logger().error(f"Failed to validate: {e}")

        return response

    def _handle_get_status(
        self,
        request: GetStatus.Request,
        response: GetStatus.Response,
    ) -> GetStatus.Response:
        """Handle GetStatus service request."""
        response.timestamp = time.time()

        if self._current_risk < self._warn_threshold:
            response.module_state = "nominal"
        elif self._current_risk < self._branch_threshold:
            response.module_state = "warning"
        elif self._current_risk < self._reject_threshold:
            response.module_state = "elevated"
        else:
            response.module_state = "critical"

        response.system_state = response.module_state
        response.safe_to_operate = self._causality_valid

        # Recent violations as warnings
        response.warnings = self._violations[-5:]  # Last 5

        if request.include_diagnostics:
            response.status_keys = [
                "risk_level",
                "causality_valid",
                "recent_events",
                "violations_count",
                "warn_threshold",
                "reject_threshold",
            ]
            response.status_values = [
                f"{self._current_risk:.3f}",
                str(self._causality_valid),
                str(len(self._recent_events)),
                str(len(self._violations)),
                f"{self._warn_threshold:.3f}",
                f"{self._reject_threshold:.3f}",
            ]

        return response


def main(args=None):
    """Run the causality monitor node."""
    rclpy.init(args=args)

    node = CausalityMonitorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
