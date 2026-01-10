#!/usr/bin/env python3
"""Timeline Node - Manages temporal event log and timeline branches.

This node interfaces with the TimeOS core event log and timeline system,
providing ROS2 pub/sub and service interfaces.
"""

import sys
import uuid
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from builtin_interfaces.msg import Time

# Try to import timeos core
try:
    from timeos.core.event_log import EventLog
    from timeos.core.timeline import Timeline
    from timeos.msgs import TimelineEvent as CoreTimelineEvent, ChronoStamp as CoreChronoStamp
    TIMEOS_AVAILABLE = True
except ImportError:
    TIMEOS_AVAILABLE = False

# Import ROS2 message types
try:
    from timeos_msgs.msg import ChronoStamp, TimelineEvent, CausalityStatus
    from timeos_msgs.srv import CreateEvent, QueryTimeline
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class TimelineNode(Node):
    """ROS2 node for timeline management.

    Publishers:
        /timeos/events (TimelineEvent): New events as they are created
        /timeos/timeline_status (CausalityStatus): Timeline health status

    Subscribers:
        /timeos/external_events (TimelineEvent): Events from external sources

    Services:
        /timeos/create_event: Create a new event
        /timeos/query_timeline: Query events from timeline
    """

    def __init__(self):
        super().__init__('timeline_node')

        # Parameters
        self.declare_parameter('db_path', ':memory:')
        self.declare_parameter('publish_rate', 10.0)
        self.declare_parameter('default_timeline', 'main')

        db_path = self.get_parameter('db_path').value
        self.publish_rate = self.get_parameter('publish_rate').value
        self.default_timeline = self.get_parameter('default_timeline').value

        # Initialize timeos core
        self._event_log: Optional[EventLog] = None
        self._timeline: Optional[Timeline] = None

        if TIMEOS_AVAILABLE:
            try:
                self._event_log = EventLog(db_path)
                self._timeline = Timeline(self._event_log)
                self.get_logger().info(f'TimeOS core initialized with db: {db_path}')
            except Exception as e:
                self.get_logger().error(f'Failed to initialize TimeOS core: {e}')
        else:
            self.get_logger().warn('TimeOS core not available, running in stub mode')

        # Callback group for services
        self._cb_group = ReentrantCallbackGroup()

        # Publishers
        if MSGS_AVAILABLE:
            self._event_pub = self.create_publisher(
                TimelineEvent,
                '/timeos/events',
                10
            )
            self._status_pub = self.create_publisher(
                CausalityStatus,
                '/timeos/timeline_status',
                10
            )

            # Subscribers
            self._external_sub = self.create_subscription(
                TimelineEvent,
                '/timeos/external_events',
                self._on_external_event,
                10
            )

            # Services
            self._create_event_srv = self.create_service(
                CreateEvent,
                '/timeos/create_event',
                self._handle_create_event,
                callback_group=self._cb_group
            )
            self._query_srv = self.create_service(
                QueryTimeline,
                '/timeos/query_timeline',
                self._handle_query_timeline,
                callback_group=self._cb_group
            )

        # Status timer
        self._status_timer = self.create_timer(
            1.0 / self.publish_rate,
            self._publish_status
        )

        self.get_logger().info('Timeline node initialized')

    def _on_external_event(self, msg: 'TimelineEvent') -> None:
        """Handle external event from another node."""
        self.get_logger().debug(f'Received external event: {msg.event_id}')

        if self._event_log:
            # Convert ROS message to core event and log it
            try:
                self._event_log.log_event(
                    event_type=msg.event_type,
                    description=msg.description,
                    x=msg.x,
                    y=msg.y,
                    z=msg.z,
                    t=msg.t,
                    timeline_id=msg.timeline_id or self.default_timeline,
                    parent_id=msg.parent_event_id or None,
                    data=msg.data_json,
                )
            except Exception as e:
                self.get_logger().error(f'Failed to log external event: {e}')

    def _handle_create_event(
        self,
        request: 'CreateEvent.Request',
        response: 'CreateEvent.Response'
    ) -> 'CreateEvent.Response':
        """Handle create event service request."""
        try:
            event_id = str(uuid.uuid4())
            timeline_id = request.timeline_id or self.default_timeline

            if self._event_log:
                self._event_log.log_event(
                    event_type=request.event_type,
                    description=request.description,
                    x=request.x,
                    y=request.y,
                    z=request.z,
                    t=request.t,
                    timeline_id=timeline_id,
                    parent_id=request.parent_event_id or None,
                    data=request.data_json,
                    event_id=event_id,
                )

                # Calculate causality risk
                causality_risk = 0.0
                if self._timeline:
                    # TODO: Implement proper causality check
                    pass

                response.success = True
                response.event_id = event_id
                response.message = 'Event created successfully'
                response.causality_risk = causality_risk

                # Publish the event
                self._publish_event(event_id, request, timeline_id)
            else:
                response.success = True
                response.event_id = event_id
                response.message = 'Event created (stub mode)'
                response.causality_risk = 0.0

        except Exception as e:
            response.success = False
            response.message = str(e)
            self.get_logger().error(f'Failed to create event: {e}')

        return response

    def _handle_query_timeline(
        self,
        request: 'QueryTimeline.Request',
        response: 'QueryTimeline.Response'
    ) -> 'QueryTimeline.Response':
        """Handle query timeline service request."""
        try:
            if self._event_log:
                events = self._event_log.get_events(
                    timeline_id=request.timeline_id or None,
                    event_type=request.event_type_filter or None,
                    limit=request.max_results or None,
                )

                # Filter by time range
                if request.t_min > 0 or request.t_max > 0:
                    events = [
                        e for e in events
                        if (request.t_min == 0 or e.t >= request.t_min) and
                           (request.t_max == 0 or e.t <= request.t_max)
                    ]

                # Convert to ROS messages
                response.events = [self._core_to_ros_event(e) for e in events]
                response.total_count = len(events)
                response.success = True
                response.message = f'Found {len(events)} events'
            else:
                response.events = []
                response.total_count = 0
                response.success = True
                response.message = 'No events (stub mode)'

        except Exception as e:
            response.success = False
            response.message = str(e)
            self.get_logger().error(f'Failed to query timeline: {e}')

        return response

    def _publish_event(
        self,
        event_id: str,
        request: 'CreateEvent.Request',
        timeline_id: str
    ) -> None:
        """Publish a newly created event."""
        if not MSGS_AVAILABLE:
            return

        msg = TimelineEvent()
        msg.event_id = event_id
        msg.timeline_id = timeline_id
        msg.event_type = request.event_type
        msg.x = request.x
        msg.y = request.y
        msg.z = request.z
        msg.t = request.t
        msg.description = request.description
        msg.data_json = request.data_json
        msg.parent_event_id = request.parent_event_id
        msg.causality_valid = True
        msg.causality_risk = 0.0

        # Set timestamp
        msg.timestamp.stamp = self.get_clock().now().to_msg()
        msg.timestamp.tau = request.t
        msg.timestamp.coordinate_time = request.t
        msg.timestamp.gamma = 1.0
        msg.timestamp.timeline_id = timeline_id

        self._event_pub.publish(msg)

    def _publish_status(self) -> None:
        """Publish timeline status."""
        if not MSGS_AVAILABLE:
            return

        msg = CausalityStatus()
        msg.stamp = self.get_clock().now().to_msg()
        msg.status = CausalityStatus.STATUS_NOMINAL
        msg.paradox_risk = 0.0
        msg.accumulated_risk = 0.0

        if self._event_log:
            events = self._event_log.get_events(limit=1000)
            msg.active_constraints = 0
            msg.violated_constraints = 0
            msg.future_cone_clear = True
            msg.past_cone_clear = True
            msg.events_in_future_cone = 0
            msg.events_in_past_cone = len(events)

        self._status_pub.publish(msg)

    def _core_to_ros_event(self, event) -> 'TimelineEvent':
        """Convert core event to ROS message."""
        msg = TimelineEvent()
        msg.event_id = str(event.event_id) if hasattr(event, 'event_id') else ''
        msg.timeline_id = str(event.timeline_id) if hasattr(event, 'timeline_id') else ''
        msg.event_type = int(event.event_type) if hasattr(event, 'event_type') else 0
        msg.x = float(event.x) if hasattr(event, 'x') else 0.0
        msg.y = float(event.y) if hasattr(event, 'y') else 0.0
        msg.z = float(event.z) if hasattr(event, 'z') else 0.0
        msg.t = float(event.t) if hasattr(event, 't') else 0.0
        msg.description = str(event.description) if hasattr(event, 'description') else ''
        return msg


def main(args=None):
    rclpy.init(args=args)

    node = TimelineNode()

    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
