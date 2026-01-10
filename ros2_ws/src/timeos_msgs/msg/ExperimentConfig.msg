# ExperimentConfig - Configuration for T-symmetry experiments

string experiment_id                   # Unique experiment identifier
string experiment_type                 # Type of experiment
string description                     # Human-readable description

# Experiment type constants
string TYPE_T_SYMMETRY = "t_symmetry"
string TYPE_CAUSALITY_TEST = "causality_test"
string TYPE_FIELD_REVERSAL = "field_reversal"
string TYPE_TEMPORAL_DRIFT = "temporal_drift"
string TYPE_CALIBRATION = "calibration"
string TYPE_CUSTOM = "custom"

# Timing
float64 duration_seconds               # Total experiment duration
float64 sample_rate_hz                 # Data acquisition rate
uint32 num_iterations                  # Number of repetitions

# Field parameters
float64 field_strength_tesla           # Target field strength
float64 field_ramp_rate                # Tesla/second
bool field_reversal                    # Include field reversal
float64 reversal_delay_sec             # Time between forward/reverse

# T-symmetry specific
float64 t_symmetry_window_sec          # Time window for symmetry analysis
float64 t_offset_sec                   # Temporal offset to probe
bool measure_forward                   # Measure forward direction
bool measure_backward                  # Measure backward direction

# Sensors to use
string[] sensor_ids                    # List of sensors to record
float64[] sensor_sample_rates          # Per-sensor sample rates

# Data recording
string output_directory                # Where to save data
string output_format                   # hdf5, csv, rosbag
bool compress_output                   # Compress output files

# Safety limits
float64 max_field_tesla                # Field limit
float64 max_temperature_kelvin         # Temperature limit
float64 max_causality_risk             # Risk threshold to abort

# Metadata
string operator                        # Who is running experiment
string[] tags                          # Tags for categorization
string notes                           # Additional notes
