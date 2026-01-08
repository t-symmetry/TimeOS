"""ROS-Compatible Interfaces - Abstraction layer for ROS2 migration.

This module provides abstractions that map cleanly to ROS2 concepts:
- Message types -> ROS2 msg files
- Publishers/Subscribers -> ROS2 topics
- Services -> ROS2 services
- Parameters -> ROS2 parameters

The standalone implementation uses Python callbacks and queues.
When migrating to ROS2, replace these with actual ROS2 primitives.
"""

from __future__ import annotations

import threading
import queue
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field as dataclass_field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Generic, TypeVar
import json


# =============================================================================
# Message Types (map to ROS2 msg files)
# =============================================================================

@dataclass
class Header:
    """Standard message header (mirrors std_msgs/Header).

    In ROS2, this would be:
    ```
    # std_msgs/Header.msg
    builtin_interfaces/Time stamp
    string frame_id
    ```
    """
    stamp: float = 0.0  # Unix timestamp (ROS2 uses builtin_interfaces/Time)
    frame_id: str = ""
    seq: int = 0  # Sequence number

    @classmethod
    def now(cls, frame_id: str = "") -> Header:
        return cls(stamp=time.time(), frame_id=frame_id)


@dataclass
class FieldStatus:
    """Field generator status message.

    ROS2 equivalent: timeos_msgs/FieldStatus.msg
    """
    header: Header = dataclass_field(default_factory=Header)
    active: bool = False
    field_tesla: float = 0.0
    target_tesla: float = 0.0
    temperature_kelvin: float = 4.2
    quench_risk: float = 0.0
    power_watts: float = 0.0
    stability: float = 1.0
    ramp_state: str = "idle"  # idle, ramping_up, ramping_down, holding
    fault: str = ""  # Empty if no fault


@dataclass
class TDUStatus:
    """TDU status message.

    ROS2 equivalent: timeos_msgs/TDUStatus.msg
    """
    header: Header = dataclass_field(default_factory=Header)
    state: str = "idle"  # idle, preparing, displacing, complete, etc.
    phase: str = "idle"  # Detailed phase
    progress: float = 0.0  # 0.0 to 1.0
    sim_time: float = 0.0  # Current simulated time position
    energy_consumed_joules: float = 0.0
    fault: str = ""


@dataclass
class ThermalStatus:
    """Thermal system status message.

    ROS2 equivalent: timeos_msgs/ThermalStatus.msg
    """
    header: Header = dataclass_field(default_factory=Header)
    temperature_kelvin: float = 4.2
    state: str = "cold"  # cold, warming, critical, quench, recovery
    quench_risk: float = 0.0
    cooling_load_watts: float = 0.0
    cooling_headroom_watts: float = 50.0
    time_to_quench_seconds: float | None = None


@dataclass
class SensorReading:
    """Generic sensor reading message.

    ROS2 equivalent: timeos_msgs/SensorReading.msg
    """
    header: Header = dataclass_field(default_factory=Header)
    sensor_id: str = ""
    value: float = 0.0
    unit: str = ""
    status: str = "ok"  # ok, degraded, fault, offline


@dataclass
class SafetyStatus:
    """Safety system status message.

    ROS2 equivalent: timeos_msgs/SafetyStatus.msg
    """
    header: Header = dataclass_field(default_factory=Header)
    level: str = "nominal"  # nominal, warning, critical, emergency
    interlocks_engaged: list[str] = dataclass_field(default_factory=list)
    active_faults: list[str] = dataclass_field(default_factory=list)
    estop_active: bool = False


@dataclass
class DisplacementRequest:
    """Request to perform displacement.

    ROS2 equivalent: timeos_msgs/srv/Displace.srv (request part)
    """
    target_time: float = 0.0
    frame_id: str = "origin"
    mode: str = "backward"  # forward, backward, lateral
    energy_budget_joules: float = 1e12
    max_duration_seconds: float = 60.0


