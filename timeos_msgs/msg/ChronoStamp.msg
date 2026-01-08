# ChronoStamp - A timestamp with uncertainty bounds and provenance
#
# Represents a point in time within a specific reference frame,
# with explicit uncertainty and source tracking.

# Reference frame identifier (e.g., "earth_tai", "lab_clock_a")
string frame_id

# Time coordinate in the reference frame (seconds since frame epoch)
float64 t

# Uncertainty bounds +/- (seconds)
float64 t_uncertainty 0.0

# Identifier of the source clock
string clock_id

# Type of clock: "atomic", "ntp", "gps", "proper", "sim", "inferred"
string clock_class "sim"

# Event IDs used to derive this timestamp (for provenance tracking)
string[] provenance
