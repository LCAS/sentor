# Concept Architecture: Integration of Sentor, RobotStateMachine, and Nav2

## Executive Summary

This document outlines the architectural design for integrating three critical systems to ensure safe and compliant autonomous navigation:
1. **Sentor** - Safety monitoring and heartbeat system
2. **RobotStateMachine** - State management for robot operational modes
3. **Nav2** - Autonomous navigation stack

The core safety requirement is that autonomous navigation shall only occur when:
```
/robot_state == "active" AND /autonomous_mode == true
```

Any violation of this condition must immediately stop robot motion and terminate active navigation goals.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Component Responsibilities](#component-responsibilities)
3. [Integration Architecture](#integration-architecture)
4. [Safety-Critical Topics and Interfaces](#safety-critical-topics-and-interfaces)
5. [State Transition Handling](#state-transition-handling)
6. [Nav2 Integration Strategies](#nav2-integration-strategies)
7. [Emergency Stop Behavior](#emergency-stop-behavior)
8. [Implementation Recommendations](#implementation-recommendations)
9. [Testing and Validation Strategy](#testing-and-validation-strategy)
10. [Failure Modes and Mitigation](#failure-modes-and-mitigation)

---

## System Overview

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    System Architecture                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐      ┌──────────────────┐                │
│  │ RobotStateMachine│      │     Sentor       │                │
│  │                  │      │                  │                │
│  │  - State Mgmt    │      │  - Safety Mon    │                │
│  │  - Mode Mgmt     │      │  - Heartbeats    │                │
│  └────────┬─────────┘      └────────┬─────────┘                │
│           │                         │                           │
│           │ /robot_state            │ /safety/heartbeat         │
│           │ /autonomous_mode        │ /warning/heartbeat        │
│           │                         │                           │
│           └──────────┬──────────────┘                           │
│                      ↓                                          │
│           ┌─────────────────────┐                               │
│           │  Safety Controller  │  (New Component)              │
│           │  Nav2 Lifecycle Mgr │                               │
│           └──────────┬──────────┘                               │
│                      │                                          │
│                      │ Control signals                          │
│                      ↓                                          │
│           ┌─────────────────────┐                               │
│           │       Nav2 Stack    │                               │
│           │                     │                               │
│           │  - BT Navigator     │                               │
│           │  - Controller       │                               │
│           │  - Planner          │                               │
│           └─────────────────────┘                               │
│                      │                                          │
│                      ↓                                          │
│           ┌─────────────────────┐                               │
│           │  Robot Base         │                               │
│           │  (cmd_vel consumer) │                               │
│           └─────────────────────┘                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### 1. RobotStateMachine

**Repository**: https://github.com/LCAS/RobotStateMachine

**Responsibilities**:
- Publish current robot operational state on `/robot_state` (e.g., "active", "paused", "emergency_stop", "idle")
- Publish autonomous mode status on `/autonomous_mode` (Boolean)
- Manage state transitions based on operator input, system events, and safety conditions
- Coordinate with safety systems through service calls or action interfaces

**Key Topics Published**:
- `/robot_state` (std_msgs/String or custom msg): Current robot state
- `/autonomous_mode` (std_msgs/Bool): Whether autonomous operation is enabled

**Key Services Provided**:
- State transition requests (e.g., SetState, SetAutonomousMode)

### 2. Sentor

**Current Repository**: LCAS/sentor

**Responsibilities**:
- Monitor critical topics and nodes for health and safety
- Publish safety heartbeat (`/safety/heartbeat`) for safety-critical systems
- Publish warning heartbeat (`/warning/heartbeat`) for autonomy-critical systems
- Trigger safety responses when monitored conditions fail
- Provide override services for manual safety intervention

**Key Topics Published**:
- `/safety/heartbeat` (std_msgs/Bool): TRUE when all safety-critical monitors pass
- `/warning/heartbeat` (std_msgs/Bool): TRUE when all autonomy-critical monitors pass

**Key Services Provided**:
- `/sentor/override_safety` (SetBool): Manual safety override
- `/sentor/override_warning` (SetBool): Manual warning override

### 3. Nav2 Stack

**Documentation**: https://docs.nav2.org/

**Responsibilities**:
- Execute autonomous navigation tasks
- Follow paths while avoiding obstacles
- Respond to preemption and cancellation requests
- Maintain behavior trees for navigation logic

**Key Topics Subscribed**:
- `/goal_pose` (geometry_msgs/PoseStamped): Navigation goals

**Key Topics Published**:
- `/cmd_vel` (geometry_msgs/Twist): Velocity commands to robot base

**Key Actions**:
- `NavigateToPose`: Navigate to a specific pose
- `FollowPath`: Follow a pre-computed path

### 4. Safety Controller Node (NEW)

**Proposed New Component**

**Responsibilities**:
- Subscribe to `/robot_state`, `/autonomous_mode`, `/safety/heartbeat`, `/warning/heartbeat`
- Compute combined safety condition: `robot_state == "active" AND autonomous_mode == true`
- Control Nav2 lifecycle states (activate/deactivate/pause)
- Cancel active navigation goals when safety conditions become invalid
- Optionally gate `cmd_vel` commands as a last-resort safety measure

**Implementation Options**: See [Nav2 Integration Strategies](#nav2-integration-strategies)

---

## Integration Architecture

### Information Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                    Information Flow                              │
└──────────────────────────────────────────────────────────────────┘

  RobotStateMachine          Sentor               Safety Controller
        │                      │                          │
        │ /robot_state         │                          │
        ├─────────────────────────────────────────────────>│
        │ /autonomous_mode     │                          │
        ├─────────────────────────────────────────────────>│
        │                      │ /safety/heartbeat        │
        │                      ├──────────────────────────>│
        │                      │ /warning/heartbeat       │
        │                      ├──────────────────────────>│
        │                      │                          │
        │                      │           [Evaluates:    │
        │                      │            state+mode+   │
        │                      │            heartbeats]   │
        │                      │                          │
        │                      │         IF SAFE:         │
        │                      │      - Activate Nav2     │
        │                      │      - Allow navigation  │
        │                      │                          │
        │                      │         IF UNSAFE:       │
        │                      │      - Pause Nav2        │
        │                      │      - Cancel goals      │
        │                      │      - Gate cmd_vel      │
        │                      │                          │
        │                      │                          ├─────>
        │                      │                          │ Nav2
        │                      │                          │  - Lifecycle
        │                      │                          │  - Goal Cancel
```

### Key Integration Points

1. **Topic Subscriptions**: Safety Controller subscribes to all decision-making topics
2. **Nav2 Lifecycle Management**: Safety Controller uses Nav2 lifecycle services
3. **Goal Cancellation**: Safety Controller can cancel navigation actions
4. **Velocity Gating**: Optional safety layer that can zero out cmd_vel

---

## Safety-Critical Topics and Interfaces

### Required Topics

| Topic | Type | Publisher | Purpose |
|-------|------|-----------|---------|
| `/robot_state` | std_msgs/String (or custom) | RobotStateMachine | Current operational state |
| `/autonomous_mode` | std_msgs/Bool | RobotStateMachine | Autonomous mode flag |
| `/safety/heartbeat` | std_msgs/Bool | Sentor | Safety-critical system health |
| `/warning/heartbeat` | std_msgs/Bool | Sentor | Autonomy-critical system health |
| `/cmd_vel` | geometry_msgs/Twist | Nav2 | Velocity commands (monitored/gated) |

### Recommended Topics for Monitoring

The following topics should be configured in Sentor's monitoring configuration:

1. **Navigation Stack Topics** (autonomy_critical: true):
   - `/odom` - Odometry feed
   - `/scan` or `/lidar` - Obstacle detection sensors
   - `/map` - Localization map
   - `/amcl_pose` or `/pose` - Localization output

2. **Critical Sensor Topics** (safety_critical: true):
   - Emergency stop button status
   - Battery voltage/state
   - Motor controller status
   - Critical safety sensors

3. **Node Monitors** (autonomy_critical: true):
   - Nav2 controller server
   - Nav2 planner server
   - Nav2 behavior server
   - Localization node (AMCL or other)

### Required Services

| Service | Type | Provider | Purpose |
|---------|------|----------|---------|
| Nav2 Lifecycle Services | lifecycle_msgs/srv/ChangeState | Nav2 nodes | Control Nav2 node states |
| Goal Cancellation | action_msgs/srv/CancelGoal | Nav2 action servers | Stop active navigation |
| State Transition | custom_msgs/srv/SetState | RobotStateMachine | Change robot state |

---

## State Transition Handling

### Valid States for Autonomous Navigation

Only the following condition permits autonomous navigation:
```python
safe_to_navigate = (robot_state == "active" and 
                   autonomous_mode == True and
                   safety_heartbeat == True and
                   warning_heartbeat == True)
```

### State Transition Scenarios

#### Scenario 1: Normal Activation
```
Initial: robot_state="idle", autonomous_mode=false
1. Operator enables autonomous mode → autonomous_mode=true
2. Operator activates robot → robot_state="active"
3. All monitors healthy → safety_heartbeat=true, warning_heartbeat=true
4. Safety Controller activates Nav2 → Navigation enabled
```

#### Scenario 2: Emergency Stop During Navigation
```
Active Navigation: robot_state="active", autonomous_mode=true
1. Emergency stop pressed → robot_state="emergency_stop"
2. Safety Controller detects state change (< 100ms)
3. Immediate actions:
   a. Cancel all active Nav2 goals
   b. Transition Nav2 to inactive lifecycle state
   c. Publish zero velocity to cmd_vel (if gating enabled)
4. Result: Robot stops immediately, navigation preempted
```

#### Scenario 3: Sensor Failure During Navigation
```
Active Navigation: All conditions satisfied
1. Critical sensor stops publishing → Sentor detects failure
2. warning_heartbeat → false (autonomy_critical sensor failed)
3. Safety Controller detects heartbeat change
4. Immediate actions:
   a. Cancel active navigation goal
   b. Pause Nav2 (optional: deactivate)
   c. Gate cmd_vel to zero
5. Result: Robot stops, waits for recovery or manual intervention
```

#### Scenario 4: Mode Change During Navigation
```
Active Navigation: robot_state="active", autonomous_mode=true
1. Operator switches to manual mode → autonomous_mode=false
2. Safety Controller detects mode change
3. Immediate actions:
   a. Cancel active navigation goal
   b. Deactivate Nav2 or transition to paused
4. Result: Robot stops autonomous navigation, ready for manual control
```

#### Scenario 5: Recovery After Fault
```
Stopped: warning_heartbeat=false (sensor recovered)
1. Sensor resumes normal operation
2. Sentor detects recovery after safe_operation_timeout
3. warning_heartbeat → true
4. Safety Controller observes all conditions satisfied
5. Safety Controller reactivates Nav2 → Navigation can resume
Note: Navigation goals are NOT automatically reissued; operator or higher-level 
      planner must send new goals.
```

### Reaction Time Requirements

- **State/Mode Change Detection**: < 100ms
- **Goal Cancellation**: < 200ms
- **Velocity Command Gating**: < 50ms
- **Total Stop Time**: < 500ms from trigger to zero motion

---

## Nav2 Integration Strategies

There are multiple approaches to integrate safety conditions with Nav2. We recommend a layered approach combining lifecycle management and behavior tree integration.

### Strategy 1: Lifecycle Management (RECOMMENDED)

**Approach**: Control Nav2 node lifecycle states based on safety conditions.

**Implementation**:
1. Safety Controller subscribes to all safety topics
2. When safe_to_navigate becomes FALSE:
   - Call lifecycle transition services to deactivate Nav2 nodes
   - Cancel any active navigation actions
3. When safe_to_navigate becomes TRUE:
   - Activate Nav2 nodes to ready state
   - Allow new navigation goals

**Pros**:
- Clean separation of concerns
- Well-defined ROS2 lifecycle pattern
- Nav2 fully aware of activation/deactivation
- No modification to Nav2 required

**Cons**:
- Lifecycle transitions take 100-500ms
- Need to manage state of multiple Nav2 nodes
- May be too slow for immediate emergency stops

**Example Lifecycle States**:
```
INACTIVE → ACTIVE: When safe_to_navigate becomes true
ACTIVE → INACTIVE: When safe_to_navigate becomes false
```

### Strategy 2: Behavior Tree Plugin (RECOMMENDED for Fine-Grained Control)

**Approach**: Create custom BT condition nodes that check safety conditions.

**Implementation**:
1. Create custom Nav2 BT plugin: `CheckSafetyCondition`
2. Plugin subscribes to `/robot_state`, `/autonomous_mode`, heartbeats
3. BT returns FAILURE when safety conditions invalid
4. Nav2 behavior tree configured with condition checks at strategic points

**Pros**:
- Fine-grained control within navigation logic
- Fast response (BT ticks at ~10-20Hz)
- Integrates naturally with Nav2 architecture
- Can handle different safety levels differently

**Cons**:
- Requires custom Nav2 plugin development
- Must modify Nav2 behavior tree XML
- Safety logic distributed between Safety Controller and BT

**Example BT Structure**:
```xml
<BehaviorTree>
  <Sequence>
    <CheckSafetyCondition topic="/robot_state" expected_value="active"/>
    <CheckSafetyCondition topic="/autonomous_mode" expected_value="true"/>
    <CheckSafetyCondition topic="/safety/heartbeat" expected_value="true"/>
    <CheckSafetyCondition topic="/warning/heartbeat" expected_value="true"/>
    <NavigateToPose/>
  </Sequence>
</BehaviorTree>
```

### Strategy 3: Action Server Wrapper (ALTERNATIVE)

**Approach**: Wrap Nav2 action servers with safety-aware proxy action servers.

**Implementation**:
1. Create proxy action server for NavigateToPose
2. Proxy checks safety conditions before forwarding goals to Nav2
3. Proxy monitors conditions during execution, cancels if invalid
4. Higher-level planners call proxy instead of Nav2 directly

**Pros**:
- No modification to Nav2
- Centralized safety logic
- Can add additional functionality (logging, metrics)

**Cons**:
- Additional latency from proxy layer
- Complexity of maintaining action state
- Must implement proxy for each action type

### Strategy 4: cmd_vel Filter Node (LAST RESORT SAFETY)

**Approach**: Final safety gate that can zero out velocity commands.

**Implementation**:
1. Place filter node between Nav2 and robot base
2. Filter subscribes to safety condition topics
3. Filter passes through cmd_vel when safe, zeros it when unsafe
4. Acts as hardware-level safety cutoff

**Pros**:
- Immediate response (< 50ms)
- Works regardless of Nav2 state
- Last line of defense
- Simple implementation

**Cons**:
- Doesn't provide feedback to Nav2 (Nav2 thinks it's still navigating)
- Can cause confusion in Nav2 state machine
- Should be used in addition to, not instead of, proper integration

### Recommended Hybrid Approach

**Combine multiple strategies for defense-in-depth**:

1. **Primary**: Lifecycle Management (Strategy 1)
   - Activate/deactivate Nav2 based on safety conditions
   - Provides clean state transitions

2. **Secondary**: Behavior Tree Integration (Strategy 2)
   - Add safety condition checks in BT for faster response
   - Allows graceful handling within navigation logic

3. **Tertiary**: cmd_vel Filter (Strategy 4)
   - Emergency safety gate as last resort
   - Ensures robot never moves when unsafe, even if primary/secondary fail

```
┌─────────────────────────────────────────────────────────────┐
│  Multi-Layer Safety Architecture                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 1: Safety Controller (Lifecycle Management)         │
│    └─> Activates/Deactivates Nav2 nodes                    │
│    └─> Cancels navigation goals                            │
│                                                             │
│  Layer 2: Nav2 Behavior Tree (Condition Checks)            │
│    └─> Safety conditions checked in BT                     │
│    └─> Fails gracefully when conditions invalid            │
│                                                             │
│  Layer 3: cmd_vel Filter (Emergency Gate)                  │
│    └─> Zeros velocity commands when unsafe                 │
│    └─> Last line of defense                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Emergency Stop Behavior

### Requirements

When any safety condition becomes invalid, the system must:

1. **Immediately stop motion** (< 500ms total latency)
2. **Cancel all active navigation goals**
3. **Prevent new navigation goals from starting**
4. **Report failure status** appropriately to calling systems
5. **Log the event** for debugging and safety analysis

### Implementation Sequence

```
┌────────────────────────────────────────────────────────────┐
│  Emergency Stop Sequence                                   │
└────────────────────────────────────────────────────────────┘

1. Safety Condition Invalid Detected (t=0ms)
   ↓
2. Safety Controller Triggered (t < 50ms)
   ├─> Cancel all active Nav2 action goals
   ├─> Publish zero cmd_vel (if filtering enabled)
   └─> Transition Nav2 lifecycle to INACTIVE
   ↓
3. Nav2 Receives Cancellation (t < 200ms)
   ├─> Behavior Tree preempted
   ├─> Local planner stops generating paths
   └─> Controller stops publishing cmd_vel
   ↓
4. Robot Motion Stops (t < 500ms)
   └─> Velocity commands cease
   ↓
5. System in Safe State
   ├─> Navigation disabled
   ├─> Robot stationary
   └─> Waiting for safety conditions to be restored
```

### Recovery Procedure

After safety conditions are restored:

1. **Validation Period**: Wait for Sentor's `safe_operation_timeout` (default: 10s)
2. **Heartbeat Confirmation**: Ensure heartbeats remain TRUE
3. **State Verification**: Confirm robot_state == "active" and autonomous_mode == true
4. **Nav2 Reactivation**: Transition Nav2 nodes back to ACTIVE
5. **Ready for Commands**: System ready to accept new navigation goals

**Important**: The system should NOT automatically resume interrupted navigation. The higher-level planner or operator must explicitly send a new navigation goal.

---

## Implementation Recommendations

### Phase 1: Safety Controller Node Development

**Priority**: HIGH  
**Dependencies**: None

**Tasks**:
1. Create new ROS2 package: `sentor_safety_controller`
2. Implement Safety Controller node with:
   - Subscriptions to all safety-critical topics
   - Logic to evaluate combined safety condition
   - Publisher for aggregated safety status (optional, for monitoring)
   - Service client for Nav2 lifecycle management
   - Action client for goal cancellation
3. Add configurable parameters:
   - Topic names for flexibility
   - Reaction time thresholds
   - Logging verbosity
4. Implement comprehensive logging for all state changes

**Example Configuration**:
```yaml
safety_controller:
  ros__parameters:
    robot_state_topic: "/robot_state"
    autonomous_mode_topic: "/autonomous_mode"
    safety_heartbeat_topic: "/safety/heartbeat"
    warning_heartbeat_topic: "/warning/heartbeat"
    
    nav2_controller_node: "/controller_server"
    nav2_planner_node: "/planner_server"
    nav2_bt_navigator_node: "/bt_navigator"
    
    reaction_time_threshold: 0.1  # seconds
    enable_cmd_vel_filter: true
    
    expected_active_state: "active"  # Expected value for robot_state
```

### Phase 2: Sentor Configuration Enhancement

**Priority**: HIGH  
**Dependencies**: Understanding of Nav2 deployment

**Tasks**:
1. Create reference Sentor configuration for Nav2 integration
2. Define monitoring rules for:
   - Navigation stack nodes (autonomy_critical: true)
   - Critical sensors (safety_critical: true)
   - Localization topics (autonomy_critical: true)
3. Set appropriate timeouts and thresholds
4. Document configuration guidelines

**Example Sentor Configuration Snippet**:
```yaml
monitors:
  - name: "/scan"
    message_type: "sensor_msgs/msg/LaserScan"
    rate: 10.0
    signal_when:
      condition: "published"
      timeout: 1.0
      autonomy_critical: true
    tags: ["navigation", "obstacle_detection"]

node_monitors:
  - name: "/controller_server"
    timeout: 2.0
    autonomy_critical: true
    tags: ["nav2", "controller"]
    
  - name: "/planner_server"
    timeout: 2.0
    autonomy_critical: true
    tags: ["nav2", "planner"]
```

### Phase 3: Nav2 Behavior Tree Plugin (Optional but Recommended)

**Priority**: MEDIUM  
**Dependencies**: Phase 1 complete

**Tasks**:
1. Create custom Nav2 BT plugin package: `sentor_nav2_bt_plugins`
2. Implement `CheckSafetyCondition` BT node
3. Implement `CheckRobotState` BT node
4. Create example BT XML configurations
5. Document BT integration patterns

### Phase 4: cmd_vel Filter Node (Safety Backup)

**Priority**: MEDIUM  
**Dependencies**: Phase 1 complete

**Tasks**:
1. Create velocity filter node package: `sentor_velocity_filter`
2. Implement filter with:
   - Input: cmd_vel from Nav2
   - Output: filtered cmd_vel to robot base
   - Safety condition checking
   - Configurable ramping for smooth stops
3. Add telemetry and diagnostics
4. Test with various robot bases

### Phase 5: Integration Testing Framework

**Priority**: HIGH  
**Dependencies**: Phases 1-4

**Tasks**:
1. Create simulation environment (Gazebo/Ignition)
2. Implement test scenarios for each failure mode
3. Develop automated test suite
4. Create validation metrics and dashboards
5. Document test procedures and acceptance criteria

### Phase 6: Documentation and Training

**Priority**: MEDIUM  
**Dependencies**: All phases

**Tasks**:
1. Create integration guide for robot deployers
2. Document configuration templates
3. Write troubleshooting guide
4. Create training materials
5. Produce video tutorials

---

## Testing and Validation Strategy

### Test Categories

#### 1. Unit Tests

Test individual components in isolation:
- Safety Controller logic (condition evaluation)
- Topic callback handling
- Service call mechanisms
- State machine transitions

#### 2. Integration Tests

Test component interactions:
- Safety Controller ↔ Nav2 lifecycle
- Safety Controller ↔ RobotStateMachine
- Sentor ↔ Safety Controller
- End-to-end safety condition propagation

#### 3. Scenario Tests

Test real-world scenarios:
- Normal navigation operation
- Emergency stop during motion
- Sensor failure recovery
- Mode switching during navigation
- Multiple simultaneous failures

#### 4. Performance Tests

Validate timing requirements:
- Reaction time measurements (< 100ms target)
- End-to-end stop time (< 500ms target)
- System latency under load
- Resource utilization

### Test Scenarios

#### Scenario 1: Emergency Stop During Navigation

**Setup**:
- Robot navigating autonomously
- All safety conditions satisfied

**Trigger**: Simulate emergency stop button press (robot_state → "emergency_stop")

**Expected Behavior**:
1. Safety Controller detects state change within 100ms
2. Navigation goal cancelled within 200ms
3. Robot motion stops within 500ms
4. Nav2 in inactive state
5. Event logged with timestamp

**Validation**:
- Record all timestamps
- Verify no cmd_vel published after stop
- Verify Nav2 action status reported as ABORTED or PREEMPTED

#### Scenario 2: Critical Sensor Failure

**Setup**:
- Robot navigating autonomously
- All safety conditions satisfied

**Trigger**: Stop publishing on critical sensor topic (e.g., /scan)

**Expected Behavior**:
1. Sentor detects missing messages within sensor timeout
2. warning_heartbeat → false
3. Safety Controller cancels navigation
4. Robot stops
5. System waits for sensor recovery

**Validation**:
- Verify heartbeat transitions
- Verify navigation preempted
- Verify system ready to resume after recovery

#### Scenario 3: Autonomous Mode Disabled During Navigation

**Setup**:
- Robot navigating autonomously

**Trigger**: Set autonomous_mode → false

**Expected Behavior**:
1. Safety Controller detects mode change
2. Navigation cancelled
3. Robot stops
4. Manual control enabled

**Validation**:
- Verify mode change detected
- Verify clean shutdown of navigation
- Verify manual control commands work

#### Scenario 4: Recovery After Transient Failure

**Setup**:
- System in stopped state due to sensor failure
- Sensor recovers and resumes publishing

**Expected Behavior**:
1. Sentor detects sensor recovery
2. After safe_operation_timeout, heartbeat → true
3. Safety Controller enables Nav2
4. System ready for new navigation goals

**Validation**:
- Verify timeout period honored
- Verify Nav2 properly reactivated
- Verify new goals can be executed

### Validation Metrics

| Metric | Target | Critical |
|--------|--------|----------|
| State change detection latency | < 100ms | YES |
| Goal cancellation latency | < 200ms | YES |
| Total stop time | < 500ms | YES |
| False positive rate | < 0.1% | NO |
| System availability | > 99.9% | NO |
| Recovery time after transient fault | < 15s | NO |

### Test Environment Setup

**Simulation**:
- Use Gazebo or Ignition with Nav2-compatible robot
- Implement mock RobotStateMachine node
- Configure Sentor with test monitors
- Create test scenarios with scripted triggers

**Hardware**:
- Test on actual robot platform
- Use real sensors and safety systems
- Validate timing on target compute platform
- Test with actual emergency stop hardware

---

## Failure Modes and Mitigation

### Failure Mode 1: Safety Controller Node Crash

**Symptom**: Safety Controller stops running during navigation

**Risk**: Robot continues navigating without safety oversight

**Mitigation**:
1. **Watchdog**: Implement watchdog that monitors Safety Controller heartbeat
2. **Failsafe**: Configure Nav2 with conservative behavior (lower speeds, larger safety margins)
3. **Redundancy**: Run multiple Safety Controller instances with different priorities
4. **Monitoring**: Add Safety Controller to Sentor node monitors as safety_critical

### Failure Mode 2: Topic Communication Failure

**Symptom**: Safety topics not received by Safety Controller

**Risk**: Stale safety data leads to incorrect decisions

**Mitigation**:
1. **Timeouts**: Implement message age checks, treat old data as invalid
2. **QoS Settings**: Use reliable QoS for safety-critical topics
3. **Monitoring**: Monitor Safety Controller's subscription health
4. **Failsafe**: Default to unsafe state if no recent messages

### Failure Mode 3: Nav2 Lifecycle Service Failure

**Symptom**: Lifecycle service calls fail or timeout

**Risk**: Nav2 remains active when it should be deactivated

**Mitigation**:
1. **Retry Logic**: Implement retries with exponential backoff
2. **cmd_vel Filter**: Fallback to velocity filtering if lifecycle fails
3. **Escalation**: Trigger system-level emergency stop if repeated failures
4. **Monitoring**: Log all service call failures for analysis

### Failure Mode 4: Race Condition Between State Changes

**Symptom**: Rapid state changes cause inconsistent safety decisions

**Risk**: Brief periods where robot state and safety state mismatch

**Mitigation**:
1. **State Machine**: Implement proper state machine in Safety Controller
2. **Debouncing**: Add short debounce period for state changes (e.g., 50ms)
3. **Locking**: Use thread-safe state access
4. **Prioritization**: Emergency stop always takes precedence

### Failure Mode 5: RobotStateMachine Publishing Incorrect State

**Symptom**: robot_state doesn't reflect actual robot condition

**Risk**: Safety system makes decisions on false information

**Mitigation**:
1. **Sentor Monitoring**: Add RobotStateMachine node to node_monitors
2. **Redundancy**: Cross-check state with other sensors (e.g., motor controller status)
3. **Validation**: Implement state validation checks (e.g., can't be "active" if motors disabled)
4. **Override**: Provide manual override capability

### Failure Mode 6: Network Congestion or Delays

**Symptom**: Safety messages delayed beyond acceptable latency

**Risk**: Delayed reaction to dangerous conditions

**Mitigation**:
1. **QoS Configuration**: Use appropriate QoS profiles (deadline, liveliness)
2. **Priority**: Use DDS priority settings for safety-critical topics
3. **Dedicated Network**: Consider dedicated network for safety communications
4. **Monitoring**: Monitor network latency and topic timing

### Failure Mode 7: Partial Nav2 Deactivation

**Symptom**: Some Nav2 nodes deactivate but others remain active

**Risk**: Inconsistent Nav2 state, potential for unexpected behavior

**Mitigation**:
1. **Atomic Operations**: Group lifecycle transitions where possible
2. **State Verification**: Verify all nodes reach expected state
3. **Rollback**: Roll back partial transitions
4. **cmd_vel Filter**: Rely on velocity filtering as backup

---

## Appendix A: Message and Service Definitions

### Custom Messages (if needed)

#### RobotState.msg
```
# Custom message for robot state (alternative to std_msgs/String)
string state           # e.g., "idle", "active", "paused", "emergency_stop"
time timestamp         # When state was entered
string previous_state  # Previous state for debugging
uint32 state_count     # Number of state transitions
```

#### SafetyStatus.msg
```
# Aggregated safety status from Safety Controller
bool safe_to_navigate
string robot_state
bool autonomous_mode
bool safety_heartbeat
bool warning_heartbeat
time last_update
string blocking_condition  # Which condition is false, if any
```

### Service Definitions

Most services can use standard ROS2 interfaces:
- `std_srvs/SetBool` - For simple enable/disable
- `lifecycle_msgs/ChangeState` - For Nav2 lifecycle
- `action_msgs/CancelGoal` - For cancelling navigation

---

## Appendix B: Configuration Templates

### Safety Controller Launch File

```python
# sentor_safety_controller_launch.py
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'robot_state_topic',
            default_value='/robot_state',
            description='Topic for robot state'
        ),
        DeclareLaunchArgument(
            'autonomous_mode_topic',
            default_value='/autonomous_mode',
            description='Topic for autonomous mode flag'
        ),
        
        Node(
            package='sentor_safety_controller',
            executable='safety_controller_node',
            name='safety_controller',
            output='screen',
            parameters=[{
                'robot_state_topic': LaunchConfiguration('robot_state_topic'),
                'autonomous_mode_topic': LaunchConfiguration('autonomous_mode_topic'),
                'safety_heartbeat_topic': '/safety/heartbeat',
                'warning_heartbeat_topic': '/warning/heartbeat',
                'enable_cmd_vel_filter': True,
                'reaction_time_threshold': 0.1,
            }]
        ),
    ])
```

### Complete System Launch

```python
# sentor_nav2_system_launch.py
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # Launch RobotStateMachine
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource('path/to/robot_state_machine_launch.py')
        ),
        
        # Launch Sentor
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource('path/to/sentor_launch.py'),
            launch_arguments={
                'config_file': 'path/to/nav2_sentor_config.yaml',
            }.items()
        ),
        
        # Launch Safety Controller
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource('path/to/safety_controller_launch.py')
        ),
        
        # Launch Nav2
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource('path/to/nav2_bringup_launch.py')
        ),
        
        # Optional: Launch cmd_vel filter
        Node(
            package='sentor_velocity_filter',
            executable='velocity_filter_node',
            name='velocity_filter',
            remappings=[
                ('cmd_vel_in', '/cmd_vel'),
                ('cmd_vel_out', '/cmd_vel_filtered'),
            ]
        ),
    ])
```

### Sentor Configuration for Nav2

```yaml
# nav2_sentor_config.yaml
monitors:
  # Critical Navigation Sensors
  - name: "/scan"
    message_type: "sensor_msgs/msg/LaserScan"
    rate: 10.0
    N: 5
    signal_when:
      condition: "published"
      timeout: 1.0
      autonomy_critical: true
      tags: ["nav2", "sensor", "lidar"]
  
  - name: "/odom"
    message_type: "nav_msgs/msg/Odometry"
    rate: 20.0
    N: 10
    signal_when:
      condition: "published"
      timeout: 0.5
      autonomy_critical: true
      tags: ["nav2", "odometry"]
  
  - name: "/amcl_pose"
    message_type: "geometry_msgs/msg/PoseWithCovarianceStamped"
    rate: 10.0
    signal_when:
      condition: "published"
      timeout: 1.0
      autonomy_critical: true
      tags: ["nav2", "localization"]
  
  # Safety-Critical Sensors
  - name: "/emergency_stop"
    message_type: "std_msgs/msg/Bool"
    rate: 5.0
    signal_lambdas:
      - expression: "lambda x: x.data == False"  # False means NOT stopped
        timeout: 0.5
        safety_critical: true
        tags: ["safety", "estop"]

node_monitors:
  # Nav2 Nodes
  - name: "/controller_server"
    timeout: 2.0
    autonomy_critical: true
    poll_rate: 2.0
    tags: ["nav2", "controller"]
  
  - name: "/planner_server"
    timeout: 2.0
    autonomy_critical: true
    poll_rate: 2.0
    tags: ["nav2", "planner"]
  
  - name: "/bt_navigator"
    timeout: 2.0
    autonomy_critical: true
    poll_rate: 2.0
    tags: ["nav2", "bt"]
  
  - name: "/amcl"
    timeout: 2.0
    autonomy_critical: true
    poll_rate: 2.0
    tags: ["nav2", "localization"]
  
  # Safety-Critical System Nodes
  - name: "/robot_state_machine"
    timeout: 2.0
    safety_critical: true
    poll_rate: 2.0
    tags: ["safety", "state_machine"]
  
  - name: "/safety_controller"
    timeout: 2.0
    safety_critical: true
    poll_rate: 2.0
    tags: ["safety", "controller"]
```

---

## Appendix C: References and Related Documentation

### External Resources

1. **Nav2 Documentation**: https://docs.nav2.org/
   - Lifecycle management: https://docs.nav2.org/configuration/packages/configuring-lifecycle.html
   - Behavior Trees: https://docs.nav2.org/behavior_trees/index.html

2. **RobotStateMachine**: https://github.com/LCAS/RobotStateMachine
   - State machine implementation and interfaces

3. **ROS2 Lifecycle**: https://design.ros2.org/articles/node_lifecycle.html
   - Understanding managed nodes

4. **ROS2 QoS**: https://docs.ros.org/en/rolling/Concepts/About-Quality-of-Service-Settings.html
   - Reliability, durability, and deadline policies for safety-critical topics

### Related Standards

1. **ISO 13849** - Safety of machinery
2. **IEC 61508** - Functional safety of electrical/electronic systems
3. **ISO 10218** - Robots and robotic devices (if applicable)

### Internal Documentation

1. Sentor README: `/README.md`
2. Sentor Wiki: https://github.com/LCAS/sentor/wiki/sentor

---

## Appendix D: Glossary

| Term | Definition |
|------|------------|
| **Active State** | Robot operational state where autonomous navigation is permitted |
| **Autonomous Mode** | Flag indicating whether autonomous control is enabled |
| **Behavior Tree (BT)** | Tree structure used by Nav2 for navigation logic |
| **Heartbeat** | Periodic signal indicating system health |
| **Lifecycle Node** | ROS2 managed node with defined state transitions |
| **Safety-Critical** | Systems or conditions whose failure could cause harm |
| **Autonomy-Critical** | Systems or conditions required for autonomous operation |
| **Safe-to-Navigate** | Combined condition permitting autonomous navigation |
| **Emergency Stop** | Immediate halt of all robot motion |
| **QoS** | Quality of Service policies for ROS2 communication |

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-10 | GitHub Copilot | Initial concept architecture |

---

## Conclusion

This concept architecture provides a comprehensive framework for integrating Sentor, RobotStateMachine, and Nav2 to ensure safe and compliant autonomous navigation. The key principles are:

1. **Defense in Depth**: Multiple layers of safety (lifecycle, BT, velocity filter)
2. **Clear Responsibility**: Well-defined roles for each component
3. **Fast Response**: Sub-500ms reaction to safety violations
4. **Clean Integration**: Uses standard ROS2 patterns (lifecycle, actions, topics)
5. **Extensibility**: Framework can accommodate additional safety requirements

The recommended implementation follows a phased approach, starting with the Safety Controller as the central coordination point, then adding additional layers for robustness. The system is designed to fail safe, with multiple independent mechanisms ensuring the robot stops when conditions are unsafe.

Next steps should focus on creating a minimal viable implementation of the Safety Controller and validating the approach in simulation before proceeding to hardware deployment.