@dataclass
class DisplacementResponse:
    """Response from displacement operation.

    ROS2 equivalent: timeos_msgs/srv/Displace.srv (response part)
    """
    success: bool = False
    actual_displacement: float = 0.0
    origin_time: float = 0.0
    destination_time: float = 0.0
    energy_consumed_joules: float = 0.0
    duration_seconds: float = 0.0
    error_message: str = ""


@dataclass
class SystemStatus:
    """Complete system status (aggregated).

    ROS2 equivalent: timeos_msgs/SystemStatus.msg
    """
    header: Header = dataclass_field(default_factory=Header)
    initialized: bool = False
    current_time: float = 0.0
    anchor_time: float | None = None
    frame_id: str = "origin"

    # Module statuses
    field_gen: FieldStatus = dataclass_field(default_factory=FieldStatus)
    tdu: TDUStatus = dataclass_field(default_factory=TDUStatus)
    thermal: ThermalStatus = dataclass_field(default_factory=ThermalStatus)
    safety: SafetyStatus = dataclass_field(default_factory=SafetyStatus)


# =============================================================================
# Pub/Sub Abstraction (maps to ROS2 topics)
# =============================================================================

T = TypeVar('T')


class Publisher(Generic[T]):
    """Message publisher (maps to ROS2 Publisher).

    In ROS2:
    ```python
    self.publisher = self.create_publisher(FieldStatus, 'field_status', 10)
    self.publisher.publish(msg)
    ```
    """

    def __init__(self, topic: str, msg_type: type[T], queue_size: int = 10):
        self._topic = topic
        self._msg_type = msg_type
        self._subscribers: list[Callable[[T], None]] = []
        self._queue: queue.Queue[T] = queue.Queue(maxsize=queue_size)
        self._lock = threading.Lock()

    @property
    def topic(self) -> str:
        return self._topic

    def publish(self, msg: T) -> None:
        """Publish a message to all subscribers."""
        with self._lock:
            for callback in self._subscribers:
                try:
                    callback(msg)
                except Exception:
                    pass  # Don't let subscriber errors affect publisher

    def _add_subscriber(self, callback: Callable[[T], None]) -> None:
        """Internal: add a subscriber callback."""
        with self._lock:
            self._subscribers.append(callback)

    def _remove_subscriber(self, callback: Callable[[T], None]) -> None:
        """Internal: remove a subscriber callback."""
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)


class Subscriber(Generic[T]):
    """Message subscriber (maps to ROS2 Subscription).

    In ROS2:
    ```python
    self.subscription = self.create_subscription(
        FieldStatus, 'field_status', self.callback, 10
    )
    ```
    """

    def __init__(
        self,
        publisher: Publisher[T],
        callback: Callable[[T], None],
    ):
        self._publisher = publisher
        self._callback = callback
        self._publisher._add_subscriber(callback)

    def unsubscribe(self) -> None:
        """Stop receiving messages."""
        self._publisher._remove_subscriber(self._callback)


class MessageBroker:
    """Central message broker for pub/sub (replaced by ROS2 DDS in ROS mode).

    This provides a simple way to create publishers and subscribers
    without direct coupling between modules.
    """

    def __init__(self):
        self._publishers: dict[str, Publisher] = {}
        self._lock = threading.Lock()

    def create_publisher(self, topic: str, msg_type: type[T], queue_size: int = 10) -> Publisher[T]:
        """Create or get a publisher for a topic."""
        with self._lock:
            if topic not in self._publishers:
                self._publishers[topic] = Publisher(topic, msg_type, queue_size)
            return self._publishers[topic]

    def create_subscription(
        self,
        topic: str,
        msg_type: type[T],
        callback: Callable[[T], None],
    ) -> Subscriber[T]:
        """Subscribe to a topic."""
        with self._lock:
            if topic not in self._publishers:
                self._publishers[topic] = Publisher(topic, msg_type)
            return Subscriber(self._publishers[topic], callback)

    def get_topics(self) -> list[str]:
        """List all active topics."""
        return list(self._publishers.keys())


# =============================================================================
# Service Abstraction (maps to ROS2 services)
# =============================================================================

RequestT = TypeVar('RequestT')
ResponseT = TypeVar('ResponseT')


