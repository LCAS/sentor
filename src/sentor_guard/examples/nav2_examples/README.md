# Nav2 Integration with sentor_guard

This directory contains examples for integrating sentor_guard with Nav2 behavior trees to ensure safe autonomous navigation.

## Overview

The `CheckAutonomyAllowed` behavior tree condition node continuously monitors sentor guard conditions and controls navigation flow based on safety state. This enables:

- **Graceful pause/resume**: Navigation automatically pauses when conditions are not met and resumes when they're satisfied
- **Real-time safety**: Continuous monitoring during navigation, not just at start
- **Integration with Nav2**: Uses standard BehaviorTree.CPP plugin mechanism
- **Configurable**: All safety parameters can be adjusted per use case

## Files

### Behavior Tree Examples
- `navigate_with_guard.xml` - Full Nav2 behavior tree with continuous safety monitoring and recovery
- `simple_nav_with_guard.xml` - Minimal example showing basic integration

### Launch Files
- `nav2_with_guard_launch.py` - Example launch file for Nav2 with sentor_guard

### Test and Demo Scripts
- `test_bt_integration.py` - Test script that publishes sample conditions to demonstrate guard behavior
- `simple_guard_demo.py` - Standalone demo showing guard usage in application code

### Documentation
- `README.md` - This file

## Requirements

1. **ROS2** (tested with Humble/Iron)
2. **Nav2** stack installed
3. **sentor_guard** package built with BehaviorTree.CPP support
4. Topics published:
   - `/robot_state` (std_msgs/String) - Current robot state
   - `/autonomous_mode` (std_msgs/Bool) - Whether autonomous mode is enabled
   - `/safety/heartbeat` (std_msgs/Bool) - Safety system heartbeat
   - `/warning/heartbeat` (std_msgs/Bool) - Warning system heartbeat

## Quick Start

### 1. Build sentor_guard with BT support

```bash
cd ~/ros2_ws
colcon build --packages-select sentor_guard
source install/setup.bash
```

If BehaviorTree.CPP is not found, install it:
```bash
sudo apt install ros-$ROS_DISTRO-behaviortree-cpp
```

### 2. Configure Nav2 to use sentor_guard plugin

Add to your Nav2 parameters YAML file:

```yaml
bt_navigator:
  ros__parameters:
    plugin_lib_names:
      - nav2_compute_path_to_pose_action_bt_node
      - nav2_follow_path_action_bt_node
      # ... other Nav2 plugins ...
      - sentor_guard_bt_nodes  # Add this line
    
    default_nav_to_pose_bt_xml: /path/to/navigate_with_guard.xml
```

### 3. Use in your behavior tree

Simple usage - check before navigation:
```xml
<Sequence>
  <CheckAutonomyAllowed 
    name="CheckSafety"
    required_state="active"
    heartbeat_timeout="1000"/>
  <ComputePathToPose goal="{goal}" path="{path}"/>
  <FollowPath path="{path}"/>
</Sequence>
```

Continuous monitoring during navigation:
```xml
<PipelineSequence>
  <RateController hz="1.0">
    <CheckAutonomyAllowed required_state="active"/>
  </RateController>
  <ComputePathToPose goal="{goal}" path="{path}"/>
  <FollowPath path="{path}"/>
</PipelineSequence>
```

## CheckAutonomyAllowed Node Reference

### Inputs (all optional with defaults)

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `state_topic` | string | `/robot_state` | Topic publishing robot state |
| `mode_topic` | string | `/autonomous_mode` | Topic publishing autonomous mode |
| `safety_heartbeat_topic` | string | `/safety/heartbeat` | Safety heartbeat topic |
| `warning_heartbeat_topic` | string | `/warning/heartbeat` | Warning heartbeat topic |
| `required_state` | string | `active` | Required robot state for autonomy |
| `heartbeat_timeout` | int | `1000` | Heartbeat timeout in milliseconds |
| `require_autonomous_mode` | bool | `true` | Whether autonomous mode must be enabled |
| `require_safety_heartbeat` | bool | `true` | Whether safety heartbeat must be healthy |
| `require_warning_heartbeat` | bool | `true` | Whether warning heartbeat must be healthy |

### Behavior

The node returns:
- **SUCCESS** when all configured conditions are satisfied
- **FAILURE** when any condition is not met

The node continuously evaluates conditions on each tick, enabling real-time response to safety state changes.

## Usage Patterns

### Pattern 1: Pre-Navigation Check

Check conditions once before starting navigation:

```xml
<Sequence>
  <CheckAutonomyAllowed name="PreNavCheck"/>
  <NavigateToPose goal="{goal}"/>
</Sequence>
```

**Use when**: You want to prevent navigation from starting when unsafe.

### Pattern 2: Continuous Monitoring

Check conditions periodically during navigation:

```xml
<PipelineSequence>
  <RateController hz="2.0">
    <CheckAutonomyAllowed name="ContinuousCheck"/>
  </RateController>
  <NavigateToPose goal="{goal}"/>
</PipelineSequence>
```

**Use when**: You want navigation to pause/resume based on safety state.

### Pattern 3: Multi-Level Safety

Check different safety levels at different points:

