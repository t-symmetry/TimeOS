"""GPS clock source via gpsd.

Provides GPS time with uncertainty tracking by querying gpsd.
Supports optional PPS discipline for sub-microsecond accuracy.
"""

from __future__ import annotations

import json
import socket
import time
from datetime import datetime, timezone
from typing import Tuple, Optional, Dict, Any, List

from timeos.msgs import ChronoStamp
from timeos.clocks.base import (
    ClockSource,
    ClockQuality,
    ClockStatus,
    ClockType,
    ClockReading,
)


# GPS-UTC offset (GPS time does not include leap seconds)
# As of 2024, GPS is 18 seconds ahead of UTC
GPS_UTC_OFFSET = 18


class GPSClock(ClockSource):
    """GPS clock source via gpsd.

    Connects to gpsd to get GPS time with proper uncertainty
    based on fix quality, HDOP, and satellite count.

    Example:
        >>> clock = GPSClock()
        >>> if clock.is_synchronized():
        ...     stamp = clock.now()
        ...     print(f"GPS time: {stamp.t}")
        ...     print(f"Satellites: {clock.satellite_count}")
    """

    def __init__(
        self,
        source_id: str = "gps",
        frame_id: str = "utc",
        host: str = "localhost",
        port: int = 2947,
        use_pps: bool = True,
        timeout: float = 5.0,
    ):
        """Initialize GPS clock source.

        Args:
            source_id: Unique identifier for this clock
            frame_id: Reference frame (default: "utc")
            host: gpsd host address
            port: gpsd port (default: 2947)
            use_pps: Use PPS if available for higher accuracy
            timeout: Socket timeout in seconds
        """
        super().__init__(
            source_id=source_id,
            clock_type=ClockType.GPS,
            frame_id=frame_id,
        )

        self._host = host
        self._port = port
        self._use_pps = use_pps
        self._timeout = timeout

        self._socket: Optional[socket.socket] = None
        self._last_tpv: Optional[Dict[str, Any]] = None
        self._last_sky: Optional[Dict[str, Any]] = None
        self._satellite_count = 0
        self._has_pps = False

        # Try to connect
        if self._connect():
            self._status = ClockStatus.SYNCING
            self.refresh()
        else:
            self._status = ClockStatus.FAULT

    def _connect(self) -> bool:
        """Connect to gpsd.

        Returns:
            True if connection succeeded.
        """
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self._timeout)
            self._socket.connect((self._host, self._port))

            # Enable watch mode
            self._socket.sendall(b'?WATCH={"enable":true,"json":true}\n')

            return True

        except (socket.error, socket.timeout):
            self._socket = None
            return False

    def _disconnect(self) -> None:
        """Disconnect from gpsd."""
        if self._socket:
            try:
                self._socket.sendall(b'?WATCH={"enable":false}\n')
                self._socket.close()
            except socket.error:
                pass
            self._socket = None

    def _read_message(self) -> Optional[Dict[str, Any]]:
        """Read a JSON message from gpsd.

        Returns:
            Parsed JSON message, or None on error.
        """
        if not self._socket:
            return None

        try:
            # Read until newline
            data = b""
            while True:
                chunk = self._socket.recv(1)
                if not chunk:
                    return None
                if chunk == b"\n":
                    break
                data += chunk

            return json.loads(data.decode("utf-8"))

        except (socket.error, socket.timeout, json.JSONDecodeError):
            return None

    def _poll(self) -> bool:
        """Poll gpsd for current state.

        Returns:
            True if we got valid data.
        """
        if not self._socket:
            if not self._connect():
                return False

        # Request a poll
        try:
            self._socket.sendall(b"?POLL;\n")
        except socket.error:
            self._disconnect()
            return False

        # Read messages until we get what we need
        got_tpv = False
        got_sky = False
        attempts = 0

        while attempts < 10 and not (got_tpv and got_sky):
            msg = self._read_message()
            if msg is None:
                break

            msg_class = msg.get("class", "")

            if msg_class == "TPV":
                self._last_tpv = msg
                got_tpv = True

            elif msg_class == "SKY":
                self._last_sky = msg
                got_sky = True

            elif msg_class == "PPS":
                self._has_pps = True

            attempts += 1

        return got_tpv

    def _calculate_uncertainty(self) -> float:
        """Calculate time uncertainty based on GPS state.

        Returns:
            Estimated uncertainty in seconds.
        """
        if not self._last_tpv:
            return float('inf')

        # Base uncertainty depends on fix mode
        mode = self._last_tpv.get("mode", 0)
        if mode < 2:  # No fix
            return float('inf')

        # Start with base uncertainty
        if self._has_pps and self._use_pps:
            # PPS-disciplined: sub-microsecond possible
            base_uncertainty = 1e-6
        elif mode == 3:  # 3D fix
            base_uncertainty = 50e-9  # GPS spec: 50ns
        else:  # 2D fix
            base_uncertainty = 100e-9

        # Adjust for HDOP if available
        hdop = self._last_tpv.get("hdop", 1.0)
        if hdop:
            base_uncertainty *= max(1.0, hdop)

        # Adjust for satellite count
        if self._last_sky:
            used = sum(1 for s in self._last_sky.get("satellites", [])
                      if s.get("used", False))
            self._satellite_count = used
            if used < 4:
                base_uncertainty *= 10  # Poor geometry
            elif used < 6:
                base_uncertainty *= 2

        # Add estimated clock offset uncertainty
        ept = self._last_tpv.get("ept", 0.0)  # Time error estimate
        if ept:
            base_uncertainty = max(base_uncertainty, ept)

        return base_uncertainty

    def _update_quality(self) -> None:
        """Update quality metrics from GPS data."""
        if not self._last_tpv:
            self._quality = ClockQuality(stratum=16)
            return

        mode = self._last_tpv.get("mode", 0)
        uncertainty = self._calculate_uncertainty()

        if mode >= 2:
            stratum = 1 if self._has_pps else 2
            self._status = ClockStatus.SYNCED
        else:
            stratum = 16
            self._status = ClockStatus.FREERUN

        # Extract time error estimates
        ept = self._last_tpv.get("ept", uncertainty)

        self._quality = ClockQuality(
            stratum=stratum,
            offset=0.0,  # GPS is the reference
            offset_uncertainty=uncertainty,
            jitter=ept,
            wander=0.0,
            drift_rate=0.0,
            last_sync=datetime.now(timezone.utc),
            sync_age=0.0,
            root_delay=0.0,
            root_dispersion=uncertainty,
            leap_indicator=0,
        )

    def now(self) -> ChronoStamp:
        """Get current GPS time.

        Note: Returns system time adjusted by GPS offset. For true
        GPS time, use read() and extract from the TPV message.

        Returns:
            ChronoStamp with GPS-derived time.
        """
        # Poll if we don't have recent data
        if self._last_tpv is None:
            self._poll()

        uncertainty = self._calculate_uncertainty()

        # Use GPS time if available, else system time
        if self._last_tpv and "time" in self._last_tpv:
            # Parse ISO timestamp from GPS
            try:
                gps_time_str = self._last_tpv["time"]
                gps_dt = datetime.fromisoformat(gps_time_str.replace("Z", "+00:00"))
                t = gps_dt.timestamp()
            except (ValueError, KeyError):
                t = time.time()
        else:
            t = time.time()

        return ChronoStamp(
            frame_id=self._frame_id,
            t=t,
            t_uncertainty=uncertainty,
            clock_id=self._source_id,
            clock_class=self._clock_type.value,
            provenance=[],
        )

    def read(self) -> ClockReading:
        """Get full clock reading with GPS quality metrics.

        Returns:
            ClockReading with GPS timestamp and quality.
        """
        t_before = time.perf_counter()
        self._poll()
        stamp = self.now()
        t_after = time.perf_counter()

        self._last_reading = ClockReading(
            stamp=stamp,
            quality=self._quality,
            status=self._status,
            source_id=self._source_id,
            read_latency=t_after - t_before,
        )

        return self._last_reading

    def get_offset(self) -> Tuple[float, float]:
        """Get GPS-system clock offset.

        Returns:
            Tuple of (offset, uncertainty) in seconds.
        """
        # GPS is considered the reference
        return (0.0, self._quality.offset_uncertainty)

    def get_quality(self) -> ClockQuality:
        """Get current GPS clock quality.

        Returns:
            ClockQuality with GPS-derived metrics.
        """
        return self._quality

    def refresh(self) -> bool:
        """Refresh GPS state from gpsd.

        Returns:
            True if refresh succeeded.
        """
        if self._poll():
            self._update_quality()
            return True
        return False

    @property
    def satellite_count(self) -> int:
        """Number of satellites used in fix."""
        return self._satellite_count

    @property
    def has_pps(self) -> bool:
        """Whether PPS signal is available."""
        return self._has_pps

    @property
    def fix_mode(self) -> int:
        """Current fix mode (0=none, 1=searching, 2=2D, 3=3D)."""
        if self._last_tpv:
            return self._last_tpv.get("mode", 0)
        return 0

    def get_position(self) -> Optional[Dict[str, float]]:
        """Get current GPS position.

        Returns:
            Dict with lat, lon, alt or None if no fix.
        """
        if not self._last_tpv or self._last_tpv.get("mode", 0) < 2:
            return None

        return {
            "lat": self._last_tpv.get("lat", 0.0),
            "lon": self._last_tpv.get("lon", 0.0),
            "alt": self._last_tpv.get("alt", 0.0),
        }

    def get_satellites(self) -> List[Dict[str, Any]]:
        """Get satellite information.

        Returns:
            List of satellite info dicts.
        """
        if not self._last_sky:
            return []
        return self._last_sky.get("satellites", [])

    def close(self) -> None:
        """Close GPS connection."""
        self._disconnect()

    def __del__(self):
        self.close()


