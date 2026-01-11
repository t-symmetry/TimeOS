"""IEEE 1588 PTP (Precision Time Protocol) clock source.

Provides integration with linuxptp for hardware timestamping
and sub-microsecond synchronization.

PTP provides much better accuracy than NTP:
- NTP: ~1-10ms typical
- PTP: ~100ns-1µs with hardware timestamping

Requires: linuxptp (ptp4l, pmc commands)
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any

from timeos.clocks.base import (
    ClockSource,
    ClockQuality,
    ClockStatus,
    ClockType,
    ClockReading,
)
from timeos.msgs import ChronoStamp


class PTPState(Enum):
    """PTP port state."""
    INITIALIZING = "INITIALIZING"
    FAULTY = "FAULTY"
    DISABLED = "DISABLED"
    LISTENING = "LISTENING"
    PRE_MASTER = "PRE_MASTER"
    MASTER = "MASTER"
    PASSIVE = "PASSIVE"
    UNCALIBRATED = "UNCALIBRATED"
    SLAVE = "SLAVE"
    GRAND_MASTER = "GRAND_MASTER"


@dataclass
class PTPStatus:
    """PTP daemon status information.

    Attributes:
        state: Current port state
        master_offset: Offset from master in nanoseconds
        path_delay: Mean path delay in nanoseconds
        freq_adjustment: Frequency adjustment in ppb
        clock_id: PTP clock identity
        master_id: Master clock identity
        domain: PTP domain number
    """
    state: PTPState = PTPState.INITIALIZING
    master_offset: float = 0.0  # nanoseconds
    path_delay: float = 0.0     # nanoseconds
    freq_adjustment: float = 0.0  # parts per billion
    clock_id: str = ""
    master_id: str = ""
    domain: int = 0


class PTPClock(ClockSource):
    """PTP (IEEE 1588) synchronized clock source.

    Reads synchronization status from linuxptp's ptp4l daemon
    using the pmc (PTP management client) command.

    Example:
        clock = PTPClock(interface="eth0")
        if clock.is_synchronized:
            stamp = clock.now()
            print(f"Time: {stamp.t}, Offset: {clock.get_offset()}")
    """

    def __init__(
        self,
        interface: str = "eth0",
        domain: int = 0,
        uds_path: str = "/var/run/ptp4l",
        source_id: Optional[str] = None,
    ):
        """Initialize PTP clock.

        Args:
            interface: Network interface for PTP
            domain: PTP domain number
            uds_path: Path to ptp4l Unix domain socket
            source_id: Optional source identifier
        """
        self._interface = interface
        self._domain = domain
        self._uds_path = uds_path
        self._source_id = source_id or f"ptp_{interface}"

        self._status = PTPStatus()
        self._last_update = 0.0
        self._update_interval = 1.0  # seconds

        self._ptp_available = self._check_ptp_available()

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def clock_type(self) -> ClockType:
        return ClockType.PTP

    @property
    def status(self) -> ClockStatus:
        if not self._ptp_available:
            return ClockStatus.FAULT

        self._maybe_update_status()

        if self._status.state == PTPState.SLAVE:
            return ClockStatus.SYNCED
        elif self._status.state in (PTPState.UNCALIBRATED, PTPState.LISTENING):
            return ClockStatus.SYNCING
        elif self._status.state == PTPState.MASTER:
            return ClockStatus.SYNCED  # Master is also synced
        elif self._status.state == PTPState.FAULTY:
            return ClockStatus.FAULT
        else:
            return ClockStatus.FREERUN

    @property
    def is_synchronized(self) -> bool:
        return self.status == ClockStatus.SYNCED

    def _check_ptp_available(self) -> bool:
        """Check if PTP tools are available."""
        try:
            result = subprocess.run(
                ["which", "pmc"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _maybe_update_status(self) -> None:
        """Update status if interval has passed."""
        now = time.monotonic()
        if now - self._last_update >= self._update_interval:
            self._update_status()
            self._last_update = now

    def _update_status(self) -> None:
        """Query PTP status from pmc."""
        if not self._ptp_available:
            return

        try:
            # Query current data set
            result = subprocess.run(
                [
                    "pmc", "-u", "-b", "0",
                    "-d", str(self._domain),
                    "GET CURRENT_DATA_SET",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                self._parse_current_data(result.stdout)

            # Query port state
            result = subprocess.run(
                [
                    "pmc", "-u", "-b", "0",
                    "-d", str(self._domain),
                    "GET PORT_DATA_SET",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                self._parse_port_data(result.stdout)

        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            self._ptp_available = False

    def _parse_current_data(self, output: str) -> None:
        """Parse CURRENT_DATA_SET response."""
        # Example output:
        # CURRENT_DATA_SET
        #     stepsRemoved     1
        #     offsetFromMaster -23.0
        #     meanPathDelay    1234.0

        for line in output.split('\n'):
            line = line.strip()

            if line.startswith('offsetFromMaster'):
                try:
                    self._status.master_offset = float(line.split()[-1])
                except (ValueError, IndexError):
                    pass

            elif line.startswith('meanPathDelay'):
                try:
                    self._status.path_delay = float(line.split()[-1])
                except (ValueError, IndexError):
                    pass

    def _parse_port_data(self, output: str) -> None:
        """Parse PORT_DATA_SET response."""
        # Example output:
        # PORT_DATA_SET
        #     portState            SLAVE

        for line in output.split('\n'):
            line = line.strip()

            if line.startswith('portState'):
                state_str = line.split()[-1]
                try:
                    self._status.state = PTPState(state_str)
                except ValueError:
                    self._status.state = PTPState.INITIALIZING

    def now(self) -> ChronoStamp:
        """Get current time with uncertainty from PTP.

        Returns:
            ChronoStamp with PTP-synchronized time
        """
        # Use system clock (which should be disciplined by ptp4l)
        t = time.time()

        # Estimate uncertainty from PTP status
        self._maybe_update_status()

        if self._status.state == PTPState.SLAVE:
            # Synced to master - uncertainty is master offset + path delay
            uncertainty = (
                abs(self._status.master_offset) +
                self._status.path_delay
            ) * 1e-9  # Convert ns to s

            # Minimum uncertainty ~100ns for good PTP
            uncertainty = max(uncertainty, 100e-9)
        else:
            # Not synced - larger uncertainty
            uncertainty = 1e-3  # 1ms

        return ChronoStamp(
            frame_id="ptp",
            t=t,
            t_uncertainty=uncertainty,
            clock_id=self._source_id,
            clock_class="ptp",
        )

    def read(self) -> ClockReading:
        """Read current time with full metadata."""
        stamp = self.now()
        return ClockReading(
            timestamp=stamp.t,
            uncertainty=stamp.t_uncertainty,
            clock_id=self._source_id,
            clock_type=self.clock_type,
            status=self.status,
        )

    def get_offset(self) -> tuple[float, float]:
        """Get offset from master clock.

        Returns:
            Tuple of (offset_seconds, uncertainty_seconds)
        """
        self._maybe_update_status()

        if self._status.state == PTPState.SLAVE:
            offset = self._status.master_offset * 1e-9  # ns to s
            uncertainty = self._status.path_delay * 1e-9
            return (offset, max(uncertainty, 100e-9))

        # Not synced - no valid offset
        return (0.0, float('inf'))

    def get_quality(self) -> ClockQuality:
        """Get clock quality metrics.

        Returns:
            ClockQuality with PTP-specific metrics
        """
        self._maybe_update_status()

        offset, uncertainty = self.get_offset()

        # PTP is stratum 1 or 2 typically
        if self._status.state == PTPState.MASTER:
            stratum = 1
        elif self._status.state == PTPState.SLAVE:
            stratum = 2
        else:
            stratum = 16

        # Calculate quality score
        if self._status.state == PTPState.SLAVE:
            # Based on offset magnitude
            offset_ns = abs(self._status.master_offset)
            if offset_ns < 100:      # <100ns
                quality = 0.99
            elif offset_ns < 1000:   # <1µs
                quality = 0.95
            elif offset_ns < 10000:  # <10µs
                quality = 0.85
            elif offset_ns < 100000: # <100µs
                quality = 0.70
            else:
                quality = 0.50
        elif self._status.state == PTPState.MASTER:
            quality = 0.95
        else:
            quality = 0.0

        # Drift rate from frequency adjustment
        drift_rate = self._status.freq_adjustment * 1e-9  # ppb to fractional

        return ClockQuality(
            stratum=stratum,
            offset=offset,
            offset_uncertainty=uncertainty,
            jitter=self._status.path_delay * 1e-9,
            drift_rate=drift_rate * 1e6,  # Convert fractional to ppm
            last_sync=datetime.now(timezone.utc) if self._status.state == PTPState.SLAVE else None,
            sync_age=0.0 if self._status.state == PTPState.SLAVE else float('inf'),
        )

    def sync(self) -> bool:
        """Request synchronization (no-op for PTP).

        PTP synchronization is handled by the ptp4l daemon.

        Returns:
            True if currently synchronized
        """
        self._update_status()
        return self._status.state == PTPState.SLAVE

    def refresh(self) -> bool:
        """Refresh quality metrics from ptp4l.

        Returns:
            True if refresh was successful
        """
        self._update_status()
        return self._ptp_available


class SimulatedPTPClock(ClockSource):
    """Simulated PTP clock for testing.

    Simulates a PTP slave with configurable offset and jitter.
    """

    def __init__(
        self,
        offset_ns: float = 50.0,
        jitter_ns: float = 20.0,
        source_id: str = "ptp_sim",
    ):
        """Initialize simulated PTP clock.

        Args:
            offset_ns: Simulated offset in nanoseconds
            jitter_ns: Simulated jitter in nanoseconds
            source_id: Source identifier
        """
        import random
        self._offset_ns = offset_ns
        self._jitter_ns = jitter_ns
        self._source_id = source_id
        self._random = random.Random()
        self._state = PTPState.SLAVE

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def clock_type(self) -> ClockType:
        return ClockType.PTP

    @property
    def status(self) -> ClockStatus:
        return ClockStatus.SYNCED if self._state == PTPState.SLAVE else ClockStatus.FREERUN

    @property
    def is_synchronized(self) -> bool:
        return self._state == PTPState.SLAVE

    def now(self) -> ChronoStamp:
        t = time.time()

        # Add simulated offset and jitter
        jitter = self._random.gauss(0, self._jitter_ns) * 1e-9
        t += (self._offset_ns * 1e-9) + jitter

        uncertainty = (abs(self._offset_ns) + self._jitter_ns * 3) * 1e-9

        return ChronoStamp(
            frame_id="ptp_sim",
            t=t,
            t_uncertainty=uncertainty,
            clock_id=self._source_id,
            clock_class="ptp",
        )

    def read(self) -> ClockReading:
        stamp = self.now()
        return ClockReading(
            timestamp=stamp.t,
            uncertainty=stamp.t_uncertainty,
            clock_id=self._source_id,
            clock_type=self.clock_type,
            status=self.status,
        )

    def get_offset(self) -> tuple[float, float]:
        return (self._offset_ns * 1e-9, self._jitter_ns * 1e-9)

    def get_quality(self) -> ClockQuality:
        return ClockQuality(
            stratum=2,
            offset=self._offset_ns * 1e-9,
            offset_uncertainty=(self._offset_ns + self._jitter_ns * 3) * 1e-9,
            jitter=self._jitter_ns * 1e-9,
            drift_rate=0.0,
            last_sync=datetime.now(timezone.utc),
            sync_age=0.0,
        )

    def sync(self) -> bool:
        return True

    def refresh(self) -> bool:
        """Refresh quality metrics (no-op for simulated).

        Returns:
            True always (simulated clock is always available)
        """
        return True
