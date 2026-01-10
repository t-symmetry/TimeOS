# TimelineEvent - An event in the temporal log
# Immutable record of something that occurred

string event_id                        # Unique event identifier (UUID)
ChronoStamp timestamp                  # When it occurred
string timeline_id                     # Which timeline branch
string parent_event_id                 # Causal parent (empty for root)
string[] child_event_ids               # Causal children

# Event classification
uint8 EVENT_TYPE_OBSERVATION = 0
uint8 EVENT_TYPE_INTERVENTION = 1
uint8 EVENT_TYPE_DISPLACEMENT = 2
uint8 EVENT_TYPE_BRANCH = 3
uint8 EVENT_TYPE_MERGE = 4
uint8 EVENT_TYPE_ANCHOR = 5
uint8 event_type

# Spacetime coordinates (lab frame, SI units)
float64 x                              # meters
float64 y                              # meters
float64 z                              # meters
float64 t                              # seconds

# Event data
string description                     # Human-readable description
string data_json                       # Arbitrary JSON payload

# Causality
float64 causality_risk                 # 0.0 to 1.0
bool causality_valid                   # True if no violations detected
string[] constraint_violations         # List of violated constraints
