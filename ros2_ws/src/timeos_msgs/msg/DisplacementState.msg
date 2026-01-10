# DisplacementState - Temporal Displacement Unit status

builtin_interfaces/Time stamp

# Displacement state
uint8 DISP_IDLE = 0
uint8 DISP_PREPARING = 1
uint8 DISP_CHARGING = 2
uint8 DISP_READY = 3
uint8 DISP_DISPLACING = 4
uint8 DISP_RETURNING = 5
uint8 DISP_COOLDOWN = 6
uint8 DISP_FAULT = 7
uint8 displacement_state

# Current position (spacetime coordinates)
float64 current_x                      # meters
float64 current_y                      # meters
float64 current_z                      # meters
float64 current_t                      # seconds (proper time)

# Target position (if displacing)
float64 target_x                       # meters
float64 target_y                       # meters
float64 target_z                       # meters
float64 target_t                       # seconds

# Displacement metrics
float64 displacement_progress          # 0.0 to 1.0
float64 estimated_completion_sec       # ETA to completion
float64 energy_required_joules         # Energy needed
float64 energy_available_joules        # Energy stored/available

# Position uncertainty
float64 position_uncertainty_m         # Spatial uncertainty
float64 temporal_uncertainty_s         # Temporal uncertainty

# Statistics
uint32 total_displacements             # Lifetime count
float64 total_distance_m               # Cumulative spatial distance
float64 total_duration_s               # Cumulative temporal displacement

# Return anchor
bool return_anchor_set                 # Return point configured
ChronoStamp return_anchor              # Return coordinates

# Status
bool ready                             # Ready for displacement
bool interlocks_satisfied              # All preconditions met
string fault_message                   # Empty if no fault
