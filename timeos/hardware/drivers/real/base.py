"""Base classes for real hardware drivers.

Provides common infrastructure for all real hardware interfaces including
connection management, error handling, and thread-safe operations.
"""

from __future__ import annotations

import abc
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Hardware connection state."""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()
    RECONNECTING = auto()


class HardwareError(Exception):
    """Base exception for hardware errors."""
    pass


class ConnectionError(HardwareError):
    """Connection-related hardware error."""
    pass


class TimeoutError(HardwareError):
    """Operation timeout error."""
    pass


class ConfigurationError(HardwareError):
    """Hardware configuration error."""
    pass


@dataclass
class HardwareConnection:
    """Represents a connection to hardware.

    Attributes:
        device_id: Unique identifier for the device
        connection_string: Device-specific connection parameters
        timeout_seconds: Default operation timeout
        retry_count: Number of retries on failure
        retry_delay_seconds: Delay between retries
    """
    device_id: str
    connection_string: str = ""
    timeout_seconds: float = 5.0
    retry_count: int = 3
    retry_delay_seconds: float = 0.5

    # Runtime state
    state: ConnectionState = field(default=ConnectionState.DISCONNECTED)
    last_error: str = ""
    connected_at: float = 0.0
    last_activity: float = 0.0


T = TypeVar("T")


class RealHardwareDriver(abc.ABC, Generic[T]):
    """Abstract base class for real hardware drivers.

    Provides:
    - Connection lifecycle management
    - Thread-safe operation execution
    - Automatic reconnection
    - Error handling and logging
    - Watchdog timeout

    Type parameter T represents the hardware state type.
    """

    def __init__(
        self,
        connection: HardwareConnection,
        watchdog_timeout: float = 10.0,
    ):
        """Initialize the hardware driver.

        Args:
            connection: Hardware connection configuration
            watchdog_timeout: Seconds before watchdog triggers disconnect
        """
        self._connection = connection
        self._watchdog_timeout = watchdog_timeout

        self._lock = threading.RLock()
        self._connected = False
        self._running = False

        # Callbacks
        self._on_connect: list[Callable[[], None]] = []
        self._on_disconnect: list[Callable[[str], None]] = []
        self._on_error: list[Callable[[Exception], None]] = []
        self._on_data: list[Callable[[T], None]] = []

        # Background threads
        self._watchdog_thread: threading.Thread | None = None
        self._poll_thread: threading.Thread | None = None

        # Statistics
        self._stats = {
            "connect_count": 0,
            "disconnect_count": 0,
            "error_count": 0,
            "read_count": 0,
            "write_count": 0,
            "bytes_read": 0,
            "bytes_written": 0,
        }

    @property
    def connection(self) -> HardwareConnection:
        """Get connection configuration."""
        return self._connection

    @property
    def is_connected(self) -> bool:
        """Check if hardware is connected."""
        return self._connected and self._connection.state == ConnectionState.CONNECTED

    @property
    def stats(self) -> dict[str, int]:
        """Get driver statistics."""
        return dict(self._stats)

    # =========================================================================
    # Abstract Methods - Implement in subclasses
    # =========================================================================

    @abc.abstractmethod
    def _do_connect(self) -> bool:
        """Perform the actual hardware connection.

        Returns:
            True if connection succeeded
        """
        pass

    @abc.abstractmethod
    def _do_disconnect(self) -> None:
        """Perform the actual hardware disconnection."""
        pass

    @abc.abstractmethod
    def _do_read(self) -> T:
        """Read current state from hardware.

        Returns:
            Current hardware state
        """
        pass

    @abc.abstractmethod
    def _do_write(self, command: Any) -> bool:
        """Write command to hardware.

        Args:
            command: Hardware-specific command

        Returns:
            True if write succeeded
        """
        pass

    @abc.abstractmethod
    def _validate_connection(self) -> bool:
        """Validate that connection is still alive.

        Returns:
            True if connection is valid
        """
        pass

    # =========================================================================
    # Connection Lifecycle
    # =========================================================================

    def connect(self) -> bool:
        """Connect to hardware.

        Returns:
            True if connection succeeded
        """
        with self._lock:
            if self._connected:
                return True

            self._connection.state = ConnectionState.CONNECTING
            logger.info(f"Connecting to {self._connection.device_id}...")

            for attempt in range(self._connection.retry_count):
                try:
                    if self._do_connect():
                        self._connected = True
                        self._connection.state = ConnectionState.CONNECTED
                        self._connection.connected_at = time.time()
                        self._connection.last_activity = time.time()
                        self._stats["connect_count"] += 1

                        # Start background threads
                        self._start_background_threads()

                        # Notify callbacks
                        for cb in self._on_connect:
                            try:
                                cb()
                            except Exception as e:
                                logger.error(f"Connect callback error: {e}")

                        logger.info(f"Connected to {self._connection.device_id}")
                        return True

                except Exception as e:
                    logger.warning(
                        f"Connection attempt {attempt + 1} failed: {e}"
                    )
                    self._connection.last_error = str(e)

                if attempt < self._connection.retry_count - 1:
                    time.sleep(self._connection.retry_delay_seconds)

            self._connection.state = ConnectionState.ERROR
            logger.error(f"Failed to connect to {self._connection.device_id}")
            return False

    def disconnect(self, reason: str = "User requested") -> None:
        """Disconnect from hardware.

        Args:
            reason: Reason for disconnection
        """
        with self._lock:
            if not self._connected:
                return

            logger.info(f"Disconnecting from {self._connection.device_id}: {reason}")

            # Stop background threads
            self._stop_background_threads()

            try:
                self._do_disconnect()
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")

            self._connected = False
            self._connection.state = ConnectionState.DISCONNECTED
            self._stats["disconnect_count"] += 1

            # Notify callbacks
            for cb in self._on_disconnect:
                try:
                    cb(reason)
                except Exception as e:
                    logger.error(f"Disconnect callback error: {e}")

    def reconnect(self) -> bool:
        """Reconnect to hardware.

        Returns:
            True if reconnection succeeded
        """
        self._connection.state = ConnectionState.RECONNECTING
        self.disconnect("Reconnecting")
        time.sleep(self._connection.retry_delay_seconds)
        return self.connect()

    # =========================================================================
    # Data Operations
    # =========================================================================

    def read(self) -> T | None:
        """Read current state from hardware.

        Returns:
            Hardware state or None on error
        """
        if not self.is_connected:
            return None

        with self._lock:
            try:
                data = self._do_read()
                self._connection.last_activity = time.time()
                self._stats["read_count"] += 1

                # Notify callbacks
                for cb in self._on_data:
                    try:
                        cb(data)
                    except Exception as e:
                        logger.error(f"Data callback error: {e}")

                return data

            except Exception as e:
                self._handle_error(e)
                return None

    def write(self, command: Any) -> bool:
        """Write command to hardware.

        Args:
            command: Hardware-specific command

        Returns:
            True if write succeeded
        """
        if not self.is_connected:
            return False

        with self._lock:
            try:
                result = self._do_write(command)
                self._connection.last_activity = time.time()
                self._stats["write_count"] += 1
                return result

            except Exception as e:
                self._handle_error(e)
                return False

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_connect(self, callback: Callable[[], None]) -> None:
        """Register connect callback."""
        self._on_connect.append(callback)

    def on_disconnect(self, callback: Callable[[str], None]) -> None:
        """Register disconnect callback."""
        self._on_disconnect.append(callback)

    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """Register error callback."""
        self._on_error.append(callback)

    def on_data(self, callback: Callable[[T], None]) -> None:
        """Register data callback."""
        self._on_data.append(callback)

    # =========================================================================
    # Background Threads
    # =========================================================================

    def _start_background_threads(self) -> None:
        """Start watchdog and polling threads."""
        self._running = True

        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name=f"{self._connection.device_id}_watchdog",
            daemon=True,
        )
        self._watchdog_thread.start()

    def _stop_background_threads(self) -> None:
        """Stop background threads."""
        self._running = False

        if self._watchdog_thread and self._watchdog_thread.is_alive():
            self._watchdog_thread.join(timeout=2.0)

        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=2.0)

    def _watchdog_loop(self) -> None:
        """Watchdog thread loop."""
        while self._running:
            time.sleep(1.0)

            if not self._connected:
                continue

            # Check for timeout
            elapsed = time.time() - self._connection.last_activity
            if elapsed > self._watchdog_timeout:
                logger.warning(
                    f"Watchdog timeout on {self._connection.device_id}"
                )
                self.disconnect("Watchdog timeout")
                continue

            # Validate connection
            try:
                if not self._validate_connection():
                    logger.warning(
                        f"Connection validation failed on {self._connection.device_id}"
                    )
                    self.reconnect()
            except Exception as e:
                logger.error(f"Watchdog validation error: {e}")

    def _handle_error(self, error: Exception) -> None:
        """Handle hardware error.

        Args:
            error: The exception that occurred
        """
        self._stats["error_count"] += 1
        self._connection.last_error = str(error)
        logger.error(f"Hardware error on {self._connection.device_id}: {error}")

        # Notify callbacks
        for cb in self._on_error:
            try:
                cb(error)
            except Exception as e:
                logger.error(f"Error callback error: {e}")

        # Check if we should disconnect
        if isinstance(error, (ConnectionError, TimeoutError)):
            self._connection.state = ConnectionState.ERROR
            self.reconnect()