```xml
<Sequence>
  <!-- Strict check before starting -->
  <CheckAutonomyAllowed 
    name="StrictCheck"
    require_warning_heartbeat="true"/>
  
  <PipelineSequence>
    <!-- Relaxed check during navigation (safety only) -->
    <RateController hz="1.0">
      <CheckAutonomyAllowed 
        name="RelaxedCheck"
        require_warning_heartbeat="false"/>
    </RateController>
    <NavigateToPose goal="{goal}"/>
  </PipelineSequence>
</Sequence>
```

**Use when**: You have different safety requirements for different phases.

### Pattern 4: With Recovery Behaviors

Combine with Nav2 recovery behaviors:

```xml
<RecoveryNode number_of_retries="3">
  <PipelineSequence>
    <RateController hz="1.0">
      <CheckAutonomyAllowed/>
    </RateController>
    <NavigateToPose goal="{goal}"/>
  </PipelineSequence>
  
  <ReactiveFallback>
    <ClearCostmap/>
    <Spin/>
    <Wait wait_duration="5.0"/>
  </ReactiveFallback>
</RecoveryNode>
```

**Use when**: You want standard Nav2 recovery combined with safety checks.

## Integration with sentor

The CheckAutonomyAllowed node integrates with the broader sentor ecosystem:

1. **Sentor** monitors sensors and publishes heartbeats
2. **RobotStateMachine** manages robot state and autonomous mode
3. **sentor_guard** libraries provide reusable safety checking
4. **CheckAutonomyAllowed** BT node brings it into Nav2 behavior trees

This creates a complete safety architecture for autonomous navigation.

## Troubleshooting

### Plugin not loading

**Error**: `Failed to load behavior tree plugin sentor_guard_bt_nodes`

**Solution**: 
1. Verify package is built: `ros2 pkg list | grep sentor_guard`
2. Check plugin is installed: `ls $(ros2 pkg prefix sentor_guard)/lib/libsentor_guard_bt_nodes.so`
3. Source workspace: `source ~/ros2_ws/install/setup.bash`

### Condition always fails

**Error**: Navigation never starts, CheckAutonomyAllowed always returns FAILURE

**Solution**:
1. Check topics are published: `ros2 topic echo /robot_state`
2. Verify values: State should be "active", mode should be true
3. Check heartbeats: `ros2 topic echo /safety/heartbeat`
4. Enable debug logging: `ros2 run nav2_bt_navigator bt_navigator --ros-args --log-level debug`

### BehaviorTree.CPP not found during build

**Error**: `Could not find a package configuration file provided by "behaviortree_cpp"`

**Solution**:
```bash
sudo apt install ros-$ROS_DISTRO-behaviortree-cpp
# Or from source
cd ~/ros2_ws/src
git clone https://github.com/BehaviorTree/BehaviorTree.CPP.git
cd ~/ros2_ws
colcon build --packages-select behaviortree_cpp
```

## Testing

### Test Scripts

Two test scripts are provided to demonstrate and test the guard behavior:

#### 1. Simple Guard Demo (`simple_guard_demo.py`)

Demonstrates how the guard works in application code:

```bash
# Terminal 1 - Run the demo
ros2 run sentor_guard simple_guard_demo.py

# Terminal 2 - Publish safe conditions
ros2 topic pub /robot_state std_msgs/String "data: 'active'" -1
ros2 topic pub /autonomous_mode std_msgs/Bool "data: true" -1
ros2 topic pub /safety/heartbeat std_msgs/Bool "data: true" -r 2
ros2 topic pub /warning/heartbeat std_msgs/Bool "data: true" -r 2
```

This shows:
- How the guard checks conditions
- What happens when conditions are not met
- How navigation resumes when conditions are satisfied

#### 2. BT Integration Test (`test_bt_integration.py`)

Publishes a sequence of test conditions to verify guard behavior:

```bash
# Run the test (it will publish various test conditions)
ros2 run sentor_guard test_bt_integration.py
```

This script:
- Publishes different combinations of conditions
- Demonstrates pause/resume scenarios
- Simulates realistic navigation conditions
- Useful for testing the CheckAutonomyAllowed BT node

### Manual Testing

Test the BT node behavior manually:

```python
# test_bt_node.py
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
import time

node = rclpy.create_node('test_publisher')

# Publishers
state_pub = node.create_publisher(String, '/robot_state', 10)
mode_pub = node.create_publisher(Bool, '/autonomous_mode', 10)
safety_pub = node.create_publisher(Bool, '/safety/heartbeat', 10)
warning_pub = node.create_publisher(Bool, '/warning/heartbeat', 10)

# Publish safe conditions
state_msg = String()
state_msg.data = 'active'
state_pub.publish(state_msg)

mode_msg = Bool()
mode_msg.data = True
mode_pub.publish(mode_msg)

hb_msg = Bool()
hb_msg.data = True
safety_pub.publish(hb_msg)
warning_pub.publish(hb_msg)

print("Publishing safe conditions...")
time.sleep(1.0)

# Now test with unsafe conditions
state_msg.data = 'paused'
state_pub.publish(state_msg)
print("Changed to unsafe state")
```

## Further Reading

- [Nav2 Behavior Trees](https://navigation.ros.org/behavior_trees/index.html)
- [BehaviorTree.CPP](https://www.behaviortree.dev/)
- [sentor_guard Documentation](../../README.md)
- [Integration Architecture](../../../ARCHITECTURE_INTEGRATION.md)

## License

MIT - Part of the LCAS sentor project
