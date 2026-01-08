# TemporalFrame - A temporal coordinate frame definition
#
# Defines a reference frame for temporal measurements, including
# the time standard, spatial reference, and validity period.

# Unique identifier for this frame
string frame_id

# Parent frame for hierarchical transforms (empty = root frame)
string parent_frame_id

# Time standard: "TAI", "UTC", "GPS", "TT", "proper_time", "sim"
string time_standard "TAI"

# Spatial reference system: "WGS84", "ICRF", "ECEF", "custom"
string spatial_reference "ICRF"

# Start of validity period (in parent frame time, -inf if not set)
float64 validity_start

# End of validity period (in parent frame time, +inf if not set)
float64 validity_end

# Confidence level for this frame definition (0.0-1.0)
float64 confidence 1.0

# Publisher/authority identity
string authority

# Metadata tags: "sim", "sensor", "inferred", "historical"
string[] tags
