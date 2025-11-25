# Guard blocking/unblocking status message
# Published when a guard blocks and when it unblocks

# Node name where the guard blocked
string node_name

# Whether the guard is currently blocking (true) or just passed (false)
bool is_blocking

# Reason for blocking (empty if not blocking)
string blocking_reason

# Truncated call stack where the guard blocked (max 10 frames)
string[] call_stack

# Time when blocking started (seconds since epoch)
builtin_interfaces/Time blocked_at

# Duration of blocking in seconds (0 if still blocking, >0 if just unblocked)
float64 blocked_duration
