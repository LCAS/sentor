# sentor_guard

Safety guard libraries and nodes for sentor-based autonomous systems.

## Overview

The `sentor_guard` package provides reusable components for implementing safe autonomous behavior by integrating sentor's state monitoring with robot control systems. It offers three complementary approaches:

1. **Software Context Guards** - Python and C++ libraries for inline safety checks
2. **Topic Guards** - Transparent topic forwarding with safety gating
3. **Lifecycle Guards** - Automatic lifecycle management of nodes based on safety conditions

## Features

- **Python Library**: Context manager pattern (`with` statement) that blocks execution until conditions met
- **C++ Library**: RAII pattern for automatic safety checking
- **Topic Guard Node**: Filters messages (e.g., cmd_vel) based on guard conditions
- **Lifecycle Guard Node**: Manages lifecycle state of other nodes
- **ROS Parameter Configuration**: Easy configuration via YAML files
- **Multiple Usage Patterns**: Blocking wait, timeout-based wait, non-blocking checks

## Installation

This package is part of the sentor repository. Build with:

```bash
cd ~/ros2_ws
colcon build --packages-select sentor_guard
source install/setup.bash
```

## Quick Start

### Python Guard

```python
from sentor_guard import SentorGuard

class MyNode(Node):
    def __init__(self):
        super().__init__('my_node')
        self.guard = SentorGuard(self, required_state='active')
    
    def do_autonomous_action(self):
        # Only executes when safe
        with self.guard:
            self.execute_navigation()
```

### C++ Guard

```cpp
#include "sentor_guard/guard.hpp"

class MyNode : public rclcpp::Node {
    sentor_guard::SentorGuard guard_;
public:
    MyNode() : Node("my_node"), guard_(shared_from_this()) {}
    
    void doAutonomousAction() {
        // RAII guard - automatically waits
        sentor_guard::SentorGuard::Guard guard(guard_);
        executeNavigation();
    }
};
```

### Launch Example

```bash
ros2 launch sentor_guard guard_example.launch.py
```

## Configuration

See `config/guard_params.yaml` for configuration options:

```yaml
/**:
  ros__parameters:
    state_topic: "/robot_state"
    mode_topic: "/autonomous_mode"
    safety_heartbeat_topic: "/safety/heartbeat"
    warning_heartbeat_topic: "/warning/heartbeat"
    required_state: "active"
    heartbeat_timeout: 1.0
```

## Safety Conditions

A guard is satisfied when **all** of the following are true:

1. **State Match**: Current state equals required state (default: "active")
2. **Mode Enabled**: Autonomous mode is enabled (default: required)
3. **Safety Heartbeat**: Safety heartbeat is true and fresh (default: required)
4. **Warning Heartbeat**: Warning heartbeat is true and fresh (default: required)

## Usage Patterns

### Pattern 1: Context Manager (Python)

```python
with self.guard:
    # Code here only runs when safe
    execute_autonomous_action()
```

### Pattern 2: RAII Guard (C++)

```cpp
{
    SentorGuard::Guard guard(my_guard);
    // Code here only runs when safe
    executeAutonomousAction();
}
```

### Pattern 3: Timeout Wait

```python
try:
    self.guard.guarded_wait(timeout=5.0)
    execute_action()
except AutonomyGuardException as e:
    handle_timeout(e)
```

### Pattern 4: Non-blocking Check

```python
if self.guard.is_autonomy_allowed():
    execute_action()
else:
    reason = self.guard.get_blocking_reason()
    log_warning(reason)
```

## Nodes

### topic_guard_node

Forwards messages only when guard conditions are met.

**Parameters:**
- `input_topic`: Source topic to monitor
- `output_topic`: Destination topic for forwarded messages
- `message_type`: ROS message type (e.g., "geometry_msgs/msg/Twist")
- `required_state`: Required robot state (default: "active")
- `heartbeat_timeout`: Maximum heartbeat age in seconds (default: 1.0)

**Example:**

```bash
ros2 run sentor_guard topic_guard_node --ros-args \
  -p input_topic:=/nav2/cmd_vel \
  -p output_topic:=/cmd_vel \
  -p message_type:=geometry_msgs/msg/Twist
```

### lifecycle_guard_node

Manages lifecycle state of other nodes based on guard conditions.

**Parameters:**
- `managed_nodes`: List of node names to manage
- `check_rate`: How often to check conditions (Hz, default: 10.0)

**Example:**

```bash
ros2 run sentor_guard lifecycle_guard_node --ros-args \
  -p managed_nodes:="['/controller_server', '/planner_server']" \
  -p check_rate:=10.0
```

## Testing

Run tests:

```bash
colcon test --packages-select sentor_guard
colcon test-result --verbose
```

## Documentation

For complete architecture documentation, see:
- [SENTOR_GUARD_DESIGN.md](../../docs/SENTOR_GUARD_DESIGN.md) - Complete design specification
- [ARCHITECTURE_INTEGRATION.md](../../ARCHITECTURE_INTEGRATION.md) - System integration architecture

## License

MIT

## Authors

Part of the LCAS sentor project.
