"""TimeOS - Time Operating System.

A modular framework for temporal event systems with causality constraints.
"""

__version__ = "0.1.0"

from timeos.msgs import ChronoStamp, TemporalFrame, TimelineEvent

__all__ = [
    "__version__",
    "ChronoStamp",
    "TemporalFrame",
    "TimelineEvent",
]
