# SafetyState - Safety system status

builtin_interfaces/Time stamp

# Overall safety status
uint8 SAFETY_DISARMED = 0
uint8 SAFETY_ARMED = 1
uint8 SAFETY_ACTIVE = 2
uint8 SAFETY_TRIPPED = 3
uint8 SAFETY_ESTOP = 4
uint8 safety_state

# Interlock status
bool interlock_field_ok                # Field within limits
bool interlock_thermal_ok              # Temperature within limits
bool interlock_power_ok                # Power within limits
bool interlock_causality_ok            # No causality violations
bool interlock_door_ok                 # Access door closed (if applicable)
bool interlock_radiation_ok            # Radiation levels safe
bool all_interlocks_ok                 # AND of all interlocks

# E-stop
bool estop_hardware_pressed            # Physical button pressed
bool estop_software_active             # Software E-stop active
bool estop_remote_active               # Remote E-stop active

# Watchdog
bool watchdog_ok                       # Watchdog not tripped
float64 watchdog_timeout_ms            # Configured timeout
float64 last_heartbeat_ms              # Time since last heartbeat

# Fault history
uint32 fault_count                     # Number of faults since arm
string[] active_faults                 # Currently active fault names
string last_fault_message              # Most recent fault

# Operator
string armed_by                        # Who armed the system
builtin_interfaces/Time armed_at       # When system was armed