class Service(Generic[RequestT, ResponseT]):
    """Service server (maps to ROS2 Service).

    In ROS2:
    ```python
    self.srv = self.create_service(Displace, 'displace', self.handle_displace)
    ```
    """

    def __init__(
        self,
        name: str,
        request_type: type[RequestT],
        response_type: type[ResponseT],
        handler: Callable[[RequestT], ResponseT],
    ):
        self._name = name
        self._request_type = request_type
        self._response_type = response_type
        self._handler = handler

    @property
    def name(self) -> str:
        return self._name

    def call(self, request: RequestT) -> ResponseT:
        """Call the service (synchronous)."""
        return self._handler(request)


class ServiceClient(Generic[RequestT, ResponseT]):
    """Service client (maps to ROS2 Client).

    In ROS2:
    ```python
    self.client = self.create_client(Displace, 'displace')
    future = self.client.call_async(request)
    ```
    """

    def __init__(self, service: Service[RequestT, ResponseT]):
        self._service = service

    def call(self, request: RequestT) -> ResponseT:
        """Call the service (synchronous)."""
        return self._service.call(request)

    def call_async(self, request: RequestT) -> threading.Thread:
        """Call the service asynchronously (returns thread with result)."""
        result_holder = {'response': None, 'error': None}

        def worker():
            try:
                result_holder['response'] = self._service.call(request)
            except Exception as e:
                result_holder['error'] = e

        thread = threading.Thread(target=worker, daemon=True)
        thread.result_holder = result_holder  # type: ignore
        thread.start()
        return thread


class ServiceRegistry:
    """Registry for services (replaced by ROS2 service discovery)."""

    def __init__(self):
        self._services: dict[str, Service] = {}
        self._lock = threading.Lock()

    def register_service(self, service: Service) -> None:
        """Register a service."""
        with self._lock:
            self._services[service.name] = service

    def get_service(self, name: str) -> Service | None:
        """Get a service by name."""
        return self._services.get(name)

    def create_client(
        self,
        name: str,
        request_type: type[RequestT],
        response_type: type[ResponseT],
    ) -> ServiceClient[RequestT, ResponseT] | None:
        """Create a client for a service."""
        service = self._services.get(name)
        if service:
            return ServiceClient(service)
        return None

    def list_services(self) -> list[str]:
        """List all registered services."""
        return list(self._services.keys())


# =============================================================================
# Parameter Server (maps to ROS2 parameters)
# =============================================================================

class ParameterServer:
    """Parameter server (maps to ROS2 parameter server).

    In ROS2, parameters are per-node:
    ```python
    self.declare_parameter('max_field_tesla', 10.0)
    value = self.get_parameter('max_field_tesla').value
    ```
    """

    def __init__(self):
        self._params: dict[str, Any] = {}
        self._callbacks: dict[str, list[Callable[[str, Any], None]]] = {}
        self._lock = threading.Lock()

    def set(self, name: str, value: Any) -> None:
        """Set a parameter value."""
        with self._lock:
            old_value = self._params.get(name)
            self._params[name] = value

            # Notify callbacks
            if name in self._callbacks:
                for callback in self._callbacks[name]:
                    try:
                        callback(name, value)
                    except Exception:
                        pass

    def get(self, name: str, default: Any = None) -> Any:
        """Get a parameter value."""
        return self._params.get(name, default)

    def declare(self, name: str, default: Any) -> None:
        """Declare a parameter with default value."""
        if name not in self._params:
            self._params[name] = default

    def add_callback(self, name: str, callback: Callable[[str, Any], None]) -> None:
        """Add callback for parameter changes."""
        with self._lock:
            if name not in self._callbacks:
                self._callbacks[name] = []
            self._callbacks[name].append(callback)

    def get_all(self) -> dict[str, Any]:
        """Get all parameters."""
        return dict(self._params)

    def load_from_dict(self, params: dict[str, Any]) -> None:
        """Load parameters from dictionary."""
        for name, value in params.items():
            self.set(name, value)

    def to_dict(self) -> dict[str, Any]:
        """Export parameters to dictionary."""
        return dict(self._params)


