# ChronoStamp - Temporal coordinate with uncertainty
# Represents a point in the temporal reference frame

builtin_interfaces/Time stamp          # ROS timestamp for synchronization
float64 tau                            # Proper time (seconds)
float64 tau_uncertainty                # Uncertainty in proper time
float64 coordinate_time                # Coordinate time in lab frame
float64 gamma                          # Lorentz factor (1.0 for stationary)
string reference_frame                 # Frame identifier
string timeline_id                     # Timeline branch identifier
uint32 sequence                        # Monotonic sequence number
