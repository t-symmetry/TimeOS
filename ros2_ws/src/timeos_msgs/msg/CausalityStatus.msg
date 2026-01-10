# CausalityStatus - Current causality monitoring state

builtin_interfaces/Time stamp

# Overall status
uint8 STATUS_NOMINAL = 0
uint8 STATUS_WARNING = 1
uint8 STATUS_VIOLATION = 2
uint8 STATUS_UNKNOWN = 3
uint8 status

# Risk assessment
float64 paradox_risk                   # 0.0 to 1.0
float64 accumulated_risk               # Cumulative risk
uint32 active_constraints              # Number of active constraints
uint32 violated_constraints            # Number of violations

# Constraint details
string[] constraint_names              # Names of checked constraints
float64[] constraint_risks             # Risk per constraint
bool[] constraint_passed               # Pass/fail per constraint

# Light cone analysis
bool future_cone_clear                 # No violations in future cone
bool past_cone_clear                   # No violations in past cone
uint32 events_in_future_cone
uint32 events_in_past_cone

# Thresholds
float64 warning_threshold              # Risk level for warning
float64 branch_threshold               # Risk level for auto-branch
float64 interlock_threshold            # Risk level for interlock