# =============================================================================
# Node Base Class (maps to ROS2 Node)
# =============================================================================

class NodeBase:
    """Base class for ROS-compatible nodes.

    In ROS2, this would extend rclpy.node.Node:
    ```python
    class FieldGeneratorNode(Node):
        def __init__(self):
            super().__init__('field_generator_node')
    ```
    """

    def __init__(
        self,
        name: str,
        broker: MessageBroker | None = None,
        services: ServiceRegistry | None = None,
        params: ParameterServer | None = None,
    ):
        self._name = name
        self._broker = broker or MessageBroker()
        self._services = services or ServiceRegistry()
        self._params = params or ParameterServer()
        self._publishers: list[Publisher] = []
        self._subscriptions: list[Subscriber] = []
        self._timers: list[threading.Timer] = []
        self._running = False

    @property
    def name(self) -> str:
        return self._name

    def create_publisher(self, msg_type: type[T], topic: str, queue_size: int = 10) -> Publisher[T]:
        """Create a publisher."""
        pub = self._broker.create_publisher(f"{self._name}/{topic}", msg_type, queue_size)
        self._publishers.append(pub)
        return pub

    def create_subscription(
        self,
        msg_type: type[T],
        topic: str,
        callback: Callable[[T], None],
    ) -> Subscriber[T]:
        """Create a subscription."""
        sub = self._broker.create_subscription(topic, msg_type, callback)
        self._subscriptions.append(sub)
        return sub

    def create_service(
        self,
        srv_type: tuple[type[RequestT], type[ResponseT]],
        name: str,
        handler: Callable[[RequestT], ResponseT],
    ) -> Service[RequestT, ResponseT]:
        """Create a service server."""
        request_type, response_type = srv_type
        service = Service(f"{self._name}/{name}", request_type, response_type, handler)
        self._services.register_service(service)
        return service

    def create_client(
        self,
        srv_type: tuple[type[RequestT], type[ResponseT]],
        name: str,
    ) -> ServiceClient[RequestT, ResponseT] | None:
        """Create a service client."""
        request_type, response_type = srv_type
        return self._services.create_client(name, request_type, response_type)

    def declare_parameter(self, name: str, default: Any) -> None:
        """Declare a parameter."""
        self._params.declare(f"{self._name}.{name}", default)

    def get_parameter(self, name: str) -> Any:
        """Get a parameter value."""
        return self._params.get(f"{self._name}.{name}")

    def set_parameter(self, name: str, value: Any) -> None:
        """Set a parameter value."""
        self._params.set(f"{self._name}.{name}", value)

    def create_timer(self, period: float, callback: Callable[[], None]) -> threading.Timer:
        """Create a periodic timer."""
        def timer_callback():
            if self._running:
                callback()
                # Reschedule
                timer = threading.Timer(period, timer_callback)
                timer.daemon = True
                timer.start()
                self._timers.append(timer)

        timer = threading.Timer(period, timer_callback)
        timer.daemon = True
        self._timers.append(timer)
        return timer

    def start(self) -> None:
        """Start the node (start timers, etc.)."""
        self._running = True
        for timer in self._timers:
            if not timer.is_alive():
                timer.start()

    def stop(self) -> None:
        """Stop the node."""
        self._running = False
        for timer in self._timers:
            timer.cancel()
        for sub in self._subscriptions:
            sub.unsubscribe()

    def get_logger(self):
        """Get logger (maps to self.get_logger() in ROS2)."""
        return NodeLogger(self._name)


class NodeLogger:
    """Simple logger that mimics ROS2 logger interface."""

    def __init__(self, name: str):
        self._name = name

    def info(self, msg: str) -> None:
        print(f"[INFO] [{self._name}] {msg}")

    def warn(self, msg: str) -> None:
        print(f"[WARN] [{self._name}] {msg}")

    def error(self, msg: str) -> None:
        print(f"[ERROR] [{self._name}] {msg}")

    def debug(self, msg: str) -> None:
        print(f"[DEBUG] [{self._name}] {msg}")
