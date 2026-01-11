"""SMPTE timecode format.

Supports SMPTE 12M timecodes used in film, video, and broadcast.
Handles both drop-frame and non-drop-frame formats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class SMPTEFrameRate(Enum):
    """Standard SMPTE frame rates."""
    FPS_24 = (24, 1, False)      # Film
    FPS_25 = (25, 1, False)      # PAL
    FPS_30 = (30, 1, False)      # NTSC non-drop
    FPS_30_DF = (30000, 1001, True)  # NTSC drop-frame (29.97 fps)
    FPS_60 = (60, 1, False)      # High frame rate
    FPS_60_DF = (60000, 1001, True)  # 59.94 drop-frame

    def __init__(self, num: int, denom: int, drop_frame: bool):
        self.numerator = num
        self.denominator = denom
        self.drop_frame = drop_frame

    @property
    def fps(self) -> float:
        """Frames per second as float."""
        return self.numerator / self.denominator

    @property
    def frame_duration(self) -> float:
        """Duration of one frame in seconds."""
        return self.denominator / self.numerator


@dataclass
class SMPTETimecode:
    """SMPTE timecode representation.

    Attributes:
        hours: Hours (0-23)
        minutes: Minutes (0-59)
        seconds: Seconds (0-59)
        frames: Frames (0 to fps-1)
        frame_rate: Frame rate
        drop_frame: Whether drop-frame counting is used
    """
    hours: int
    minutes: int
    seconds: int
    frames: int
    frame_rate: SMPTEFrameRate = SMPTEFrameRate.FPS_30

    def __post_init__(self):
        """Validate timecode values."""
        if not 0 <= self.hours <= 23:
            raise ValueError(f"Hours must be 0-23, got {self.hours}")
        if not 0 <= self.minutes <= 59:
            raise ValueError(f"Minutes must be 0-59, got {self.minutes}")
        if not 0 <= self.seconds <= 59:
            raise ValueError(f"Seconds must be 0-59, got {self.seconds}")

        max_frames = int(self.frame_rate.fps)
        if not 0 <= self.frames < max_frames:
            raise ValueError(f"Frames must be 0-{max_frames-1}, got {self.frames}")

    @property
    def drop_frame(self) -> bool:
        """Whether this timecode uses drop-frame counting."""
        return self.frame_rate.drop_frame

    def to_seconds(self) -> float:
        """Convert to seconds from midnight.

        For drop-frame timecodes, this accounts for dropped frames
        to give wall-clock time.
        """
        # Total frames (not accounting for drops yet)
        fps = int(self.frame_rate.fps)
        total_frames = (
            self.hours * 3600 * fps +
            self.minutes * 60 * fps +
            self.seconds * fps +
            self.frames
        )

        if self.drop_frame:
            # Drop-frame: 2 frames are skipped at the start of each minute,
            # except every 10th minute
            # This compensates for 29.97 fps vs 30 fps

            # Count total minutes (not counting 10-minute marks)
            total_minutes = self.hours * 60 + self.minutes

            # Frames dropped = 2 * (total_minutes - floor(total_minutes/10))
            ten_minute_periods = total_minutes // 10
            frames_dropped = 2 * (total_minutes - ten_minute_periods)

            # Actual frame count
            actual_frames = total_frames - frames_dropped

            return actual_frames * self.frame_rate.frame_duration
        else:
            return total_frames * self.frame_rate.frame_duration

    def to_frame_number(self) -> int:
        """Convert to absolute frame number from midnight."""
        fps = int(self.frame_rate.fps)
        total_frames = (
            self.hours * 3600 * fps +
            self.minutes * 60 * fps +
            self.seconds * fps +
            self.frames
        )

        if self.drop_frame:
            total_minutes = self.hours * 60 + self.minutes
            ten_minute_periods = total_minutes // 10
            frames_dropped = 2 * (total_minutes - ten_minute_periods)
            return total_frames - frames_dropped

        return total_frames

    @classmethod
    def from_seconds(
        cls,
        seconds: float,
        frame_rate: SMPTEFrameRate = SMPTEFrameRate.FPS_30,
    ) -> SMPTETimecode:
        """Create timecode from seconds.

        Args:
            seconds: Seconds from midnight
            frame_rate: Frame rate to use

        Returns:
            SMPTETimecode instance
        """
        if seconds < 0:
            raise ValueError("Seconds must be non-negative")

        fps = int(frame_rate.fps)

        if frame_rate.drop_frame:
            # For drop-frame, we need to calculate considering dropped frames
            frame_duration = frame_rate.frame_duration
            total_frames = int(seconds / frame_duration)

            # Add back dropped frames to get timecode frames
            # Every minute (except every 10th) drops 2 frames
            # 30 fps: 1800 frames/min nominal, 1798 actual
            # Every 10 minutes: 17982 actual frames

            D = 2  # Frames dropped per minute
            M = fps * 60 - D  # Actual frames per minute (1798)
            M10 = fps * 60 * 10 - D * 9  # Actual frames per 10 minutes (17982)

            # How many complete 10-minute periods?
            ten_min_periods = total_frames // M10
            remaining = total_frames % M10

            # How many complete minutes in the remaining?
            if remaining < fps * 60:
                # First minute of 10-minute period (no drop)
                minutes_in_period = 0
                frames_in_minute = remaining
            else:
                # Subsequent minutes drop frames
                remaining -= fps * 60
                minutes_in_period = 1 + remaining // M
                frames_in_minute = remaining % M

                # Account for the dropped frames at minute boundary
                if frames_in_minute < D:
                    frames_in_minute += D

            total_minutes = ten_min_periods * 10 + minutes_in_period

            hours = total_minutes // 60
            minutes = total_minutes % 60
            seconds_val = frames_in_minute // fps
            frames = frames_in_minute % fps

        else:
            # Non-drop-frame: straightforward calculation
            total_frames = int(seconds / frame_rate.frame_duration)

            frames_per_second = fps
            frames_per_minute = frames_per_second * 60
            frames_per_hour = frames_per_minute * 60

            hours = total_frames // frames_per_hour
            total_frames %= frames_per_hour

            minutes = total_frames // frames_per_minute
            total_frames %= frames_per_minute

            seconds_val = total_frames // frames_per_second
            frames = total_frames % frames_per_second

        return cls(
            hours=hours,
            minutes=minutes,
            seconds=seconds_val,
            frames=frames,
            frame_rate=frame_rate,
        )

    @classmethod
    def from_frame_number(
        cls,
        frame_number: int,
        frame_rate: SMPTEFrameRate = SMPTEFrameRate.FPS_30,
    ) -> SMPTETimecode:
        """Create timecode from absolute frame number."""
        seconds = frame_number * frame_rate.frame_duration
        return cls.from_seconds(seconds, frame_rate)


def format_smpte(
    tc: SMPTETimecode,
    include_frame_rate: bool = False,
) -> str:
    """Format SMPTE timecode as string.

    Args:
        tc: Timecode to format
        include_frame_rate: Include @fps suffix

    Returns:
        Formatted timecode string (e.g., "01:23:45:12" or "01:23:45;12" for DF)
    """
    # Use semicolon separator for drop-frame
    sep = ";" if tc.drop_frame else ":"

    result = f"{tc.hours:02d}:{tc.minutes:02d}:{tc.seconds:02d}{sep}{tc.frames:02d}"

    if include_frame_rate:
        if tc.drop_frame:
            result += f"@{tc.frame_rate.fps:.2f}DF"
        else:
            result += f"@{int(tc.frame_rate.fps)}"

    return result


def parse_smpte(
    s: str,
    default_frame_rate: SMPTEFrameRate = SMPTEFrameRate.FPS_30,
) -> SMPTETimecode:
    """Parse SMPTE timecode string.

    Args:
        s: Timecode string (e.g., "01:23:45:12" or "01:23:45;12")
        default_frame_rate: Frame rate if not specified

    Returns:
        SMPTETimecode instance

    Raises:
        ValueError: If string is not valid timecode
    """
    # Pattern: HH:MM:SS:FF or HH:MM:SS;FF (optionally with @fps)
    pattern = r"^(\d{1,2}):(\d{2}):(\d{2})([;:])(\d{2})(?:@([0-9.]+)(DF)?)?$"
    match = re.match(pattern, s.strip())

    if not match:
        raise ValueError(f"Invalid SMPTE timecode: {s}")

    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    separator = match.group(4)
    frames = int(match.group(5))

    # Determine frame rate
    frame_rate = default_frame_rate

    if match.group(6):
        fps = float(match.group(6))
        is_df = match.group(7) == "DF" or separator == ";"

        # Match to known frame rates
        if abs(fps - 24) < 0.1:
            frame_rate = SMPTEFrameRate.FPS_24
        elif abs(fps - 25) < 0.1:
            frame_rate = SMPTEFrameRate.FPS_25
        elif abs(fps - 30) < 0.1 or abs(fps - 29.97) < 0.1:
            frame_rate = SMPTEFrameRate.FPS_30_DF if is_df else SMPTEFrameRate.FPS_30
        elif abs(fps - 60) < 0.1 or abs(fps - 59.94) < 0.1:
            frame_rate = SMPTEFrameRate.FPS_60_DF if is_df else SMPTEFrameRate.FPS_60
    elif separator == ";":
        # Semicolon implies drop-frame
        if frame_rate == SMPTEFrameRate.FPS_30:
            frame_rate = SMPTEFrameRate.FPS_30_DF
        elif frame_rate == SMPTEFrameRate.FPS_60:
            frame_rate = SMPTEFrameRate.FPS_60_DF

    return SMPTETimecode(
        hours=hours,
        minutes=minutes,
        seconds=seconds,
        frames=frames,
        frame_rate=frame_rate,
    )


def smpte_to_seconds(s: str) -> float:
    """Convert SMPTE timecode string to seconds.

    Args:
        s: Timecode string

    Returns:
        Seconds from midnight
    """
    tc = parse_smpte(s)
    return tc.to_seconds()


def seconds_to_smpte(
    seconds: float,
    frame_rate: SMPTEFrameRate = SMPTEFrameRate.FPS_30,
) -> str:
    """Convert seconds to SMPTE timecode string.

    Args:
        seconds: Seconds from midnight
        frame_rate: Frame rate to use

    Returns:
        SMPTE timecode string
    """
    tc = SMPTETimecode.from_seconds(seconds, frame_rate)
    return format_smpte(tc)
