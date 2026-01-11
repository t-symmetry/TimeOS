"""HDF5 temporal metadata conventions.

Provides functions for reading and writing temporal metadata
in HDF5 files following standard conventions.

Supports:
- Timestamps as datasets with uncertainty attributes
- Time coordinate arrays with units and calendar
- Provenance tracking in HDF5 attributes
- Integration with TimeOS ChronoStamp

Requires: h5py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from timeos.msgs import ChronoStamp


class TimeUnit(Enum):
    """Time units for HDF5 temporal data."""
    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    MICROSECONDS = "microseconds"
    NANOSECONDS = "nanoseconds"
    DAYS = "days"
    HOURS = "hours"
    MINUTES = "minutes"


class Calendar(Enum):
    """Calendar conventions."""
    STANDARD = "standard"         # Mixed Gregorian/Julian
    GREGORIAN = "gregorian"       # Proleptic Gregorian
    PROLEPTIC_GREGORIAN = "proleptic_gregorian"
    JULIAN = "julian"
    NOLEAP = "noleap"             # 365-day years
    ALL_LEAP = "all_leap"         # 366-day years


@dataclass
class TemporalMetadata:
    """Temporal metadata for an HDF5 dataset.

    Attributes:
        units: Time units string (e.g., "seconds since 1970-01-01")
        calendar: Calendar convention
        uncertainty: Global uncertainty for all timestamps
        clock_id: Source clock identifier
        frame_id: Reference frame identifier
        provenance: List of source identifiers
    """
    units: str = "seconds since 1970-01-01 00:00:00 UTC"
    calendar: Calendar = Calendar.STANDARD
    uncertainty: float = 0.0
    clock_id: str = ""
    frame_id: str = ""
    provenance: List[str] = None

    def __post_init__(self):
        if self.provenance is None:
            self.provenance = []

    def to_attrs(self) -> Dict[str, Any]:
        """Convert to HDF5 attribute dictionary."""
        attrs = {
            "units": self.units,
            "calendar": self.calendar.value,
        }

        if self.uncertainty > 0:
            attrs["uncertainty"] = self.uncertainty
            attrs["uncertainty_units"] = self._get_base_unit()

        if self.clock_id:
            attrs["clock_id"] = self.clock_id

        if self.frame_id:
            attrs["frame_id"] = self.frame_id

        if self.provenance:
            attrs["provenance"] = ",".join(self.provenance)

        return attrs

    @classmethod
    def from_attrs(cls, attrs: Dict[str, Any]) -> "TemporalMetadata":
        """Create from HDF5 attributes."""
        calendar_str = attrs.get("calendar", "standard")
        try:
            calendar = Calendar(calendar_str)
        except ValueError:
            calendar = Calendar.STANDARD

        provenance = []
        prov_str = attrs.get("provenance", "")
        if prov_str:
            provenance = prov_str.split(",")

        return cls(
            units=attrs.get("units", "seconds since 1970-01-01 00:00:00 UTC"),
            calendar=calendar,
            uncertainty=float(attrs.get("uncertainty", 0.0)),
            clock_id=str(attrs.get("clock_id", "")),
            frame_id=str(attrs.get("frame_id", "")),
            provenance=provenance,
        )

    def _get_base_unit(self) -> str:
        """Get base time unit from units string."""
        units_lower = self.units.lower()
        for unit in TimeUnit:
            if units_lower.startswith(unit.value):
                return unit.value
        return "seconds"


def parse_time_units(units: str) -> Tuple[TimeUnit, datetime]:
    """Parse CF-style time units string.

    Args:
        units: Units string like "seconds since 1970-01-01 00:00:00"

    Returns:
        Tuple of (time_unit, reference_datetime)
    """
    parts = units.split(" since ")
    if len(parts) != 2:
        raise ValueError(f"Invalid time units format: {units}")

    unit_str = parts[0].lower().strip()
    ref_str = parts[1].strip()

    # Parse unit
    unit = TimeUnit.SECONDS
    for tu in TimeUnit:
        if unit_str.startswith(tu.value):
            unit = tu
            break

    # Parse reference time
    # Handle various formats
    ref_str = ref_str.replace("T", " ").replace("Z", "")
    ref_str = ref_str.split("+")[0]  # Remove timezone offset

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ]

    ref_dt = None
    for fmt in formats:
        try:
            ref_dt = datetime.strptime(ref_str.strip(), fmt)
            ref_dt = ref_dt.replace(tzinfo=timezone.utc)
            break
        except ValueError:
            continue

    if ref_dt is None:
        ref_dt = datetime(1970, 1, 1, tzinfo=timezone.utc)

    return unit, ref_dt


def time_to_numeric(
    dt: datetime,
    units: str = "seconds since 1970-01-01 00:00:00 UTC",
) -> float:
    """Convert datetime to numeric value according to units.

    Args:
        dt: Datetime to convert
        units: Target units string

    Returns:
        Numeric time value
    """
    unit, ref_dt = parse_time_units(units)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = dt - ref_dt
    seconds = delta.total_seconds()

    if unit == TimeUnit.SECONDS:
        return seconds
    elif unit == TimeUnit.MILLISECONDS:
        return seconds * 1000
    elif unit == TimeUnit.MICROSECONDS:
        return seconds * 1e6
    elif unit == TimeUnit.NANOSECONDS:
        return seconds * 1e9
    elif unit == TimeUnit.DAYS:
        return seconds / 86400
    elif unit == TimeUnit.HOURS:
        return seconds / 3600
    elif unit == TimeUnit.MINUTES:
        return seconds / 60
    else:
        return seconds


def numeric_to_time(
    value: float,
    units: str = "seconds since 1970-01-01 00:00:00 UTC",
) -> datetime:
    """Convert numeric value to datetime according to units.

    Args:
        value: Numeric time value
        units: Source units string

    Returns:
        Datetime value
    """
    from datetime import timedelta

    unit, ref_dt = parse_time_units(units)

    if unit == TimeUnit.SECONDS:
        seconds = value
    elif unit == TimeUnit.MILLISECONDS:
        seconds = value / 1000
    elif unit == TimeUnit.MICROSECONDS:
        seconds = value / 1e6
    elif unit == TimeUnit.NANOSECONDS:
        seconds = value / 1e9
    elif unit == TimeUnit.DAYS:
        seconds = value * 86400
    elif unit == TimeUnit.HOURS:
        seconds = value * 3600
    elif unit == TimeUnit.MINUTES:
        seconds = value * 60
    else:
        seconds = value

    return ref_dt + timedelta(seconds=seconds)


def write_time_dataset(
    h5file: Any,
    name: str,
    times: List[float],
    metadata: Optional[TemporalMetadata] = None,
    uncertainties: Optional[List[float]] = None,
    compression: Optional[str] = "gzip",
) -> Any:
    """Write a time coordinate dataset to HDF5.

    Args:
        h5file: Open HDF5 file or group
        name: Dataset name
        times: Time values
        metadata: Temporal metadata
        uncertainties: Per-value uncertainties (optional)
        compression: Compression filter (None, 'gzip', 'lzf')

    Returns:
        Created HDF5 dataset
    """
    import numpy as np

    if metadata is None:
        metadata = TemporalMetadata()

    # Create main time dataset
    kwargs = {}
    if compression:
        kwargs["compression"] = compression

    ds = h5file.create_dataset(name, data=np.array(times, dtype=np.float64), **kwargs)

    # Add metadata attributes
    for key, value in metadata.to_attrs().items():
        ds.attrs[key] = value

    # Add uncertainties as a separate dataset if provided
    if uncertainties:
        unc_ds = h5file.create_dataset(
            f"{name}_uncertainty",
            data=np.array(uncertainties, dtype=np.float64),
            **kwargs
        )
        unc_ds.attrs["units"] = metadata._get_base_unit()
        unc_ds.attrs["long_name"] = f"Uncertainty in {name}"

        # Link from main dataset
        ds.attrs["uncertainty_dataset"] = f"{name}_uncertainty"

    return ds


def read_time_dataset(
    h5file: Any,
    name: str,
) -> Tuple[List[float], TemporalMetadata, Optional[List[float]]]:
    """Read a time coordinate dataset from HDF5.

    Args:
        h5file: Open HDF5 file or group
        name: Dataset name

    Returns:
        Tuple of (times, metadata, uncertainties)
    """
    ds = h5file[name]
    times = list(ds[:])

    # Read metadata
    metadata = TemporalMetadata.from_attrs(dict(ds.attrs))

    # Try to read uncertainties
    uncertainties = None
    unc_name = ds.attrs.get("uncertainty_dataset", f"{name}_uncertainty")
    if unc_name in h5file:
        uncertainties = list(h5file[unc_name][:])

    return times, metadata, uncertainties


def write_events_hdf5(
    h5file: Any,
    events: List[Any],
    group_name: str = "events",
) -> None:
    """Write TimeOS events to HDF5.

    Args:
        h5file: Open HDF5 file
        events: List of TimelineEvent objects
        group_name: Group name for events
    """
    import numpy as np

    if group_name in h5file:
        del h5file[group_name]

    grp = h5file.create_group(group_name)

    # Extract data arrays
    event_ids = [e.event_id for e in events]
    times = [e.stamp.t for e in events]
    uncertainties = [e.stamp.t_uncertainty for e in events]
    frame_ids = [e.stamp.frame_id for e in events]
    branch_ids = [e.branch_id for e in events]
    event_types = [e.event_type for e in events]
    authors = [e.author or "" for e in events]

    # Write datasets
    dt = np.dtype('S64')  # Fixed-length strings

    grp.create_dataset("event_id", data=np.array(event_ids, dtype=dt))
    grp.create_dataset("time", data=np.array(times, dtype=np.float64))
    grp.create_dataset("time_uncertainty", data=np.array(uncertainties, dtype=np.float64))
    grp.create_dataset("frame_id", data=np.array(frame_ids, dtype=dt))
    grp.create_dataset("branch_id", data=np.array(branch_ids, dtype=dt))
    grp.create_dataset("event_type", data=np.array(event_types, dtype=dt))
    grp.create_dataset("author", data=np.array(authors, dtype=dt))

    # Add group-level metadata
    grp.attrs["count"] = len(events)
    grp.attrs["format_version"] = "1.0"
    grp.attrs["created"] = datetime.now(tz=timezone.utc).isoformat()


def read_events_hdf5(
    h5file: Any,
    group_name: str = "events",
) -> List[Dict[str, Any]]:
    """Read events from HDF5.

    Args:
        h5file: Open HDF5 file
        group_name: Group name for events

    Returns:
        List of event dictionaries
    """
    if group_name not in h5file:
        return []

    grp = h5file[group_name]

    events = []
    n = grp.attrs.get("count", len(grp["event_id"]))

    for i in range(n):
        event = {
            "event_id": grp["event_id"][i].decode() if hasattr(grp["event_id"][i], 'decode') else grp["event_id"][i],
            "t": float(grp["time"][i]),
            "t_uncertainty": float(grp["time_uncertainty"][i]),
            "frame_id": grp["frame_id"][i].decode() if hasattr(grp["frame_id"][i], 'decode') else grp["frame_id"][i],
            "branch_id": grp["branch_id"][i].decode() if hasattr(grp["branch_id"][i], 'decode') else grp["branch_id"][i],
            "event_type": grp["event_type"][i].decode() if hasattr(grp["event_type"][i], 'decode') else grp["event_type"][i],
            "author": grp["author"][i].decode() if hasattr(grp["author"][i], 'decode') else grp["author"][i],
        }
        events.append(event)

    return events


def chrono_stamp_to_hdf5_attrs(
    stamp: "ChronoStamp",
    prefix: str = "time_",
) -> Dict[str, Any]:
    """Convert ChronoStamp to HDF5 attributes.

    Args:
        stamp: ChronoStamp to convert
        prefix: Prefix for attribute names

    Returns:
        Dictionary of HDF5 attributes
    """
    return {
        f"{prefix}value": stamp.t,
        f"{prefix}uncertainty": stamp.t_uncertainty,
        f"{prefix}frame_id": stamp.frame_id,
        f"{prefix}clock_id": stamp.clock_id,
        f"{prefix}clock_class": stamp.clock_class,
        f"{prefix}units": "seconds since 1970-01-01 00:00:00 UTC",
    }


def hdf5_attrs_to_chrono_stamp(
    attrs: Dict[str, Any],
    prefix: str = "time_",
) -> "ChronoStamp":
    """Convert HDF5 attributes to ChronoStamp.

    Args:
        attrs: HDF5 attributes dictionary
        prefix: Prefix for attribute names

    Returns:
        ChronoStamp instance
    """
    from timeos.msgs import ChronoStamp

    return ChronoStamp(
        frame_id=str(attrs.get(f"{prefix}frame_id", "default")),
        t=float(attrs.get(f"{prefix}value", 0.0)),
        t_uncertainty=float(attrs.get(f"{prefix}uncertainty", 0.0)),
        clock_id=str(attrs.get(f"{prefix}clock_id", "")),
        clock_class=str(attrs.get(f"{prefix}clock_class", "sim")),
    )