class SimulatedGPSClock(ClockSource):
    """Simulated GPS clock for testing.

    Provides a GPS-like clock without actual hardware.

    Example:
        >>> clock = SimulatedGPSClock()
        >>> stamp = clock.now()
    """

    def __init__(
        self,
        source_id: str = "gps_sim",
        frame_id: str = "utc",
        base_uncertainty: float = 50e-9,
        satellite_count: int = 8,
    ):
        """Initialize simulated GPS clock.

        Args:
            source_id: Unique identifier
            frame_id: Reference frame
            base_uncertainty: Simulated uncertainty
            satellite_count: Simulated satellite count
        """
        super().__init__(
            source_id=source_id,
            clock_type=ClockType.GPS,
            frame_id=frame_id,
        )

        self._base_uncertainty = base_uncertainty
        self._satellite_count = satellite_count
        self._status = ClockStatus.SYNCED
        self._update_quality()

    def _update_quality(self) -> None:
        """Update simulated quality."""
        self._quality = ClockQuality(
            stratum=1,
            offset=0.0,
            offset_uncertainty=self._base_uncertainty,
            jitter=self._base_uncertainty,
            wander=0.0,
            drift_rate=0.0,
            last_sync=datetime.now(timezone.utc),
            sync_age=0.0,
            root_delay=0.0,
            root_dispersion=self._base_uncertainty,
            leap_indicator=0,
        )

    def now(self) -> ChronoStamp:
        """Get simulated GPS time.

        Returns:
            ChronoStamp with simulated GPS time.
        """
        return ChronoStamp(
            frame_id=self._frame_id,
            t=time.time(),
            t_uncertainty=self._base_uncertainty,
            clock_id=self._source_id,
            clock_class=self._clock_type.value,
            provenance=[],
        )

    def read(self) -> ClockReading:
        """Get full simulated reading.

        Returns:
            ClockReading with simulated data.
        """
        return ClockReading(
            stamp=self.now(),
            quality=self._quality,
            status=self._status,
            source_id=self._source_id,
            read_latency=1e-6,
        )

    def get_offset(self) -> Tuple[float, float]:
        """Get simulated offset.

        Returns:
            Zero offset with base uncertainty.
        """
        return (0.0, self._base_uncertainty)

    def get_quality(self) -> ClockQuality:
        """Get simulated quality.

        Returns:
            ClockQuality with simulated metrics.
        """
        return self._quality

    def refresh(self) -> bool:
        """Refresh simulated clock.

        Returns:
            Always True.
        """
        self._update_quality()
        return True

    @property
    def satellite_count(self) -> int:
        """Simulated satellite count."""
        return self._satellite_count
