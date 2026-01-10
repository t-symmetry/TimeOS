"""LabVIEW TCP/IP Bridge for TimeOS.

Provides bidirectional communication with LabVIEW applications via TCP/IP.
Supports both client mode (connect to LabVIEW) and server mode (LabVIEW connects).

Protocol:
- JSON-based command/response format
- Heartbeat for connection monitoring
- Binary data transfer for high-speed acquisition

LabVIEW side should use:
- TCP/IP functions from Data Communication palette
- JSON library for message parsing
- Shared variables for real-time data
"""

from __future__ import annotations

import json
import logging
import queue
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

from timeos.hardware.drivers.real.base import (
    RealHardwareDriver,
    HardwareConnection,
    HardwareError,
    ConnectionError,
    TimeoutError,
)

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """LabVIEW command types."""
    # System
    HEARTBEAT = "heartbeat"
    IDENTIFY = "identify"
    STATUS = "status"
    ERROR = "error"

    # Control
    SET_FIELD = "set_field"
    GET_FIELD = "get_field"
    SET_TEMPERATURE = "set_temperature"
    GET_TEMPERATURE = "get_temperature"

    # Displacement
    PREPARE_DISPLACEMENT = "prepare_displacement"
    EXECUTE_DISPLACEMENT = "execute_displacement"
    ABORT_DISPLACEMENT = "abort_displacement"

    # Safety
    ESTOP = "estop"
    RESET = "reset"
    GET_INTERLOCKS = "get_interlocks"

    # Data
    START_ACQUISITION = "start_acquisition"
    STOP_ACQUISITION = "stop_acquisition"
    GET_DATA = "get_data"

    # Custom
    CUSTOM = "custom"


@dataclass
class LabVIEWCommand:
    """Command to send to LabVIEW.

    Attributes:
        command_type: Type of command
        parameters: Command parameters
        request_id: Unique ID for matching responses
        timeout: Command timeout in seconds
    """
    command_type: CommandType
    parameters: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    timeout: float = 5.0

    def __post_init__(self):
        if not self.request_id:
            self.request_id = f"{time.time():.6f}"

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps({
            "type": self.command_type.value,
            "params": self.parameters,
            "id": self.request_id,
        })

    @classmethod
    def from_json(cls, data: str) -> "LabVIEWCommand":
        """Deserialize from JSON string."""
        obj = json.loads(data)
        return cls(
            command_type=CommandType(obj.get("type", "custom")),
            parameters=obj.get("params", {}),
            request_id=obj.get("id", ""),
        )


@dataclass
class LabVIEWResponse:
    """Response from LabVIEW.

    Attributes:
        success: Whether command succeeded
        data: Response data
        error_message: Error message if failed
        request_id: Matching request ID
        timestamp: Response timestamp
    """
    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    request_id: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps({
            "success": self.success,
            "data": self.data,
            "error": self.error_message,
            "id": self.request_id,
            "ts": self.timestamp,
        })

    @classmethod
    def from_json(cls, data: str) -> "LabVIEWResponse":
        """Deserialize from JSON string."""
        obj = json.loads(data)
        return cls(
            success=obj.get("success", True),
            data=obj.get("data", {}),
            error_message=obj.get("error", ""),
            request_id=obj.get("id", ""),
            timestamp=obj.get("ts", time.time()),
        )


@dataclass
class LabVIEWState:
    """Current state from LabVIEW."""
    connected: bool = False
    vi_name: str = ""
    vi_version: str = ""
    last_heartbeat: float = 0.0

    # Hardware state
    field_tesla: float = 0.0
    temperature_kelvin: float = 4.2
    displacement_active: bool = False
    interlocks: list[str] = field(default_factory=list)

    # Custom data
    custom_data: dict[str, Any] = field(default_factory=dict)


