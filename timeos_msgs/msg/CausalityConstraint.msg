# CausalityConstraint - A constraint on causal relationships
#
# Defines rules that must be satisfied for timeline consistency.

# Unique identifier for this constraint
string constraint_id

# Type of constraint:
# - "causal_order": parents must precede children
# - "no_self_causation": event cannot be its own ancestor
# - "branch_consistency": no cross-branch references without merge
# - "custom": user-defined constraint
string constraint_type

# Human-readable description
string description

# Whether this is a hard constraint (reject) or soft (warn/branch)
bool is_hard true

# Policy on violation: "reject", "branch", "warn", "ignore"
string violation_policy "reject"

# Optional: specific event types this constraint applies to (empty = all)
string[] applies_to_types

# Optional: specific branches this constraint applies to (empty = all)
string[] applies_to_branches

# Optional: custom constraint parameters (JSON-encoded)
string parameters
