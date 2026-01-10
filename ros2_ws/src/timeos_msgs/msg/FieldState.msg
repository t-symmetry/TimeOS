# FieldState - Electromagnetic field generator state

builtin_interfaces/Time stamp

# Field values
float64 field_strength                 # Tesla
float64 field_setpoint                 # Target Tesla
float64 field_error                    # Setpoint - actual

# Field components (if vector field)
float64 bx                             # Tesla
float64 by                             # Tesla
float64 bz                             # Tesla

# Ramp state
uint8 RAMP_IDLE = 0
uint8 RAMP_UP = 1
uint8 RAMP_DOWN = 2
uint8 RAMP_HOLDING = 3
uint8 RAMP_QUENCHING = 4
uint8 ramp_state

float64 ramp_rate                      # Tesla/second
float64 ramp_progress                  # 0.0 to 1.0

# Power
float64 power_watts                    # Current power draw
float64 current_amps                   # Coil current
float64 voltage_volts                  # Coil voltage

# Quality metrics
float64 stability                      # 0.0 to 1.0 (1.0 = perfectly stable)
float64 homogeneity                    # Field uniformity metric
float64 ripple_ppm                     # Ripple in parts per million

# Status
bool active                            # Field is energized
bool at_setpoint                       # Within tolerance of setpoint
bool interlock_ok                      # Safety interlocks satisfied
string fault_message                   # Empty if no fault
