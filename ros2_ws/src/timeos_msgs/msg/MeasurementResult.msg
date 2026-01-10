# MeasurementResult - Results from T-symmetry measurements

builtin_interfaces/Time stamp
string experiment_id                   # Associated experiment
string measurement_id                  # Unique measurement identifier

# T-symmetry analysis results
float64 t_symmetry_score               # -1.0 to 1.0 (0 = perfect symmetry)
float64 t_symmetry_uncertainty         # Uncertainty in score
float64 asymmetry_magnitude            # |forward - backward|
float64 asymmetry_significance         # Statistical significance (sigma)

# Direction comparison
float64 forward_value                  # Forward-time measurement
float64 forward_uncertainty
float64 backward_value                 # Backward-time measurement
float64 backward_uncertainty
float64 difference                     # forward - backward
float64 difference_uncertainty

# Statistical analysis
uint32 sample_count                    # Number of samples
float64 mean                           # Mean value
float64 std_dev                        # Standard deviation
float64 chi_squared                    # Chi-squared statistic
float64 p_value                        # P-value for symmetry test

# Time series data (summary)
float64 time_series_duration_sec       # Duration of measurement
float64 time_series_sample_rate_hz     # Sampling rate
uint32 time_series_samples             # Number of samples in series
float64 time_series_min                # Minimum value
float64 time_series_max                # Maximum value

# Quality
float64 data_quality                   # 0.0 to 1.0
float64 fit_quality                    # R-squared or similar
bool measurement_valid                 # Passed quality checks
string[] quality_issues                # List of quality concerns

# Physical conditions during measurement
float64 field_strength_tesla           # Average field during measurement
float64 temperature_kelvin             # Average temperature
float64 causality_risk                 # Average causality risk

# Interpretation
string conclusion                      # Brief interpretation
float64 confidence                     # Confidence in conclusion (0-1)
string[] anomalies_detected            # Any anomalies found

# References
string[] related_measurements          # IDs of related measurements
string raw_data_path                   # Path to raw data file
