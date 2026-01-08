# TimelineEvent - A universal envelope for temporal events
#
# Wraps any event with temporal metadata, causal links,
# and provenance information.

# Unique identifier (UUID string)
string event_id

# When the event occurred
ChronoStamp stamp

# Type: "observation", "actuation", "annotation", "constraint", "branch", "merge"
string event_type "observation"

# Event-specific data (serialized payload)
uint8[] payload

# Schema reference for payload (e.g., "timeos/SensorReading@1")
string payload_schema

# Event IDs this event causally depends on
string[] parents

# Timeline branch this event belongs to
string branch_id "main"

# Identity of event creator
string author

# Sequence number (per-author, for ordering)
uint64 seq
