# SensorReading - Generic sensor measurement for research
# Used for T-symmetry experiments and general instrumentation

builtin_interfaces/Time stamp
ChronoStamp chrono_stamp               # Temporal coordinate of measurement

# Sensor identification
string sensor_id                       # Unique sensor identifier
string sensor_type                     # Type (magnetometer, thermometer, etc.)
string channel                         # Channel or axis identifier

# Value
float64 value                          # Primary measurement value
float64 uncertainty                    # Measurement uncertainty (1-sigma)
string units                           # Physical units

# Vector reading (if applicable)
float64[] values                       # Multi-channel values
float64[] uncertainties                # Per-channel uncertainties
string[] labels                        # Per-channel labels

# Quality metrics
float64 snr_db                         # Signal-to-noise ratio (dB)
float64 confidence                     # 0.0 to 1.0
bool valid                             # Reading is valid

# Calibration
bool calibrated                        # Calibration applied
string calibration_id                  # Calibration reference
float64 calibration_age_sec            # Time since calibration

# Raw data (for debugging/analysis)
float64 raw_value                      # Pre-calibration value
int32 raw_counts                       # ADC counts (if applicable)

# Metadata
string experiment_id                   # Associated experiment
string notes                           # Additional notes
