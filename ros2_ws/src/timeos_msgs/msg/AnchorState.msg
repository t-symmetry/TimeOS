# AnchorState - Temporal anchor/reference status

builtin_interfaces/Time stamp

# Connection status
bool connected                         # Anchor lock acquired
bool locked                            # Stable lock achieved
float64 lock_quality                   # 0.0 to 1.0 (1.0 = perfect)

# Reference source
uint8 REF_NONE = 0
uint8 REF_INTERNAL = 1
uint8 REF_GPS = 2
uint8 REF_PTP = 3
uint8 REF_ATOMIC = 4
uint8 REF_EXTERNAL = 5
uint8 reference_source

# Timing metrics
float64 drift_ppm                      # Drift in parts per million
float64 jitter_ns                      # Jitter in nanoseconds
float64 offset_ns                      # Offset from reference in ns
float64 frequency_hz                   # Reference frequency

# GPS-specific (if applicable)
float64 latitude                       # Degrees
float64 longitude                      # Degrees
float64 altitude                       # Meters
uint8 satellites_visible               # GPS satellites in view
uint8 satellites_used                  # GPS satellites in solution

# Anchor point
ChronoStamp anchor_point               # The anchored temporal coordinate
string anchor_id                       # Anchor identifier
string anchor_description              # Human-readable description

# Status
bool pps_present                       # 1PPS signal detected
bool disciplined                       # Oscillator is disciplined
string fault_message                   # Empty if no fault
