# TemporalFrame - Reference frame for temporal measurements
# Defines the coordinate system for events and measurements

string frame_id                        # Unique frame identifier
string parent_frame_id                 # Parent frame (empty for root)
ChronoStamp origin                     # Origin timestamp

# 4-velocity of frame relative to parent (c=1 units)
float64 velocity_x
float64 velocity_y
float64 velocity_z
float64 velocity_t                     # Should be gamma for timelike

# Frame metadata
float64 gamma                          # Lorentz factor
float64 beta                           # v/c ratio
bool is_inertial                       # True if non-accelerating
string description                     # Human-readable description
