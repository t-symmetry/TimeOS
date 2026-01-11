"""NTP clock source with chrony/ntpd integration.

Provides NTP time with proper offset and uncertainty tracking
by querying chronyc or ntpq for synchronization status.
"""

from __future__ import annotations

import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Tuple, Optional, Dict, Any

from timeos.msgs import ChronoStamp
from timeos.clocks.base import (
    ClockSource,
    ClockQuality,
    ClockStatus,
    ClockType,
    ClockReading,
)


class NTPClock(ClockSource):
    """NTP clock source with chrony/ntpd integration.

    Reads system time with uncertainty derived from NTP daemon
    synchronization status. Supports both chrony and ntpd.

    Example:
        >>> clock = NTPClock()
        >>> if clock.is_synchronized():
        ...     stamp = clock.now()
        ...     print(f"Offset: {clock.get_quality().offset * 1e6:.1f} µs")
        ...     print(f"Jitter: {clock.get_quality().jitter * 1e6:.1f} µs")
    """

    def __init__(
        self,
        source_id: str = "ntp",
        frame_id: str = "utc",
        prefer_chrony: bool = True,
        refresh_interval: float = 10.0,
    ):
        """Initialize NTP clock source.

        Args:
            source_id: Unique identifier for this clock
            frame_id: Reference frame (default: "utc")
            prefer_chrony: Try chrony before ntpd
            refresh_interval: Minimum seconds between quality refreshes
        """
        super().__init__(
            source_id=source_id,
            clock_type=ClockType.NTP,
            frame_id=frame_id,
        )

        self._prefer_chrony = prefer_chrony
        self._refresh_interval = refresh_interval
        self._last_refresh: float = 0.0
        self._ntp_daemon: Optional[str] = None

        # Detect available NTP daemon
        self._detect_ntp_daemon()

        # Initial quality refresh
        if self._ntp_daemon:
            self.refresh()
        else:
            self._status = ClockStatus.FAULT

    def _detect_ntp_daemon(self) -> None:
        """Detect which NTP daemon is running."""
        daemons = ["chrony", "ntpd"] if self._prefer_chrony else ["ntpd", "chrony"]

        for daemon in daemons:
            if daemon == "chrony":
                if self._check_chrony():
                    self._ntp_daemon = "chrony"
                    return
            elif daemon == "ntpd":
                if self._check_ntpd():
                    self._ntp_daemon = "ntpd"
                    return

        self._ntp_daemon = None

    def _check_chrony(self) -> bool:
        """Check if chrony is available."""
        try:
            result = subprocess.run(
                ["chronyc", "tracking"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _check_ntpd(self) -> bool:
        """Check if ntpd is available."""
        try:
            result = subprocess.run(
                ["ntpq", "-p"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _parse_chrony_tracking(self) -> Optional[Dict[str, Any]]:
        """Parse chronyc tracking output.

        Returns:
            Dict with parsed values, or None on error.
        """
        try:
            result = subprocess.run(
                ["chronyc", "tracking"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )

            if result.returncode != 0:
                return None

            data = {}
            for line in result.stdout.splitlines():
                if ":" not in line:
                    continue

                key, value = line.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                data[key] = value

            return data

        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            return None

    def _parse_time_value(self, value: str) -> float:
        """Parse time value from chrony output.

        Args:
            value: String like "0.000123456 seconds" or "123 ns"

        Returns:
            Time in seconds.
        """
        # Extract numeric part and unit
        match = re.match(r"([+-]?\d+\.?\d*)\s*(\w+)?", value)
        if not match:
            return 0.0

        num = float(match.group(1))
        unit = match.group(2) or "seconds"

        # Convert to seconds
        unit_multipliers = {
            "seconds": 1.0,
            "second": 1.0,
            "sec": 1.0,
            "s": 1.0,
            "milliseconds": 1e-3,
            "millisecond": 1e-3,
            "ms": 1e-3,
            "microseconds": 1e-6,
            "microsecond": 1e-6,
            "us": 1e-6,
            "nanoseconds": 1e-9,
            "nanosecond": 1e-9,
            "ns": 1e-9,
        }

        return num * unit_multipliers.get(unit.lower(), 1.0)

    def _update_quality_chrony(self) -> bool:
        """Update quality from chrony.

        Returns:
            True if update succeeded.
        """
        data = self._parse_chrony_tracking()
        if data is None:
            self._status = ClockStatus.FAULT
            return False

        # Parse stratum
        stratum = 16
        if "stratum" in data:
            try:
                stratum = int(data["stratum"])
            except ValueError:
                pass

        # Parse offset
        offset = 0.0
        if "system_time" in data:
            offset = self._parse_time_value(data["system_time"])
        elif "last_offset" in data:
            offset = self._parse_time_value(data["last_offset"])

        # Parse root delay/dispersion
        root_delay = 0.0
        if "root_delay" in data:
            root_delay = self._parse_time_value(data["root_delay"])

        root_dispersion = 0.0
        if "root_dispersion" in data:
            root_dispersion = self._parse_time_value(data["root_dispersion"])

        # Parse RMS offset (jitter estimate)
        jitter = 0.0
        if "rms_offset" in data:
            jitter = self._parse_time_value(data["rms_offset"])

        # Parse frequency/drift
        drift_rate = 0.0
        if "frequency" in data:
            # Frequency is in ppm
            match = re.match(r"([+-]?\d+\.?\d*)", data["frequency"])
            if match:
                drift_rate = float(match.group(1))

        # Parse leap status
        leap = 0
        if "leap_status" in data:
            leap_str = data["leap_status"].lower()
            if "normal" in leap_str:
                leap = 0
            elif "insert" in leap_str:
                leap = 1
            elif "delete" in leap_str:
                leap = 2
            else:
                leap = 3

        # Determine sync status
        if stratum < 16 and leap != 3:
            if jitter > 0.01:  # > 10ms jitter
                self._status = ClockStatus.DEGRADED
            else:
                self._status = ClockStatus.SYNCED
        else:
            self._status = ClockStatus.FREERUN

        # Update quality
        self._quality = ClockQuality(
            stratum=stratum,
            offset=offset,
            offset_uncertainty=max(jitter, root_dispersion),
            jitter=jitter,
            wander=0.0,
            drift_rate=drift_rate,
            last_sync=datetime.now(timezone.utc),
            sync_age=0.0,
            root_delay=root_delay,
            root_dispersion=root_dispersion,
            leap_indicator=leap,
        )

        return True

    def _parse_ntpq_peers(self) -> Optional[Dict[str, Any]]:
        """Parse ntpq -p output for sync peer.

        Returns:
            Dict with parsed values from sync peer, or None.
        """
        try:
            result = subprocess.run(
                ["ntpq", "-pn"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )

            if result.returncode != 0:
                return None

            # Find the sync peer (marked with *)
            for line in result.stdout.splitlines():
                if line.startswith("*"):
                    # Parse peer line
                    # Format: *remote refid st t when poll reach delay offset jitter
                    parts = line[1:].split()
                    if len(parts) >= 10:
                        return {
                            "remote": parts[0],
                            "refid": parts[1],
                            "stratum": int(parts[2]),
                            "delay": float(parts[7]) / 1000,  # ms to s
                            "offset": float(parts[8]) / 1000,  # ms to s
                            "jitter": float(parts[9]) / 1000,  # ms to s
                        }

            return None

        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            return None

    def _update_quality_ntpd(self) -> bool:
        """Update quality from ntpd.

        Returns:
            True if update succeeded.
        """
        data = self._parse_ntpq_peers()
        if data is None:
            self._status = ClockStatus.FREERUN
            return False

        stratum = data.get("stratum", 16)
        offset = data.get("offset", 0.0)
        delay = data.get("delay", 0.0)
        jitter = data.get("jitter", 0.0)

        if stratum < 16:
            self._status = ClockStatus.SYNCED
        else:
            self._status = ClockStatus.FREERUN

        self._quality = ClockQuality(
            stratum=stratum,
            offset=offset,
            offset_uncertainty=jitter,
            jitter=jitter,
            wander=0.0,
            drift_rate=0.0,
            last_sync=datetime.now(timezone.utc),
            sync_age=0.0,
            root_delay=delay,
            root_dispersion=jitter * 2,  # Estimate
            leap_indicator=0,
        )

        return True

    def now(self) -> ChronoStamp:
        """Get current time with NTP-derived uncertainty.

        Returns:
            ChronoStamp with current time and NTP uncertainty.
        """
        # Auto-refresh if stale
        if time.monotonic() - self._last_refresh > self._refresh_interval:
            self.refresh()

        t = time.time()

        # Uncertainty is NTP offset uncertainty + jitter
        uncertainty = self._quality.offset_uncertainty + self._quality.jitter

        return ChronoStamp(
            frame_id=self._frame_id,
            t=t,
            t_uncertainty=uncertainty,
            clock_id=self._source_id,
            clock_class=self._clock_type.value,
            provenance=[],
        )

    def read(self) -> ClockReading:
        """Get full clock reading with quality metrics.

        Returns:
            ClockReading with timestamp, quality, and status.
        """
        t_before = time.perf_counter()
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
        """Get NTP offset with uncertainty.

        Returns:
            Tuple of (offset, uncertainty) in seconds.
        """
        return (self._quality.offset, self._quality.offset_uncertainty)

    def get_quality(self) -> ClockQuality:
        """Get current clock quality metrics.

        Returns:
            ClockQuality with NTP metrics.
        """
        return self._quality

    def refresh(self) -> bool:
        """Refresh quality from NTP daemon.

        Returns:
            True if refresh succeeded.
        """
        self._last_refresh = time.monotonic()

        if self._ntp_daemon == "chrony":
            return self._update_quality_chrony()
        elif self._ntp_daemon == "ntpd":
            return self._update_quality_ntpd()
        else:
            return False

    @property
    def ntp_daemon(self) -> Optional[str]:
        """Get detected NTP daemon name."""
        return self._ntp_daemon

    def get_sources(self) -> list:
        """Get list of NTP sources.

        Returns:
            List of source info dicts.
        """
        if self._ntp_daemon == "chrony":
            return self._get_chrony_sources()
        elif self._ntp_daemon == "ntpd":
            return self._get_ntpq_sources()
        return []

    def _get_chrony_sources(self) -> list:
        """Get chrony source list."""
        try:
            result = subprocess.run(
                ["chronyc", "sources"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )

            if result.returncode != 0:
                return []

            sources = []
            for line in result.stdout.splitlines()[3:]:  # Skip header
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 8:
                    sources.append({
                        "mode": parts[0],
                        "state": parts[1],
                        "name": parts[2],
                        "stratum": parts[3],
                        "poll": parts[4],
                        "reach": parts[5],
                        "last_rx": parts[6],
                        "offset": parts[7],
                    })

            return sources

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    def _get_ntpq_sources(self) -> list:
        """Get ntpq peer list."""
        try:
            result = subprocess.run(
                ["ntpq", "-pn"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )

            if result.returncode != 0:
                return []

            sources = []
            for line in result.stdout.splitlines()[2:]:  # Skip header
                if not line.strip():
                    continue
                tally = line[0]
                parts = line[1:].split()
                if len(parts) >= 9:
                    sources.append({
                        "tally": tally,
                        "remote": parts[0],
                        "refid": parts[1],
                        "stratum": parts[2],
                        "type": parts[3],
                        "when": parts[4],
                        "poll": parts[5],
                        "reach": parts[6],
                        "delay": parts[7],
                        "offset": parts[8],
                        "jitter": parts[9] if len(parts) > 9 else "0",
                    })

            return sources

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []
