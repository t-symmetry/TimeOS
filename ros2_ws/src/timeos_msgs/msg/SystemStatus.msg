# SystemStatus - Overall TimeOS system status

builtin_interfaces/Time stamp

# System state
uint8 STATE_OFFLINE = 0
uint8 STATE_INITIALIZING = 1
uint8 STATE_STANDBY = 2
uint8 STATE_READY = 3
uint8 STATE_OPERATING = 4
uint8 STATE_FAULT = 5
uint8 STATE_EMERGENCY = 6
uint8 system_state

# Module status
FieldState field
ThermalState thermal
SafetyState safety
CausalityStatus causality
AnchorState anchor
DisplacementState displacement

# Overall metrics
float64 uptime_seconds                 # Time since initialization
uint32 event_count                     # Total events logged
uint32 displacement_count              # Total displacements
uint32 branch_count                    # Timeline branches created

# Resource usage
float64 cpu_percent                    # CPU utilization
float64 memory_percent                 # Memory utilization
float64 disk_percent                   # Disk utilization
float64 network_bytes_sec              # Network throughput

# Mode
bool demo_mode                         # Running in demo mode
bool emulated_mode                     # Using emulated hardware
bool hil_mode                          # Hardware-in-the-loop mode
string[] enabled_modules               # List of enabled module names

# Version info
string version                         # TimeOS version
string ros_distro                      # ROS distribution
