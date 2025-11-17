# Nav2 Behavior Tree Integration Guide

This document provides a complete guide for integrating sentor_guard with Nav2 behavior trees to enable safe autonomous navigation with real-time safety monitoring.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [Basic Usage](#basic-usage)
6. [Advanced Usage](#advanced-usage)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)

---

## Overview

The `CheckAutonomyAllowed` behavior tree condition node enables direct integration of sentor safety monitoring within Nav2 navigation behavior trees. This provides:

- **Real-time safety monitoring** during navigation
- **Graceful pause/resume** when safety conditions change
- **Configurable safety requirements** per use case
- **Standard integration** using BehaviorTree.CPP plugin mechanism

### How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    System Flow                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐     ┌──────────────┐                 │
│  │ Sentor       │     │ RobotState   │                 │
│  │ Monitoring   │     │ Machine      │                 │
│  └──────┬───────┘     └──────┬───────┘                 │
│         │                    │                          │
│         │ /safety/heartbeat  │ /robot_state             │
│         │ /warning/heartbeat │ /autonomous_mode         │
│         │                    │                          │
│         └────────┬───────────┘                          │
│                  ↓                                      │
│         ┌────────────────────┐                          │
│         │ CheckAutonomy      │  (BT Condition Node)     │
│         │ Allowed            │                          │
│         └────────┬───────────┘                          │
│                  ↓                                      │
│         Returns SUCCESS/FAILURE                         │
│                  ↓                                      │
│         ┌────────────────────┐                          │
│         │ Nav2 Behavior Tree │                          │
│         │ - ComputePath      │                          │
│         │ - FollowPath       │                          │
│         │ - Recovery         │                          │
│         └────────────────────┘                          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

The condition node continuously evaluates safety requirements and returns:
- `SUCCESS` when all conditions are satisfied → navigation proceeds
- `FAILURE` when any condition is not met → navigation pauses

---

## Architecture

### Components

1. **CheckAutonomyAllowed BT Node** (`sentor_guard_bt_nodes` library)
   - C++ implementation using BehaviorTree.CPP
   - Integrates with sentor_guard C++ library
   - Configurable via BT XML

2. **SentorGuard C++ Library** (`sentor_guard` library)
   - Monitors ROS topics for safety conditions
   - Provides blocking/non-blocking condition checking
   - RAII pattern for safe execution

3. **Safety Topics** (Published by external systems)
   - `/robot_state` - Current operational state
   - `/autonomous_mode` - Autonomous mode enabled/disabled
   - `/safety/heartbeat` - Safety system health
   - `/warning/heartbeat` - Warning system health

### Integration Points

The BT node integrates at multiple levels:

```
Level 1: Pre-Navigation Check
  <Sequence>
    <CheckAutonomyAllowed/>  ← Check once before starting
    <NavigateToPose/>
  </Sequence>

Level 2: Continuous Monitoring
  <PipelineSequence>
    <RateController hz="2.0">
      <CheckAutonomyAllowed/>  ← Check continuously
    </RateController>
    <NavigateToPose/>
  </PipelineSequence>

Level 3: Multi-Point Checking
  <Sequence>
    <CheckAutonomyAllowed name="PreCheck"/>
    <ComputePathToPose/>
    <CheckAutonomyAllowed name="PreExecution"/>  ← Multiple checks
    <FollowPath/>
  </Sequence>
```

---

## Prerequisites

### Required

- **ROS2** (Humble, Iron, or later)
- **Nav2** stack
- **BehaviorTree.CPP** 4.x

### Optional but Recommended

- **Sentor** monitoring package (for safety/warning heartbeats)
- **RobotStateMachine** (for state/mode management)

### Installation of Dependencies

```bash
# Install Nav2 and BehaviorTree.CPP
sudo apt install ros-$ROS_DISTRO-navigation2 ros-$ROS_DISTRO-behaviortree-cpp

# Or build from source
cd ~/ros2_ws/src
git clone https://github.com/ros-planning/navigation2.git
git clone https://github.com/BehaviorTree/BehaviorTree.CPP.git
cd ~/ros2_ws
colcon build
```

---

## Installation

### 1. Build sentor_guard Package

```bash
cd ~/ros2_ws/src
# Clone sentor repository if not already present
git clone https://github.com/LCAS/sentor.git

cd ~/ros2_ws
colcon build --packages-select sentor_guard
source install/setup.bash
```

### 2. Verify Installation

```bash
# Check if BT plugin library is built
ls $(ros2 pkg prefix sentor_guard)/lib/libsentor_guard_bt_nodes.so

# Check if plugin descriptor is installed
ls $(ros2 pkg prefix sentor_guard)/share/sentor_guard/sentor_guard_bt_nodes.xml
```

### 3. Configure Nav2

Add the plugin to your Nav2 bt_navigator parameters YAML:

```yaml
bt_navigator:
  ros__parameters:
    plugin_lib_names:
      - nav2_compute_path_to_pose_action_bt_node
      - nav2_follow_path_action_bt_node
      - nav2_back_up_action_bt_node
      - nav2_spin_action_bt_node
      - nav2_wait_action_bt_node
      - nav2_clear_costmap_service_bt_node
      - nav2_is_stuck_condition_bt_node
      - nav2_goal_reached_condition_bt_node
      - nav2_goal_updated_condition_bt_node
      - nav2_rate_controller_bt_node
      - nav2_distance_controller_bt_node
      - nav2_speed_controller_bt_node
      - nav2_truncate_path_action_bt_node
      - nav2_recovery_node_bt_node
      - nav2_pipeline_sequence_bt_node
      - nav2_round_robin_node_bt_node
      - nav2_transform_available_condition_bt_node
      - nav2_time_expired_condition_bt_node
      - nav2_distance_traveled_condition_bt_node
      - sentor_guard_bt_nodes  # Add this line
```

---

## Basic Usage

### Simple Example

Create a behavior tree XML file (e.g., `my_nav_bt.xml`):

```xml
<root BTCPP_format="4">
  <BehaviorTree ID="NavigateWithSafety">
    <Sequence>
      <!-- Check safety before navigation -->
      <CheckAutonomyAllowed 
        name="SafetyCheck"
        required_state="active"
        heartbeat_timeout="1000"/>
      
      <!-- Standard Nav2 navigation -->
      <ComputePathToPose goal="{goal}" path="{path}" planner_id="GridBased"/>
      <FollowPath path="{path}" controller_id="FollowPath"/>
    </Sequence>
  </BehaviorTree>
</root>
```

### Configuration Parameters

All parameters are optional with sensible defaults:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `state_topic` | string | `/robot_state` | Topic for robot state |
| `mode_topic` | string | `/autonomous_mode` | Topic for autonomous mode |
| `safety_heartbeat_topic` | string | `/safety/heartbeat` | Safety heartbeat topic |
| `warning_heartbeat_topic` | string | `/warning/heartbeat` | Warning heartbeat topic |
| `required_state` | string | `active` | Required state value |
| `heartbeat_timeout` | int | `1000` | Heartbeat timeout (ms) |
| `require_autonomous_mode` | bool | `true` | Check autonomous mode |
| `require_safety_heartbeat` | bool | `true` | Check safety heartbeat |
| `require_warning_heartbeat` | bool | `true` | Check warning heartbeat |

---

## Advanced Usage

### Continuous Monitoring with Pause/Resume

```xml
<root BTCPP_format="4">
  <BehaviorTree ID="ContinuousMonitoring">
    <PipelineSequence>
      <!-- Check at 2Hz during navigation -->
      <RateController hz="2.0">
        <CheckAutonomyAllowed required_state="active"/>
      </RateController>
      
      <Sequence>
        <ComputePathToPose goal="{goal}" path="{path}"/>
        <FollowPath path="{path}"/>
      </Sequence>
    </PipelineSequence>
  </BehaviorTree>
</root>
```

When conditions fail:
1. BT returns FAILURE
2. Navigation pauses (FollowPath stops)
3. On next tick, conditions checked again
4. If conditions satisfied, navigation resumes

### Multi-Level Safety

Different safety requirements at different points:

```xml
<root BTCPP_format="4">
  <BehaviorTree ID="MultiLevelSafety">
    <Sequence>
      <!-- Strict check before starting -->
      <CheckAutonomyAllowed 
        name="StrictPreCheck"
        require_safety_heartbeat="true"
        require_warning_heartbeat="true"
        heartbeat_timeout="500"/>
      
      <ComputePathToPose goal="{goal}" path="{path}"/>
      
      <PipelineSequence>
        <!-- Relaxed check during execution (safety only) -->
        <RateController hz="2.0">
          <CheckAutonomyAllowed 
            name="ExecutionCheck"
            require_warning_heartbeat="false"
            heartbeat_timeout="1000"/>
        </RateController>
        
        <FollowPath path="{path}"/>
      </PipelineSequence>
    </Sequence>
  </BehaviorTree>
</root>
```

### Integration with Recovery Behaviors

```xml
<root BTCPP_format="4">
  <BehaviorTree ID="NavigateWithRecovery">
    <RecoveryNode number_of_retries="3" name="NavWithRecovery">
      <!-- Main navigation sequence -->
      <PipelineSequence>
        <RateController hz="1.0">
          <CheckAutonomyAllowed/>
        </RateController>
        <ComputePathToPose goal="{goal}" path="{path}"/>
        <FollowPath path="{path}"/>
      </PipelineSequence>
      
      <!-- Recovery behaviors -->
      <ReactiveFallback name="RecoveryActions">
        <GoalUpdated/>
        <ClearEntireCostmap service_name="global_costmap/clear_entirely_global_costmap"/>
        <ClearEntireCostmap service_name="local_costmap/clear_entirely_local_costmap"/>
        <Spin spin_dist="1.57"/>
        <Wait wait_duration="5.0"/>
        <BackUp backup_dist="0.30" backup_speed="0.05"/>
      </ReactiveFallback>
    </RecoveryNode>
  </BehaviorTree>
</root>
```

---

## Testing

### Using Test Scripts

sentor_guard provides test scripts to verify integration:

#### 1. Simple Guard Demo

```bash
# Terminal 1 - Run demo
ros2 run sentor_guard simple_guard_demo.py

# Terminal 2 - Publish safe conditions
ros2 topic pub /robot_state std_msgs/String "data: 'active'" -1
ros2 topic pub /autonomous_mode std_msgs/Bool "data: true" -1
ros2 topic pub /safety/heartbeat std_msgs/Bool "data: true" -r 2
ros2 topic pub /warning/heartbeat std_msgs/Bool "data: true" -r 2
```

#### 2. BT Integration Test

```bash
ros2 run sentor_guard test_bt_integration.py
```

This publishes test conditions and simulates pause/resume scenarios.

### Testing with Nav2

1. Start Nav2 with your behavior tree:
```bash
ros2 launch nav2_bringup navigation_launch.py \
  params_file:=your_params.yaml
```

2. Publish safety conditions:
```bash
# Safe conditions
ros2 topic pub /robot_state std_msgs/String "data: 'active'" -r 1
ros2 topic pub /autonomous_mode std_msgs/Bool "data: true" -r 1
ros2 topic pub /safety/heartbeat std_msgs/Bool "data: true" -r 2
ros2 topic pub /warning/heartbeat std_msgs/Bool "data: true" -r 2
```

3. Send navigation goal:
```bash
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: 'map'}, pose: {position: {x: 1.0, y: 0.0}}}}"
```

4. Test pause by changing state:
```bash
ros2 topic pub /robot_state std_msgs/String "data: 'paused'" -1
```

---

## Troubleshooting

### Plugin Not Loading

**Symptom**: `Failed to load behavior tree plugin sentor_guard_bt_nodes`

**Solutions**:
1. Verify package is built:
   ```bash
   ros2 pkg list | grep sentor_guard
   ```

2. Check library exists:
   ```bash
   ls $(ros2 pkg prefix sentor_guard)/lib/libsentor_guard_bt_nodes.so
   ```

3. Ensure workspace is sourced:
   ```bash
   source ~/ros2_ws/install/setup.bash
   ```

### Navigation Never Starts

**Symptom**: CheckAutonomyAllowed always returns FAILURE

**Solutions**:
1. Verify topics are published:
   ```bash
   ros2 topic list | grep -E "robot_state|autonomous_mode|heartbeat"
   ```

2. Check topic values:
   ```bash
   ros2 topic echo /robot_state
   ros2 topic echo /autonomous_mode
   ```

3. Enable debug logging:
   ```bash
   ros2 run nav2_bt_navigator bt_navigator --ros-args --log-level debug
   ```

### Heartbeat Timeout

**Symptom**: Navigation pauses frequently due to stale heartbeats

**Solutions**:
1. Increase timeout in BT XML:
   ```xml
   <CheckAutonomyAllowed heartbeat_timeout="2000"/>
   ```

2. Check heartbeat publication rate:
   ```bash
   ros2 topic hz /safety/heartbeat
   ```

3. Ensure heartbeat publishers are running

---

## Best Practices

### 1. Choose Appropriate Check Frequency

- **Pre-navigation only**: Fast response not critical, checking before start
- **1-2 Hz**: Balance between responsiveness and overhead
- **5-10 Hz**: Critical applications requiring fast response

### 2. Configure Timeouts Appropriately

- **Short timeout (500ms)**: Critical safety sensors
- **Medium timeout (1000ms)**: Standard heartbeats
- **Long timeout (2000ms)**: Slower systems or degraded mode

### 3. Use Defense in Depth

Combine multiple safety layers:
1. **BT condition check**: Real-time monitoring in navigation
2. **Lifecycle management**: Control Nav2 node activation
3. **cmd_vel filter**: Emergency backstop

### 4. Design for Graceful Degradation

```xml
<Sequence>
  <!-- Strict check initially -->
  <CheckAutonomyAllowed 
    require_safety_heartbeat="true"
    require_warning_heartbeat="true"/>
  
  <Fallback>
    <!-- Try normal navigation -->
    <Sequence>
      <CheckAutonomyAllowed/>
      <NormalNavigation/>
    </Sequence>
    
    <!-- Fall back to cautious mode -->
    <Sequence>
      <CheckAutonomyAllowed 
        require_warning_heartbeat="false"/>
      <CautiousNavigation/>
    </Sequence>
  </Fallback>
</Sequence>
```

### 5. Monitor and Log

Enable comprehensive logging:
```xml
<CheckAutonomyAllowed name="PreNav" />  <!-- Named for easier debugging -->
```

Check logs:
```bash
ros2 topic echo /rosout | grep CheckAutonomyAllowed
```

---

## Example: Complete Navigation System

See the provided examples:
- `src/sentor_guard/examples/nav2_examples/navigate_with_guard.xml`
- `src/sentor_guard/examples/nav2_examples/simple_nav_with_guard.xml`
- `src/sentor_guard/examples/nav2_examples/nav2_with_guard_launch.py`

---

## Related Documentation

- [sentor_guard Package README](../src/sentor_guard/README.md)
- [Nav2 Examples README](../src/sentor_guard/examples/nav2_examples/README.md)
- [Integration Architecture](../ARCHITECTURE_INTEGRATION.md)
- [Integration Summary](../INTEGRATION_SUMMARY.md)

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/LCAS/sentor/issues
- Package maintainer: LCAS team

---

## License

MIT - Part of the LCAS sentor project
