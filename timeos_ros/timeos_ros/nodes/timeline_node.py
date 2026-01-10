#!/usr/bin/env python3
"""Timeline Node - ROS2 node for timeline event management.

This node provides:
- Event publishing on /timeline/events topic
- Event creation via /timeline/create_event service
- Timeline querying via /timeline/query service
- Branch management
"""

from __future__ import annotations

import uuid
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

# TimeOS imports
try:
    from timeos.core.timeline import Timeline
    from timeos.msgs import ChronoStamp, TimelineEvent as CoreTimelineEvent
    TIMEOS_AVAILABLE = True
except ImportError:
    TIMEOS_AVAILABLE = False

# ROS2 message imports (generated from timeos_msgs)
from timeos_msgs.msg import TimelineEvent, ChronoStamp as RosChronoStamp

# Service imports (generated from timeos_ros)
from timeos_ros.srv import CreateEvent, QueryTimeline


class TimelineNode(Node):
    """ROS2 node for timeline event management.

    Publishes:
        /timeline/events (TimelineEvent): All timeline events

    Services:
        /timeline/create_event (CreateEvent): Create new events
        /timeline/query (QueryTimeline): Query timeline
    """

    def __init__(self):
        super().__init__("timeline_node")

        # Parameters
        self.declare_parameter("db_path", ":memory:")
        self.declare_parameter("author", "ros2_timeline")
        self.declare_parameter("publish_rate", 10.0)

        db_path = self.get_parameter("db_path").value
        self._author = self.get_parameter("author").value

        # Initialize timeline
        if TIMEOS_AVAILABLE:
            self._timeline = Timeline(db_path=db_path)
            self._timeline.set_author(self._author)
            self.get_logger().info(f"Timeline initialized with db: {db_path}")
        else:
            self._timeline = None
            self.get_logger().warn("TimeOS not available, running in stub mode")

        # QoS for reliable event delivery
        event_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            depth=100,
        )

        # Publisher for timeline events
        self._event_pub = self.create_publisher(
            TimelineEvent,
            "/timeline/events",
            event_qos,
        )

        # Services
        self._create_srv = self.create_service(
            CreateEvent,
            "/timeline/create_event",
            self._handle_create_event,
        )

        self._query_srv = self.create_service(
            QueryTimeline,
            "/timeline/query",
            self._handle_query_timeline,
        )

        # Sequence counter
        self._seq = 0

        self.get_logger().info("Timeline node started")

    def _handle_create_event(
        self,
        request: CreateEvent.Request,
        response: CreateEvent.Response,
    ) -> CreateEvent.Response:
        """Handle CreateEvent service request."""
        try:
            if not self._timeline:
                response.success = False
                response.error_message = "Timeline not available"
                return response

            # Create ChronoStamp
            stamp = ChronoStamp(
                frame_id=request.frame_id or "origin",
                t=request.t,
                t_uncertainty=request.t_uncertainty,
            )

            # Create event in timeline
            branch_id = request.branch_id or "main"
            parents = list(request.parents) if request.parents else None

            event = self._timeline.create_event(
                stamp=stamp,
                event_type=request.event_type or "observation",
                payload=bytes(request.payload) if request.payload else None,
                branch_id=branch_id,
                parents=parents,
            )

            # Publish to ROS topic
            ros_event = self._core_to_ros_event(event)
            self._event_pub.publish(ros_event)

            response.success = True
            response.event_id = event.event_id
            response.seq = event.seq

            self.get_logger().debug(f"Created event: {event.event_id}")

        except Exception as e:
            response.success = False
            response.error_message = str(e)
            self.get_logger().error(f"Failed to create event: {e}")

        return response

    def _handle_query_timeline(
        self,
        request: QueryTimeline.Request,
        response: QueryTimeline.Response,
    ) -> QueryTimeline.Response:
        """Handle QueryTimeline service request."""
        try:
            if not self._timeline:
                response.success = False
                response.error_message = "Timeline not available"
                return response

            # Query parameters
            branch_id = request.branch_id or None
            event_types = list(request.event_types) if request.event_types else None

            # Get events from timeline
            events = []
            branches_to_query = [branch_id] if branch_id else [
                b.branch_id for b in self._timeline.list_branches()
            ]

            for bid in branches_to_query:
                for event in self._timeline.slice(branch_id=bid):
                    # Filter by time range
                    if request.t_start != 0.0 and event.stamp.t < request.t_start:
                        continue
                    if request.t_end != 0.0 and event.stamp.t > request.t_end:
                        continue

                    # Filter by event type
                    if event_types and event.event_type not in event_types:
                        continue

                    events.append(event)

            # Sort by time
            events.sort(key=lambda e: e.stamp.t)
            total_count = len(events)

            # Apply pagination
            if request.offset > 0:
                events = events[request.offset:]
            if request.limit > 0:
                events = events[:request.limit]

            # Convert to ROS messages
            response.events = [
                self._core_to_ros_event(e, include_payload=request.include_payload)
                for e in events
            ]
            response.total_count = total_count
            response.success = True

        except Exception as e:
            response.success = False
            response.error_message = str(e)
            self.get_logger().error(f"Failed to query timeline: {e}")

        return response

    def _core_to_ros_event(
        self,
        event: "CoreTimelineEvent",
        include_payload: bool = True,
    ) -> TimelineEvent:
        """Convert core TimelineEvent to ROS message."""
        ros_event = TimelineEvent()
        ros_event.event_id = event.event_id
        ros_event.event_type = event.event_type
        ros_event.branch_id = event.branch_id
        ros_event.author = event.author or ""
        ros_event.seq = event.seq

        # Stamp
        ros_event.stamp.frame_id = event.stamp.frame_id
        ros_event.stamp.t = event.stamp.t
        ros_event.stamp.t_uncertainty = event.stamp.t_uncertainty or 0.0
        ros_event.stamp.clock_id = event.stamp.clock_class or ""
        ros_event.stamp.clock_class = event.stamp.clock_class or "sim"

        # Parents
        ros_event.parents = list(event.parents) if event.parents else []

        # Payload
        if include_payload and event.payload:
            ros_event.payload = list(event.payload)

        return ros_event


def main(args=None):
    """Run the timeline node."""
    rclpy.init(args=args)

    node = TimelineNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
