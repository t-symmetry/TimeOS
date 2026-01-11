"""ISO 8601 time format with uncertainty extensions.

Extends standard ISO 8601 with uncertainty notation:
    2024-01-15T10:30:00.000±0.001Z    # ±1ms uncertainty
    2024-01-15T10:30:00.000[TAI]       # Explicit time scale
    2024-01-15T10:30:00.000±0.001[GPS] # Both uncertainty and scale
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from enum import Enum


class TimeScale(Enum):
    """Time scale indicators."""
    UTC = "UTC"
    TAI = "TAI"   # International Atomic Time (UTC + leap seconds)
    GPS = "GPS"   # GPS Time (TAI - 19 seconds)
    TT = "TT"     # Terrestrial Time (TAI + 32.184s)
    LOCAL = "LOCAL"


@dataclass
class ISO8601Options:
    """Options for ISO 8601 formatting.

    Attributes:
        include_uncertainty: Include ± uncertainty notation
        include_scale: Include [SCALE] suffix
        precision: Decimal places for seconds (0-9)
        use_Z_suffix: Use Z for UTC (vs +00:00)
        compact: Omit separators (T, -, :)
    """
    include_uncertainty: bool = True
    include_scale: bool = False
    precision: int = 3
    use_Z_suffix: bool = True
    compact: bool = False


@dataclass
class ParsedTime:
    """Result of parsing an ISO 8601 string.

    Attributes:
        datetime: Parsed datetime (always UTC)
        uncertainty: Uncertainty in seconds (0 if not specified)
        scale: Time scale (UTC if not specified)
        original: Original string
    """
    datetime: datetime
    uncertainty: float = 0.0
    scale: TimeScale = TimeScale.UTC
    original: str = ""

    @property
    def timestamp(self) -> float:
        """Get Unix timestamp."""
        return self.datetime.timestamp()


# Regex patterns for parsing
ISO8601_PATTERN = re.compile(
    r"^(\d{4})-?(\d{2})-?(\d{2})"  # Date: YYYY-MM-DD or YYYYMMDD
    r"[T ]?"                        # Optional T or space separator
    r"(\d{2}):?(\d{2}):?(\d{2})"   # Time: HH:MM:SS or HHMMSS
    r"(?:\.(\d+))?"                # Optional fractional seconds
    r"(?:([+-])(\d{2}):?(\d{2})|Z)?"  # Optional timezone
    r"(?:±([0-9.]+))?"             # Optional uncertainty
    r"(?:\[([A-Z]+)\])?"           # Optional scale
    r"$"
)

UNCERTAINTY_PATTERN = re.compile(r"±([0-9.]+(?:[eE][+-]?\d+)?)")
SCALE_PATTERN = re.compile(r"\[([A-Z]+)\]")


def format_iso8601(
    dt: datetime,
    options: Optional[ISO8601Options] = None,
) -> str:
    """Format datetime as ISO 8601 string.

    Args:
        dt: Datetime to format
        options: Formatting options

    Returns:
        ISO 8601 formatted string
    """
    if options is None:
        options = ISO8601Options()

    # Ensure UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    # Build format string
    if options.precision > 0:
        # Include fractional seconds
        microseconds = dt.microsecond
        frac = f".{microseconds:06d}"[:options.precision + 1]
        base = dt.strftime("%Y-%m-%dT%H:%M:%S") + frac
    else:
        base = dt.strftime("%Y-%m-%dT%H:%M:%S")

    if options.use_Z_suffix:
        base += "Z"
    else:
        base += "+00:00"

    if options.compact:
        base = base.replace("-", "").replace(":", "").replace("T", "")

    return base


def format_iso8601_with_uncertainty(
    dt: datetime,
    uncertainty: float,
    scale: TimeScale = TimeScale.UTC,
    options: Optional[ISO8601Options] = None,
) -> str:
    """Format datetime with uncertainty as extended ISO 8601.

    Args:
        dt: Datetime to format
        uncertainty: Uncertainty in seconds
        scale: Time scale
        options: Formatting options

    Returns:
        Extended ISO 8601 string with uncertainty

    Example:
        >>> format_iso8601_with_uncertainty(
        ...     datetime(2024, 1, 15, 10, 30, 0),
        ...     uncertainty=0.001,
        ...     scale=TimeScale.UTC
        ... )
        '2024-01-15T10:30:00.000±0.001Z'
    """
    if options is None:
        options = ISO8601Options(include_uncertainty=True, include_scale=True)

    base = format_iso8601(dt, ISO8601Options(
        precision=options.precision,
        use_Z_suffix=False,  # We'll add it or scale suffix
        compact=options.compact,
    ))

    result = base

    # Add uncertainty if requested
    if options.include_uncertainty and uncertainty > 0:
        # Format uncertainty to appropriate precision
        if uncertainty >= 1:
            unc_str = f"±{uncertainty:.1f}"
        elif uncertainty >= 0.001:
            unc_str = f"±{uncertainty:.3f}"
        elif uncertainty >= 0.000001:
            unc_str = f"±{uncertainty:.6f}"
        else:
            unc_str = f"±{uncertainty:.9f}"
        result += unc_str

    # Add timezone/scale suffix
    if options.include_scale and scale != TimeScale.UTC:
        result += f"[{scale.value}]"
    elif options.use_Z_suffix:
        result += "Z"
    else:
        result += "+00:00"

    return result


def parse_iso8601(s: str) -> datetime:
    """Parse ISO 8601 string to datetime.

    Args:
        s: ISO 8601 formatted string

    Returns:
        Parsed datetime (UTC)

    Raises:
        ValueError: If string is not valid ISO 8601
    """
    result = parse_iso8601_with_uncertainty(s)
    return result.datetime


def parse_iso8601_with_uncertainty(s: str) -> ParsedTime:
    """Parse extended ISO 8601 string with uncertainty.

    Args:
        s: ISO 8601 string (optionally with ± and [SCALE])

    Returns:
        ParsedTime with datetime, uncertainty, and scale

    Raises:
        ValueError: If string is not valid
    """
    original = s

    # Extract uncertainty
    uncertainty = 0.0
    unc_match = UNCERTAINTY_PATTERN.search(s)
    if unc_match:
        uncertainty = float(unc_match.group(1))
        s = s[:unc_match.start()] + s[unc_match.end():]

    # Extract scale
    scale = TimeScale.UTC
    scale_match = SCALE_PATTERN.search(s)
    if scale_match:
        scale_str = scale_match.group(1)
        try:
            scale = TimeScale(scale_str)
        except ValueError:
            scale = TimeScale.UTC
        s = s[:scale_match.start()] + s[scale_match.end():]

    # Parse the core ISO 8601 part
    match = ISO8601_PATTERN.match(s)
    if not match:
        # Try standard library as fallback
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return ParsedTime(
                datetime=dt.astimezone(timezone.utc),
                uncertainty=uncertainty,
                scale=scale,
                original=original,
            )
        except ValueError:
            raise ValueError(f"Invalid ISO 8601 format: {original}")

    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    hour = int(match.group(4))
    minute = int(match.group(5))
    second = int(match.group(6))

    # Fractional seconds
    microsecond = 0
    if match.group(7):
        frac = match.group(7)
        # Pad or truncate to 6 digits
        frac = (frac + "000000")[:6]
        microsecond = int(frac)

    # Timezone
    tz = timezone.utc
    if match.group(8):  # Has explicit offset
        sign = 1 if match.group(8) == "+" else -1
        tz_hours = int(match.group(9))
        tz_minutes = int(match.group(10))
        offset = timedelta(hours=tz_hours, minutes=tz_minutes)
        tz = timezone(sign * offset)

    dt = datetime(year, month, day, hour, minute, second, microsecond, tzinfo=tz)
    dt = dt.astimezone(timezone.utc)

    return ParsedTime(
        datetime=dt,
        uncertainty=uncertainty,
        scale=scale,
        original=original,
    )


def convert_to_scale(
    dt: datetime,
    from_scale: TimeScale,
    to_scale: TimeScale,
) -> datetime:
    """Convert datetime between time scales.

    Args:
        dt: Datetime to convert
        from_scale: Source time scale
        to_scale: Target time scale

    Returns:
        Converted datetime

    Note:
        This is approximate. For precise conversions, use
        a proper time scale library like astropy.time.
    """
    if from_scale == to_scale:
        return dt

    # Convert to TAI first (as reference)
    # Leap seconds: UTC is behind TAI by ~37 seconds as of 2024
    LEAP_SECONDS = 37

    if from_scale == TimeScale.UTC:
        tai_offset = LEAP_SECONDS
    elif from_scale == TimeScale.TAI:
        tai_offset = 0
    elif from_scale == TimeScale.GPS:
        tai_offset = 19  # GPS = TAI - 19s
    elif from_scale == TimeScale.TT:
        tai_offset = -32.184  # TT = TAI + 32.184s
    else:
        tai_offset = 0

    dt_tai = dt + timedelta(seconds=tai_offset)

    # Convert from TAI to target
    if to_scale == TimeScale.UTC:
        target_offset = -LEAP_SECONDS
    elif to_scale == TimeScale.TAI:
        target_offset = 0
    elif to_scale == TimeScale.GPS:
        target_offset = -19
    elif to_scale == TimeScale.TT:
        target_offset = 32.184
    else:
        target_offset = 0

    return dt_tai + timedelta(seconds=target_offset)


def format_duration_iso8601(seconds: float) -> str:
    """Format a duration in ISO 8601 duration format.

    Args:
        seconds: Duration in seconds

    Returns:
        ISO 8601 duration string (e.g., "PT1H30M15S")
    """
    if seconds < 0:
        prefix = "-"
        seconds = abs(seconds)
    else:
        prefix = ""

    hours = int(seconds // 3600)
    seconds %= 3600
    minutes = int(seconds // 60)
    seconds %= 60

    parts = ["P"]

    if hours > 0 or minutes > 0 or seconds > 0:
        parts.append("T")

    if hours > 0:
        parts.append(f"{hours}H")
    if minutes > 0:
        parts.append(f"{minutes}M")
    if seconds > 0:
        if seconds == int(seconds):
            parts.append(f"{int(seconds)}S")
        else:
            parts.append(f"{seconds:.3f}S")

    result = "".join(parts)
    if result == "PT":
        result = "PT0S"

    return prefix + result


def parse_duration_iso8601(s: str) -> float:
    """Parse ISO 8601 duration to seconds.

    Args:
        s: ISO 8601 duration string

    Returns:
        Duration in seconds

    Raises:
        ValueError: If string is not valid duration
    """
    negative = s.startswith("-")
    if negative:
        s = s[1:]

    if not s.startswith("P"):
        raise ValueError(f"Invalid duration format: {s}")

    s = s[1:]

    # Handle date portion (days, months, years) - simplified
    days = 0
    if "D" in s.split("T")[0]:
        date_part = s.split("T")[0]
        day_match = re.search(r"(\d+)D", date_part)
        if day_match:
            days = int(day_match.group(1))

    # Handle time portion
    seconds = 0.0
    if "T" in s:
        time_part = s.split("T")[1]

        hour_match = re.search(r"(\d+)H", time_part)
        if hour_match:
            seconds += int(hour_match.group(1)) * 3600

        min_match = re.search(r"(\d+)M", time_part)
        if min_match:
            seconds += int(min_match.group(1)) * 60

        sec_match = re.search(r"([0-9.]+)S", time_part)
        if sec_match:
            seconds += float(sec_match.group(1))

    total = days * 86400 + seconds

    return -total if negative else total