class LabVIEWBridge(RealHardwareDriver[LabVIEWState]):
    """TCP/IP bridge to LabVIEW applications.

    Can operate in two modes:
    - Client mode: TimeOS connects to LabVIEW server
    - Server mode: LabVIEW connects to TimeOS server

    Example usage (client mode):
        connection = HardwareConnection(
            device_id="labview_main",
            connection_string="192.168.1.100:5000",
        )
        bridge = LabVIEWBridge(connection, mode="client")
        bridge.connect()

        # Send command
        cmd = LabVIEWCommand(CommandType.GET_FIELD)
        response = bridge.send_command(cmd)
        print(f"Field: {response.data['field_tesla']} T")

    Example usage (server mode):
        connection = HardwareConnection(
            device_id="labview_server",
            connection_string="0.0.0.0:5000",
        )
        bridge = LabVIEWBridge(connection, mode="server")
        bridge.on_command(handle_labview_command)
        bridge.connect()  # Starts listening
    """

    def __init__(
        self,
        connection: HardwareConnection,
        mode: str = "client",
        heartbeat_interval: float = 1.0,
        simulation_mode: bool = False,
    ):
        """Initialize LabVIEW bridge.

        Args:
            connection: Hardware connection config
            mode: "client" or "server"
            heartbeat_interval: Seconds between heartbeats
            simulation_mode: Run without actual connection
        """
        super().__init__(connection)

        self._mode = mode
        self._heartbeat_interval = heartbeat_interval
        self._simulation_mode = simulation_mode

        # Socket
        self._socket: socket.socket | None = None
        self._client_socket: socket.socket | None = None  # For server mode

        # State
        self._state = LabVIEWState()

        # Message queues
        self._send_queue: queue.Queue[LabVIEWCommand] = queue.Queue()
        self._pending_responses: dict[str, queue.Queue[LabVIEWResponse]] = {}

        # Callbacks
        self._command_handlers: list[Callable[[LabVIEWCommand], LabVIEWResponse]] = []

        # Threads
        self._recv_thread: threading.Thread | None = None
        self._send_thread: threading.Thread | None = None
        self._heartbeat_thread: threading.Thread | None = None

    @property
    def state(self) -> LabVIEWState:
        """Get current LabVIEW state."""
        return self._state

    def on_command(
        self,
        handler: Callable[[LabVIEWCommand], LabVIEWResponse],
    ) -> None:
        """Register command handler (for server mode).

        Args:
            handler: Function to handle incoming commands
        """
        self._command_handlers.append(handler)

    # =========================================================================
    # RealHardwareDriver Implementation
    # =========================================================================

    def _do_connect(self) -> bool:
        """Establish TCP connection."""
        if self._simulation_mode:
            logger.info("LabVIEW bridge simulation mode - no connection")
            self._state.connected = True
            return True

        try:
            # Parse connection string
            parts = self._connection.connection_string.split(":")
            host = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 5000

            if self._mode == "client":
                return self._connect_client(host, port)
            else:
                return self._start_server(host, port)

        except Exception as e:
            logger.error(f"LabVIEW connection failed: {e}")
            raise ConnectionError(str(e))

    def _connect_client(self, host: str, port: int) -> bool:
        """Connect as client to LabVIEW server."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(self._connection.timeout_seconds)
        self._socket.connect((host, port))

        logger.info(f"Connected to LabVIEW at {host}:{port}")

        # Start communication threads
        self._start_comm_threads()

        # Send identify command
        response = self.send_command(LabVIEWCommand(CommandType.IDENTIFY))
        if response.success:
            self._state.vi_name = response.data.get("vi_name", "Unknown")
            self._state.vi_version = response.data.get("version", "Unknown")
            self._state.connected = True
            logger.info(f"LabVIEW VI: {self._state.vi_name} v{self._state.vi_version}")

        return True

    def _start_server(self, host: str, port: int) -> bool:
        """Start server for LabVIEW to connect."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((host, port))
        self._socket.listen(1)
        self._socket.settimeout(1.0)

        logger.info(f"LabVIEW server listening on {host}:{port}")

        # Start accept thread
        self._accept_thread = threading.Thread(
            target=self._accept_loop,
            daemon=True,
        )
        self._accept_thread.start()

        return True

    def _accept_loop(self) -> None:
        """Accept incoming connections."""
        while self._running:
            try:
                client, addr = self._socket.accept()
                logger.info(f"LabVIEW client connected from {addr}")
                self._client_socket = client
                self._state.connected = True
                self._start_comm_threads()
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"Accept error: {e}")

    def _do_disconnect(self) -> None:
        """Close TCP connection."""
        self._state.connected = False

        if self._client_socket:
            try:
                self._client_socket.close()
            except Exception:
                pass
            self._client_socket = None

        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def _do_read(self) -> LabVIEWState:
        """Read current state."""
        if self._simulation_mode:
            return self._read_simulated()

        # State is updated by recv thread
        return self._state

    def _do_write(self, command: Any) -> bool:
        """Send command to LabVIEW."""
        if isinstance(command, LabVIEWCommand):
            response = self.send_command(command)
            return response.success
        elif isinstance(command, dict):
            cmd = LabVIEWCommand(
                CommandType.CUSTOM,
                parameters=command,
            )
            response = self.send_command(cmd)
            return response.success
        return False

    def _validate_connection(self) -> bool:
        """Validate connection with heartbeat."""
        if self._simulation_mode:
            return True

        # Check last heartbeat
        if time.time() - self._state.last_heartbeat > self._heartbeat_interval * 3:
            return False

        return self._state.connected

    # =========================================================================
    # Communication
    # =========================================================================

    def send_command(
        self,
        command: LabVIEWCommand,
        wait_response: bool = True,
    ) -> LabVIEWResponse:
        """Send command and optionally wait for response.

        Args:
            command: Command to send
            wait_response: Whether to wait for response

        Returns:
            Response from LabVIEW
        """
        if self._simulation_mode:
            return self._simulate_command(command)

        # Create response queue
        response_queue: queue.Queue[LabVIEWResponse] = queue.Queue()
        self._pending_responses[command.request_id] = response_queue

        try:
            # Send command
            self._send_message(command.to_json())

            if not wait_response:
                return LabVIEWResponse(success=True, request_id=command.request_id)

            # Wait for response
            try:
                response = response_queue.get(timeout=command.timeout)
                return response
            except queue.Empty:
                return LabVIEWResponse(
                    success=False,
                    error_message="Timeout waiting for response",
                    request_id=command.request_id,
                )

        finally:
            self._pending_responses.pop(command.request_id, None)

    def _send_message(self, message: str) -> None:
        """Send message over socket.

        Args:
            message: JSON message string
        """
        sock = self._client_socket or self._socket
        if not sock:
            raise ConnectionError("Not connected")

        # Protocol: 4-byte length prefix + message
        data = message.encode("utf-8")
        length = struct.pack(">I", len(data))
        sock.sendall(length + data)

    def _recv_message(self) -> str | None:
        """Receive message from socket.

        Returns:
            JSON message string or None
        """
        sock = self._client_socket or self._socket
        if not sock:
            return None

        try:
            # Read length prefix
            length_data = self._recv_exact(sock, 4)
            if not length_data:
                return None

            length = struct.unpack(">I", length_data)[0]

            # Read message
            message_data = self._recv_exact(sock, length)
            if not message_data:
                return None

            return message_data.decode("utf-8")

        except socket.timeout:
            return None
        except Exception as e:
            logger.error(f"Recv error: {e}")
            return None

    def _recv_exact(self, sock: socket.socket, n: int) -> bytes | None:
        """Receive exactly n bytes."""
        data = b""
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _start_comm_threads(self) -> None:
        """Start communication threads."""
        self._recv_thread = threading.Thread(
            target=self._recv_loop,
            daemon=True,
        )
        self._recv_thread.start()

        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _recv_loop(self) -> None:
        """Receive loop thread."""
        while self._running and self._state.connected:
            message = self._recv_message()
            if not message:
                time.sleep(0.01)
                continue

            try:
                self._handle_message(message)
            except Exception as e:
                logger.error(f"Message handling error: {e}")

    def _handle_message(self, message: str) -> None:
        """Handle received message.

        Args:
            message: JSON message string
        """
        obj = json.loads(message)

        # Check if it's a response
        if "success" in obj:
            response = LabVIEWResponse.from_json(message)
            response_queue = self._pending_responses.get(response.request_id)
            if response_queue:
                response_queue.put(response)
            return

        # It's a command (server mode)
        command = LabVIEWCommand.from_json(message)

        # Handle heartbeat internally
        if command.command_type == CommandType.HEARTBEAT:
            self._state.last_heartbeat = time.time()
            self._send_response(LabVIEWResponse(
                success=True,
                request_id=command.request_id,
            ))
            return

        # Dispatch to handlers
        for handler in self._command_handlers:
            try:
                response = handler(command)
                self._send_response(response)
                return
            except Exception as e:
                logger.error(f"Command handler error: {e}")

        # No handler found
        self._send_response(LabVIEWResponse(
            success=False,
            error_message=f"Unknown command: {command.command_type.value}",
            request_id=command.request_id,
        ))

    def _send_response(self, response: LabVIEWResponse) -> None:
        """Send response to LabVIEW.

        Args:
            response: Response to send
        """
        try:
            self._send_message(response.to_json())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    def _heartbeat_loop(self) -> None:
        """Heartbeat loop thread."""
        while self._running and self._state.connected:
            time.sleep(self._heartbeat_interval)

            if self._mode == "client":
                # Send heartbeat
                try:
                    response = self.send_command(
                        LabVIEWCommand(CommandType.HEARTBEAT),
                        wait_response=True,
                    )
                    if response.success:
                        self._state.last_heartbeat = time.time()
                except Exception as e:
                    logger.warning(f"Heartbeat failed: {e}")

    # =========================================================================
    # Simulation
    # =========================================================================

    def _read_simulated(self) -> LabVIEWState:
        """Generate simulated state."""
        import math
        import random

        t = time.time()

        self._state.field_tesla = 5.0 + 0.1 * math.sin(t * 0.1)
        self._state.temperature_kelvin = 4.2 + 0.05 * random.random()
        self._state.last_heartbeat = t

        return self._state

    def _simulate_command(self, command: LabVIEWCommand) -> LabVIEWResponse:
        """Simulate command response.

        Args:
            command: Command to simulate
        """
        if command.command_type == CommandType.IDENTIFY:
            return LabVIEWResponse(
                success=True,
                data={
                    "vi_name": "TimeOS_Simulation.vi",
                    "version": "1.0.0",
                },
                request_id=command.request_id,
            )

        elif command.command_type == CommandType.GET_FIELD:
            return LabVIEWResponse(
                success=True,
                data={"field_tesla": self._state.field_tesla},
                request_id=command.request_id,
            )

        elif command.command_type == CommandType.SET_FIELD:
            target = command.parameters.get("target_tesla", 0.0)
            self._state.field_tesla = target
            return LabVIEWResponse(
                success=True,
                data={"accepted": True, "target_tesla": target},
                request_id=command.request_id,
            )

        elif command.command_type == CommandType.GET_TEMPERATURE:
            return LabVIEWResponse(
                success=True,
                data={"temperature_kelvin": self._state.temperature_kelvin},
                request_id=command.request_id,
            )

        elif command.command_type == CommandType.GET_INTERLOCKS:
            return LabVIEWResponse(
                success=True,
                data={"interlocks": [], "safe": True},
                request_id=command.request_id,
            )

        elif command.command_type == CommandType.HEARTBEAT:
            self._state.last_heartbeat = time.time()
            return LabVIEWResponse(
                success=True,
                request_id=command.request_id,
            )

        else:
            return LabVIEWResponse(
                success=True,
                data={"simulated": True},
                request_id=command.request_id,
            )
