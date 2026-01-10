"""Real-time data logging for TimeOS.

Provides high-performance data logging with:
- Ring buffers for continuous acquisition
- HDF5 file storage for large datasets
- CSV export for analysis
- Real-time streaming to subscribers
- Configurable decimation and filtering
"""

from __future__ import annotations

import csv
import logging
import os
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Iterator

logger = logging.getLogger(__name__)

# Try to import h5py for HDF5 support
try:
    import h5py
    HDF5_AVAILABLE = True
except ImportError:
    HDF5_AVAILABLE = False
    logger.info("h5py not available - HDF5 logging disabled")

# Try to import numpy for efficient arrays
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None


class LogFormat(Enum):
    """Data log file formats."""
    CSV = auto()
    HDF5 = auto()
    BINARY = auto()


@dataclass
class LogChannel:
    """Configuration for a data logging channel.

    Attributes:
        name: Channel name
        units: Engineering units
        dtype: Data type ("float64", "float32", "int32", etc.)
        min_value: Expected minimum (for scaling)
        max_value: Expected maximum (for scaling)
        decimation: Log every Nth sample (1 = all)
        description: Channel description
    """
    name: str
    units: str = ""
    dtype: str = "float64"
    min_value: float = -1e9
    max_value: float = 1e9
    decimation: int = 1
    description: str = ""

    # Runtime
    sample_count: int = 0
    last_value: float = 0.0
    last_timestamp: float = 0.0


@dataclass
class LogSession:
    """A data logging session.

    Attributes:
        session_id: Unique session identifier
        start_time: Session start timestamp
        channels: Channels being logged
        file_path: Path to log file
        format: File format
        metadata: Session metadata
    """
    session_id: str
    start_time: float = 0.0
    end_time: float = 0.0
    channels: list[LogChannel] = field(default_factory=list)
    file_path: str = ""
    format: LogFormat = LogFormat.CSV
    metadata: dict[str, Any] = field(default_factory=dict)

    # Statistics
    total_samples: int = 0
    bytes_written: int = 0
    errors: int = 0

    def __post_init__(self):
        if not self.start_time:
            self.start_time = time.time()
        if not self.session_id:
            self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")


@dataclass
class DataPoint:
    """A single data point."""
    channel: str
    value: float
    timestamp: float
    quality: int = 0  # 0 = good, >0 = quality code


