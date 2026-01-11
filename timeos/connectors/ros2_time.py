"""ROS2 Time bridging for TimeOS.

Provides conversion between ROS2 builtin_interfaces/Time/Duration
and TimeOS ChronoStamp/temporal types.

This module does NOT require rclpy to be installed - it works with
raw message data structures for maximum compatibility.

Supports:
- builtin_interfaces/Time <-> ChronoStamp
- builtin_interfaces/Duration <-> float seconds
- std_msgs/Header timestamps
- rosgraph_msgs/Clock for simulation time
- tf2_msgs timestamped transforms
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List, Union
from enum import Enum

from timeos.msgs import ChronoStamp


class ROS2TimeSource(Enum):
    """Source of ROS2 time."""

    SYSTEM = "system"       # System wall clock
    ROS = "ros"             # /clock topic (simulation time)
    STEADY = "steady"       # Monotonic clock


@dataclass
class ROS2Time:
    """ROS2 Time representation (builtin_interfaces/Time).

    Matches the ROS2 message structure without requiring rclpy.

    Attributes:
        sec: Seconds component (signed int32)
        nanosec: Nanoseconds component (unsigned int32, 0-999999999)
    """

    sec: int = 0
    nanosec: int = 0

    def __post_init__(self):
        """Normalize nanoseconds to valid range."""
        if self.nanosec >= 1_000_000_000:
            extra_sec = self.nanosec // 1_000_000_000
            self.sec += extra_sec
            self.nanosec = self.nanosec % 1_000_000_000
        elif self.nanosec < 0:
            borrow = (-self.nanosec // 1_000_000_000) + 1
            self.sec -= borrow
            self.nanosec += borrow * 1_000_000_000

    def to_sec(self) -> float:
        """Convert to seconds as float."""
        return self.sec + self.nanosec * 1e-9

    def to_nsec(self) -> int:
        """Convert to nanoseconds as integer."""
        return self.sec * 1_000_000_000 + self.nanosec

    @classmethod
    def from_sec(cls, seconds: float) -> "ROS2Time":
        """Create from seconds float.

        Args:
            seconds: Time in seconds

        Returns:
            ROS2Time instance
        """
        sec = int(seconds)
        nanosec = int((seconds - sec) * 1e9)
        return cls(sec=sec, nanosec=nanosec)

    @classmethod
    def from_nsec(cls, nanoseconds: int) -> "ROS2Time":
        """Create from nanoseconds integer.

        Args:
            nanoseconds: Time in nanoseconds

        Returns:
            ROS2Time instance
        """
        sec = nanoseconds // 1_000_000_000
        nanosec = nanoseconds % 1_000_000_000
        return cls(sec=sec, nanosec=nanosec)

    @classmethod
    def from_msg(cls, msg: Any) -> "ROS2Time":
        """Create from ROS2 message.

        Args:
            msg: builtin_interfaces/Time message or dict

        Returns:
            ROS2Time instance
        """
        if isinstance(msg, dict):
            return cls(sec=msg.get("sec", 0), nanosec=msg.get("nanosec", 0))
        return cls(sec=getattr(msg, "sec", 0), nanosec=getattr(msg, "nanosec", 0))

    def to_msg_dict(self) -> Dict[str, int]:
        """Convert to message dictionary.

        Returns:
            Dict with sec and nanosec keys
        """
        return {"sec": self.sec, "nanosec": self.nanosec}

    def __add__(self, other: "ROS2Duration") -> "ROS2Time":
        """Add duration to time."""
        return ROS2Time(
            sec=self.sec + other.sec,
            nanosec=self.nanosec + other.nanosec,
        )

    def __sub__(self, other: Union["ROS2Time", "ROS2Duration"]) -> Union["ROS2Duration", "ROS2Time"]:
        """Subtract time or duration."""
        if isinstance(other, ROS2Time):
            return ROS2Duration(
                sec=self.sec - other.sec,
                nanosec=self.nanosec - other.nanosec,
            )
        return ROS2Time(
            sec=self.sec - other.sec,
            nanosec=self.nanosec - other.nanosec,
        )

    def __lt__(self, other: "ROS2Time") -> bool:
        return (self.sec, self.nanosec) < (other.sec, other.nanosec)

    def __le__(self, other: "ROS2Time") -> bool:
        return (self.sec, self.nanosec) <= (other.sec, other.nanosec)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ROS2Time):
            return False
        return self.sec == other.sec and self.nanosec == other.nanosec


@dataclass
class ROS2Duration:
    """ROS2 Duration representation (builtin_interfaces/Duration).

    Attributes:
        sec: Seconds component (signed int32)
        nanosec: Nanoseconds component (unsigned int32)
    """

    sec: int = 0
    nanosec: int = 0

    def __post_init__(self):
        """Normalize nanoseconds."""
        if self.nanosec >= 1_000_000_000:
            extra_sec = self.nanosec // 1_000_000_000
            self.sec += extra_sec
            self.nanosec = self.nanosec % 1_000_000_000
        elif self.nanosec < 0:
            borrow = (-self.nanosec // 1_000_000_000) + 1
            self.sec -= borrow
            self.nanosec += borrow * 1_000_000_000

    def to_sec(self) -> float:
        """Convert to seconds."""
        return self.sec + self.nanosec * 1e-9

    def to_nsec(self) -> int:
        """Convert to nanoseconds."""
        return self.sec * 1_000_000_000 + self.nanosec

    @classmethod
    def from_sec(cls, seconds: float) -> "ROS2Duration":
        """Create from seconds."""
        sec = int(seconds)
        nanosec = int((seconds - sec) * 1e9)
        return cls(sec=sec, nanosec=nanosec)

    @classmethod
    def from_msg(cls, msg: Any) -> "ROS2Duration":
        """Create from ROS2 message."""
        if isinstance(msg, dict):
            return cls(sec=msg.get("sec", 0), nanosec=msg.get("nanosec", 0))
        return cls(sec=getattr(msg, "sec", 0), nanosec=getattr(msg, "nanosec", 0))

    def to_msg_dict(self) -> Dict[str, int]:
        """Convert to message dictionary."""
        return {"sec": self.sec, "nanosec": self.nanosec}

    def __neg__(self) -> "ROS2Duration":
        """Negate duration."""
        return ROS2Duration.from_sec(-self.to_sec())

    def __add__(self, other: "ROS2Duration") -> "ROS2Duration":
        """Add durations."""
        return ROS2Duration(
            sec=self.sec + other.sec,
            nanosec=self.nanosec + other.nanosec,
        )

    def __sub__(self, other: "ROS2Duration") -> "ROS2Duration":
        """Subtract durations."""
        return ROS2Duration(
            sec=self.sec - other.sec,
            nanosec=self.nanosec - other.nanosec,
        )

    def __mul__(self, factor: float) -> "ROS2Duration":
        """Multiply by scalar."""
        return ROS2Duration.from_sec(self.to_sec() * factor)

    def __abs__(self) -> "ROS2Duration":
        """Absolute value."""
        return ROS2Duration.from_sec(abs(self.to_sec()))


@dataclass
class ROS2Header:
    """ROS2 Header representation (std_msgs/Header).

    Attributes:
        stamp: Timestamp
        frame_id: Coordinate frame ID
    """

    stamp: ROS2Time = field(default_factory=ROS2Time)
    frame_id: str = ""

    @classmethod
    def from_msg(cls, msg: Any) -> "ROS2Header":
        """Create from ROS2 message."""
        if isinstance(msg, dict):
            stamp = ROS2Time.from_msg(msg.get("stamp", {}))
            frame_id = msg.get("frame_id", "")
        else:
            stamp = ROS2Time.from_msg(getattr(msg, "stamp", ROS2Time()))
            frame_id = getattr(msg, "frame_id", "")
        return cls(stamp=stamp, frame_id=frame_id)

    def to_msg_dict(self) -> Dict[str, Any]:
        """Convert to message dictionary."""
        return {
            "stamp": self.stamp.to_msg_dict(),
            "frame_id": self.frame_id,
        }


class ROS2TimeBridge:
    """Bridge between ROS2 Time and TimeOS ChronoStamp.

    Handles conversion with uncertainty tracking and frame mapping.

    Example:
        >>> bridge = ROS2TimeBridge()
        >>> ros_time = ROS2Time(sec=1234567890, nanosec=123456789)
        >>> stamp = bridge.ros2_to_chrono(ros_time)
        >>> print(f"Time: {stamp.t}, Frame: {stamp.frame_id}")

        >>> # Convert back
        >>> ros_time_2 = bridge.chrono_to_ros2(stamp)
    """

    def __init__(
        self,
        default_frame_id: str = "base_link",
        default_uncertainty: float = 1e-6,
        clock_id: str = "ros2",
        frame_map: Optional[Dict[str, str]] = None,
    ):
        """Initialize ROS2 time bridge.

        Args:
            default_frame_id: Default frame ID for conversions
            default_uncertainty: Default uncertainty in seconds
            clock_id: Clock identifier for ChronoStamps
            frame_map: Mapping from ROS2 frame_id to TimeOS frame_id
        """
        self._default_frame_id = default_frame_id
        self._default_uncertainty = default_uncertainty
        self._clock_id = clock_id
        self._frame_map = frame_map or {}

        # Time tracking for simulation time
        self._sim_time: Optional[ROS2Time] = None
        self._use_sim_time = False

    def ros2_to_chrono(
        self,
        ros_time: Union[ROS2Time, Dict[str, int], Any],
        frame_id: Optional[str] = None,
        uncertainty: Optional[float] = None,
    ) -> ChronoStamp:
        """Convert ROS2 Time to ChronoStamp.

        Args:
            ros_time: ROS2 Time (object, dict, or message)
            frame_id: Optional frame ID override
            uncertainty: Optional uncertainty override

        Returns:
            ChronoStamp instance
        """
        if not isinstance(ros_time, ROS2Time):
            ros_time = ROS2Time.from_msg(ros_time)

        # Map frame ID
        frame = frame_id or self._default_frame_id
        if frame in self._frame_map:
            frame = self._frame_map[frame]

        return ChronoStamp(
            frame_id=frame,
            t=ros_time.to_sec(),
            t_uncertainty=uncertainty or self._default_uncertainty,
            clock_id=self._clock_id,
            clock_class="ros2",
        )

    def chrono_to_ros2(self, stamp: ChronoStamp) -> ROS2Time:
        """Convert ChronoStamp to ROS2 Time.

        Args:
            stamp: ChronoStamp instance

        Returns:
            ROS2Time instance
        """
        return ROS2Time.from_sec(stamp.t)

    def header_to_chrono(
        self,
        header: Union[ROS2Header, Dict[str, Any], Any],
        uncertainty: Optional[float] = None,
    ) -> ChronoStamp:
        """Convert ROS2 Header to ChronoStamp.

        Args:
            header: ROS2 Header (object, dict, or message)
            uncertainty: Optional uncertainty override

        Returns:
            ChronoStamp instance
        """
        if not isinstance(header, ROS2Header):
            header = ROS2Header.from_msg(header)

        return self.ros2_to_chrono(
            header.stamp,
            frame_id=header.frame_id or None,
            uncertainty=uncertainty,
        )

    def chrono_to_header(
        self,
        stamp: ChronoStamp,
        frame_id: Optional[str] = None,
    ) -> ROS2Header:
        """Convert ChronoStamp to ROS2 Header.

        Args:
            stamp: ChronoStamp instance
            frame_id: Optional frame ID override

        Returns:
            ROS2Header instance
        """
        # Reverse frame map
        ros_frame = frame_id or stamp.frame_id
        for ros_name, chrono_name in self._frame_map.items():
            if chrono_name == ros_frame:
                ros_frame = ros_name
                break

        return ROS2Header(
            stamp=self.chrono_to_ros2(stamp),
            frame_id=ros_frame,
        )

    def duration_to_seconds(
        self,
        duration: Union[ROS2Duration, Dict[str, int], Any],
    ) -> float:
        """Convert ROS2 Duration to seconds.

        Args:
            duration: ROS2 Duration

        Returns:
            Duration in seconds
        """
        if not isinstance(duration, ROS2Duration):
            duration = ROS2Duration.from_msg(duration)
        return duration.to_sec()

    def seconds_to_duration(self, seconds: float) -> ROS2Duration:
        """Convert seconds to ROS2 Duration.

        Args:
            seconds: Duration in seconds

        Returns:
            ROS2Duration instance
        """
        return ROS2Duration.from_sec(seconds)

    def set_sim_time(self, ros_time: Union[ROS2Time, Dict[str, int], Any]) -> None:
        """Set simulation time from /clock topic.

        Args:
            ros_time: Current simulation time
        """
        if not isinstance(ros_time, ROS2Time):
            ros_time = ROS2Time.from_msg(ros_time)
        self._sim_time = ros_time
        self._use_sim_time = True

    def get_time(self) -> ROS2Time:
        """Get current time (system or simulation).

        Returns:
            Current ROS2Time
        """
        if self._use_sim_time and self._sim_time is not None:
            return self._sim_time
        return ROS2Time.from_sec(time.time())

    def now(self) -> ChronoStamp:
        """Get current time as ChronoStamp.

        Returns:
            ChronoStamp with current time
        """
        return self.ros2_to_chrono(self.get_time())


def ros2_time_to_chrono(
    sec: int,
    nanosec: int,
    frame_id: str = "base_link",
    uncertainty: float = 1e-6,
) -> ChronoStamp:
    """Convenience function to convert ROS2 time components to ChronoStamp.

    Args:
        sec: Seconds component
        nanosec: Nanoseconds component
        frame_id: Frame ID
        uncertainty: Time uncertainty

    Returns:
        ChronoStamp instance
    """
    t = sec + nanosec * 1e-9
    return ChronoStamp(
        frame_id=frame_id,
        t=t,
        t_uncertainty=uncertainty,
        clock_id="ros2",
        clock_class="ros2",
    )


def chrono_to_ros2_time(stamp: ChronoStamp) -> Tuple[int, int]:
    """Convenience function to convert ChronoStamp to ROS2 time components.

    Args:
        stamp: ChronoStamp instance

    Returns:
        Tuple of (sec, nanosec)
    """
    ros_time = ROS2Time.from_sec(stamp.t)
    return (ros_time.sec, ros_time.nanosec)


def parse_ros2_timestamp(timestamp_str: str) -> ROS2Time:
    """Parse ROS2 timestamp string.

    Handles formats like:
    - "1234567890.123456789"
    - "sec: 1234567890, nanosec: 123456789"
    - ISO 8601 datetime strings

    Args:
        timestamp_str: Timestamp string

    Returns:
        ROS2Time instance
    """
    timestamp_str = timestamp_str.strip()

    # Try float format
    try:
        return ROS2Time.from_sec(float(timestamp_str))
    except ValueError:
        pass

    # Try sec/nanosec format
    if "sec:" in timestamp_str.lower():
        import re
        sec_match = re.search(r"sec:\s*(\d+)", timestamp_str)
        nanosec_match = re.search(r"nanosec:\s*(\d+)", timestamp_str)
        if sec_match:
            sec = int(sec_match.group(1))
            nanosec = int(nanosec_match.group(1)) if nanosec_match else 0
            return ROS2Time(sec=sec, nanosec=nanosec)

    # Try ISO 8601
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return ROS2Time.from_sec(dt.timestamp())
    except ValueError:
        pass

    raise ValueError(f"Cannot parse ROS2 timestamp: {timestamp_str}")


def format_ros2_timestamp(
    ros_time: ROS2Time,
    format: str = "float",
) -> str:
    """Format ROS2 timestamp as string.

    Args:
        ros_time: ROS2Time instance
        format: Output format ("float", "components", "iso8601")

    Returns:
        Formatted timestamp string
    """
    if format == "float":
        return f"{ros_time.to_sec():.9f}"
    elif format == "components":
        return f"sec: {ros_time.sec}, nanosec: {ros_time.nanosec}"
    elif format == "iso8601":
        dt = datetime.fromtimestamp(ros_time.to_sec(), tz=timezone.utc)
        return dt.isoformat()
    else:
        raise ValueError(f"Unknown format: {format}")
