# ThermalState - Thermal system monitoring

builtin_interfaces/Time stamp

# Primary temperature
float64 temperature_kelvin             # Main temperature reading
float64 temperature_setpoint           # Target temperature
float64 temperature_rate               # K/second (positive = heating)

# Zone temperatures
float64 temp_magnet_core               # Kelvin
float64 temp_cryostat                  # Kelvin
float64 temp_radiation_shield          # Kelvin
float64 temp_ambient                   # Kelvin

# Cryogenic state
uint8 CRYO_WARM = 0
uint8 CRYO_COOLING = 1
uint8 CRYO_COLD = 2
uint8 CRYO_WARMING = 3
uint8 cryo_state

# Cooling system
float64 cooling_power_watts            # Current cooling power
float64 cooling_capacity_watts         # Maximum available
float64 helium_level_percent           # LHe level (0-100)
float64 nitrogen_level_percent         # LN2 level (0-100)

# Quench monitoring
float64 quench_risk                    # 0.0 to 1.0
float64 thermal_margin_kelvin          # Distance to critical temp
float64 critical_temperature           # Quench threshold
bool quench_detected                   # Active quench event
float64 time_to_quench_seconds         # Estimated time if trending

# Status
bool cooling_active                    # Cooling system running
bool thermal_stable                    # Temperature stable
string fault_message                   # Empty if no fault