class DataLogger:
    """High-performance data logger.

    Features:
    - Ring buffer for real-time viewing
    - Background file writing
    - Multiple output formats
    - Data streaming callbacks
    - Automatic session management

    Example usage:
        logger = DataLogger(
            base_path="/data/timeos",
            buffer_size=10000,
        )

        # Configure channels
        logger.add_channel(LogChannel(
            name="field",
            units="T",
            decimation=10,
        ))

        # Start session
        session = logger.start_session(
            format=LogFormat.HDF5,
            metadata={"experiment": "test_001"},
        )

        # Log data
        logger.log("field", 5.0)

        # Stop session
        logger.stop_session()
    """

    def __init__(
        self,
        base_path: str = ".",
        buffer_size: int = 10000,
        flush_interval: float = 1.0,
    ):
        """Initialize data logger.

        Args:
            base_path: Base directory for log files
            buffer_size: Ring buffer size per channel
            flush_interval: Seconds between file flushes
        """
        self._base_path = Path(base_path)
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval

        # Ensure directory exists
        self._base_path.mkdir(parents=True, exist_ok=True)

        # Channels
        self._channels: dict[str, LogChannel] = {}

        # Ring buffers (channel -> deque of (timestamp, value))
        self._buffers: dict[str, deque] = {}

        # Current session
        self._session: LogSession | None = None
        self._session_lock = threading.Lock()

        # Write queue and thread
        self._write_queue: queue.Queue[DataPoint] = queue.Queue()
        self._write_thread: threading.Thread | None = None
        self._running = False

        # File handles
        self._csv_file = None
        self._csv_writer = None
        self._hdf5_file = None
        self._hdf5_datasets: dict[str, Any] = {}

        # Callbacks
        self._data_callbacks: list[Callable[[DataPoint], None]] = []

    def add_channel(self, channel: LogChannel) -> None:
        """Add a logging channel.

        Args:
            channel: Channel configuration
        """
        self._channels[channel.name] = channel
        self._buffers[channel.name] = deque(maxlen=self._buffer_size)
        logger.debug(f"Added channel: {channel.name}")

    def remove_channel(self, name: str) -> None:
        """Remove a logging channel.

        Args:
            name: Channel name
        """
        self._channels.pop(name, None)
        self._buffers.pop(name, None)

    def get_channel(self, name: str) -> LogChannel | None:
        """Get channel by name."""
        return self._channels.get(name)

    @property
    def channels(self) -> list[LogChannel]:
        """Get all channels."""
        return list(self._channels.values())

    @property
    def session(self) -> LogSession | None:
        """Get current session."""
        return self._session

    def on_data(self, callback: Callable[[DataPoint], None]) -> None:
        """Register data callback.

        Args:
            callback: Function called for each data point
        """
        self._data_callbacks.append(callback)

    # =========================================================================
    # Session Management
    # =========================================================================

    def start_session(
        self,
        session_id: str = "",
        format: LogFormat = LogFormat.CSV,
        metadata: dict[str, Any] | None = None,
    ) -> LogSession:
        """Start a new logging session.

        Args:
            session_id: Session identifier (auto-generated if empty)
            format: Output file format
            metadata: Session metadata

        Returns:
            The created session
        """
        with self._session_lock:
            if self._session:
                self.stop_session()

            # Create session
            self._session = LogSession(
                session_id=session_id,
                channels=list(self._channels.values()),
                format=format,
                metadata=metadata or {},
            )

            # Generate file path
            ext = {
                LogFormat.CSV: ".csv",
                LogFormat.HDF5: ".h5",
                LogFormat.BINARY: ".bin",
            }[format]

            self._session.file_path = str(
                self._base_path / f"timeos_{self._session.session_id}{ext}"
            )

            # Open file
            self._open_file(format)

            # Start write thread
            self._running = True
            self._write_thread = threading.Thread(
                target=self._write_loop,
                daemon=True,
            )
            self._write_thread.start()

            logger.info(f"Started session: {self._session.session_id}")
            return self._session

    def stop_session(self) -> LogSession | None:
        """Stop the current logging session.

        Returns:
            The completed session or None
        """
        with self._session_lock:
            if not self._session:
                return None

            self._session.end_time = time.time()

            # Stop write thread
            self._running = False
            if self._write_thread:
                self._write_thread.join(timeout=2.0)
                self._write_thread = None

            # Flush and close file
            self._close_file()

            session = self._session
            self._session = None

            logger.info(
                f"Stopped session: {session.session_id}, "
                f"{session.total_samples} samples, "
                f"{session.bytes_written} bytes"
            )
            return session

    # =========================================================================
    # Data Logging
    # =========================================================================

    def log(
        self,
        channel: str,
        value: float,
        timestamp: float | None = None,
        quality: int = 0,
    ) -> None:
        """Log a data point.

        Args:
            channel: Channel name
            value: Data value
            timestamp: Timestamp (current time if None)
            quality: Quality code (0 = good)
        """
        if channel not in self._channels:
            return

        ch = self._channels[channel]
        ts = timestamp or time.time()

        # Apply decimation
        ch.sample_count += 1
        if ch.sample_count % ch.decimation != 0:
            return

        # Create data point
        point = DataPoint(
            channel=channel,
            value=value,
            timestamp=ts,
            quality=quality,
        )

        # Update channel state
        ch.last_value = value
        ch.last_timestamp = ts

        # Add to ring buffer
        self._buffers[channel].append((ts, value))

        # Queue for file writing
        if self._session:
            self._write_queue.put(point)

        # Notify callbacks
        for cb in self._data_callbacks:
            try:
                cb(point)
            except Exception as e:
                logger.error(f"Data callback error: {e}")

    def log_dict(
        self,
        data: dict[str, float],
        timestamp: float | None = None,
    ) -> None:
        """Log multiple channels at once.

        Args:
            data: Channel name -> value mapping
            timestamp: Common timestamp
        """
        ts = timestamp or time.time()
        for channel, value in data.items():
            self.log(channel, value, ts)

    # =========================================================================
    # Data Access
    # =========================================================================

    def get_buffer(
        self,
        channel: str,
        count: int | None = None,
    ) -> list[tuple[float, float]]:
        """Get recent data from ring buffer.

        Args:
            channel: Channel name
            count: Number of points (None = all)

        Returns:
            List of (timestamp, value) tuples
        """
        if channel not in self._buffers:
            return []

        buffer = self._buffers[channel]
        if count is None:
            return list(buffer)
        return list(buffer)[-count:]

    def get_latest(self, channel: str) -> tuple[float, float] | None:
        """Get latest value for channel.

        Args:
            channel: Channel name

        Returns:
            (timestamp, value) or None
        """
        if channel not in self._buffers:
            return None

        buffer = self._buffers[channel]
        if not buffer:
            return None

        return buffer[-1]

    def get_statistics(self, channel: str) -> dict[str, float]:
        """Get statistics for channel buffer.

        Args:
            channel: Channel name

        Returns:
            Dictionary with min, max, mean, std, count
        """
        buffer = self._buffers.get(channel, [])
        if not buffer:
            return {"min": 0, "max": 0, "mean": 0, "std": 0, "count": 0}

        values = [v for _, v in buffer]

        if NUMPY_AVAILABLE:
            arr = np.array(values)
            return {
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr)),
                "count": len(arr),
            }
        else:
            n = len(values)
            mean = sum(values) / n
            variance = sum((v - mean) ** 2 for v in values) / n
            return {
                "min": min(values),
                "max": max(values),
                "mean": mean,
                "std": variance ** 0.5,
                "count": n,
            }

    # =========================================================================
    # File I/O
    # =========================================================================

    def _open_file(self, format: LogFormat) -> None:
        """Open log file."""
        if format == LogFormat.CSV:
            self._csv_file = open(self._session.file_path, "w", newline="")
            self._csv_writer = csv.writer(self._csv_file)

            # Write header
            header = ["timestamp"] + [ch.name for ch in self._channels.values()]
            self._csv_writer.writerow(header)

        elif format == LogFormat.HDF5:
            if not HDF5_AVAILABLE:
                logger.error("HDF5 not available, falling back to CSV")
                self._session.format = LogFormat.CSV
                self._open_file(LogFormat.CSV)
                return

            self._hdf5_file = h5py.File(self._session.file_path, "w")

            # Create datasets for each channel
            for ch in self._channels.values():
                dtype = getattr(np, ch.dtype, np.float64)
                ds = self._hdf5_file.create_dataset(
                    ch.name,
                    shape=(0,),
                    maxshape=(None,),
                    dtype=dtype,
                    chunks=(1000,),
                )
                ds.attrs["units"] = ch.units
                ds.attrs["description"] = ch.description
                self._hdf5_datasets[ch.name] = ds

            # Timestamps dataset
            self._hdf5_file.create_dataset(
                "timestamps",
                shape=(0,),
                maxshape=(None,),
                dtype=np.float64,
                chunks=(1000,),
            )

            # Metadata
            for key, value in self._session.metadata.items():
                self._hdf5_file.attrs[key] = str(value)

    def _close_file(self) -> None:
        """Close log file."""
        if self._csv_file:
            self._csv_file.close()
            self._csv_file = None
            self._csv_writer = None

        if self._hdf5_file:
            self._hdf5_file.close()
            self._hdf5_file = None
            self._hdf5_datasets.clear()

    def _write_loop(self) -> None:
        """Background write thread."""
        batch: list[DataPoint] = []
        last_flush = time.time()

        while self._running or not self._write_queue.empty():
            try:
                point = self._write_queue.get(timeout=0.1)
                batch.append(point)
            except queue.Empty:
                pass

            # Flush periodically or when batch is large
            now = time.time()
            if batch and (
                len(batch) >= 100 or
                now - last_flush >= self._flush_interval
            ):
                self._write_batch(batch)
                batch.clear()
                last_flush = now

        # Final flush
        if batch:
            self._write_batch(batch)

    def _write_batch(self, batch: list[DataPoint]) -> None:
        """Write a batch of data points."""
        if not self._session:
            return

        try:
            if self._session.format == LogFormat.CSV:
                self._write_csv_batch(batch)
            elif self._session.format == LogFormat.HDF5:
                self._write_hdf5_batch(batch)

            self._session.total_samples += len(batch)

        except Exception as e:
            logger.error(f"Write error: {e}")
            self._session.errors += 1

    def _write_csv_batch(self, batch: list[DataPoint]) -> None:
        """Write batch to CSV."""
        if not self._csv_writer:
            return

        # Group by timestamp
        rows: dict[float, dict[str, float]] = {}
        for point in batch:
            if point.timestamp not in rows:
                rows[point.timestamp] = {}
            rows[point.timestamp][point.channel] = point.value

        # Write rows
        for ts in sorted(rows.keys()):
            row = [ts]
            for ch in self._channels.values():
                row.append(rows[ts].get(ch.name, ""))
            self._csv_writer.writerow(row)

        self._csv_file.flush()
        self._session.bytes_written = os.path.getsize(self._session.file_path)

    def _write_hdf5_batch(self, batch: list[DataPoint]) -> None:
        """Write batch to HDF5."""
        if not self._hdf5_file:
            return

        # Group by channel
        channel_data: dict[str, list[tuple[float, float]]] = {}
        for point in batch:
            if point.channel not in channel_data:
                channel_data[point.channel] = []
            channel_data[point.channel].append((point.timestamp, point.value))

        # Append to datasets
        for channel, data in channel_data.items():
            if channel not in self._hdf5_datasets:
                continue

            ds = self._hdf5_datasets[channel]
            values = [v for _, v in data]

            # Resize and append
            old_size = ds.shape[0]
            new_size = old_size + len(values)
            ds.resize((new_size,))
            ds[old_size:new_size] = values

        self._hdf5_file.flush()
        self._session.bytes_written = os.path.getsize(self._session.file_path)

    # =========================================================================
    # Export
    # =========================================================================

    def export_csv(
        self,
        output_path: str,
        channels: list[str] | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> int:
        """Export buffer data to CSV.

        Args:
            output_path: Output file path
            channels: Channels to export (None = all)
            start_time: Start timestamp filter
            end_time: End timestamp filter

        Returns:
            Number of rows exported
        """
        channels = channels or list(self._channels.keys())

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(["timestamp"] + channels)

            # Get data from buffers
            all_data: list[tuple[float, dict[str, float]]] = []

            for channel in channels:
                buffer = self._buffers.get(channel, [])
                for ts, value in buffer:
                    if start_time and ts < start_time:
                        continue
                    if end_time and ts > end_time:
                        continue

                    # Find or create row
                    row_data = next(
                        (r for t, r in all_data if abs(t - ts) < 0.001),
                        None
                    )
                    if row_data is None:
                        row_data = {}
                        all_data.append((ts, row_data))
                    row_data[channel] = value

            # Sort and write
            all_data.sort(key=lambda x: x[0])
            for ts, row_data in all_data:
                row = [ts] + [row_data.get(ch, "") for ch in channels]
                writer.writerow(row)

            return len(all_data)
