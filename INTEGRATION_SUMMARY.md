# Integration Summary: Sentor + RobotStateMachine + Nav2

## Quick Reference Guide

This document provides a high-level overview of the proposed integration architecture. For complete details, see [ARCHITECTURE_INTEGRATION.md](ARCHITECTURE_INTEGRATION.md).

---

## Core Safety Requirement

Autonomous navigation is permitted **ONLY** when:

```python
robot_state == "active" AND autonomous_mode == True
```

Additionally recommended:
```python
safety_heartbeat == True AND warning_heartbeat == True
```

Any violation must immediately stop the robot and cancel navigation.

---

## System Components

| Component | Role | Key Output |
|-----------|------|------------|
| **RobotStateMachine** | Manages robot operational state and mode | `/robot_state`, `/autonomous_mode` |
| **Sentor** | Monitors system health | `/safety/heartbeat`, `/warning/heartbeat` |
| **Safety Controller** (NEW) | Coordinates safety conditions with Nav2 | Lifecycle management, goal cancellation |
| **sentor_guard** (NEW) | Reusable safety libraries and nodes | Python/C++ guards, topic filters, lifecycle mgmt |
| **Nav2** | Autonomous navigation | Navigation goals, motion commands |

---

## Architecture Overview

```
RobotStateMachine ──┐
                    ├──> Safety Controller ──> Nav2 ──> Robot Base
Sentor ─────────────┘
```

**Safety Controller** is the new component that:
1. Subscribes to all safety condition topics
2. Controls Nav2 activation/deactivation based on conditions
3. Cancels navigation goals when conditions become invalid
4. Optionally filters velocity commands as last-resort safety

---

## Integration Approach: Multi-Layer Safety

### Layer 1: Lifecycle Management (Primary)
- Safety Controller activates/deactivates Nav2 based on safety conditions
- Uses **sentor_guard** libraries for condition checking
- Clean, well-defined ROS2 pattern
- ~100-500ms response time

### Layer 2: Behavior Tree Integration (✅ Implemented)
- `CheckAutonomyAllowed` BT condition node checks safety in Nav2
- Uses **sentor_guard** C++ library for condition evaluation
- Faster response (~50-100ms) with continuous monitoring
- Enables graceful pause/resume of navigation
- Integrates via standard BehaviorTree.CPP plugin mechanism
- Example BTs and launch files provided in `sentor_guard/examples/nav2_examples/`

### Layer 3: cmd_vel Filter (Emergency Backup)
- **sentor_guard** Topic Guard node filters cmd_vel
- Zeros velocity commands when unsafe
- <50ms response time
- Last line of defense

### Additional: Application-Level Guards
- **sentor_guard** Python/C++ libraries in user code
- Context managers and RAII patterns
- Blocks execution until safe
- Defense in depth throughout the system

---

## State Transition Examples

### Normal Operation
```
1. autonomous_mode ← true
2. robot_state ← "active"
3. All monitors healthy (heartbeats ← true)
4. Safety Controller activates Nav2
5. Navigation goals accepted and executed
```

### Emergency Stop
```
1. Emergency button pressed → robot_state ← "emergency_stop"
2. Safety Controller detects change (< 100ms)
3. Cancels active Nav2 goals (< 200ms)
4. Optionally zeros cmd_vel (< 50ms)
5. Robot stops (< 500ms total)
```

### Sensor Failure
```
1. Critical sensor stops publishing
2. Sentor detects failure → warning_heartbeat ← false
3. Safety Controller cancels navigation
4. Robot stops
5. After recovery + timeout → System ready again
```

---

## Key Timing Requirements

| Event | Target Latency | Critical |
|-------|----------------|----------|
| State change detection | < 100ms | YES |
| Goal cancellation | < 200ms | YES |
| Total stop time | < 500ms | YES |
| Recovery after fault | < 15s | NO |

---

## Implementation Phases

### Phase 1: sentor_guard Package (HIGH PRIORITY)
- Create **`sentor_guard`** package with reusable libraries
- Implement Python guard library (context manager pattern)
- Implement C++ guard library (RAII pattern)
- Add topic guard node and lifecycle guard node
- Include configuration examples and launch files

### Phase 2: Sentor Configuration (HIGH PRIORITY)
- Create Nav2-specific monitoring configuration
- Define which topics/nodes are safety-critical vs autonomy-critical
- Set appropriate timeouts

### Phase 3: Safety Controller (HIGH PRIORITY)
- Create `sentor_safety_controller` package
- Use **sentor_guard** libraries for condition evaluation
- Add Nav2 lifecycle management
- Add goal cancellation capability

### Phase 4: Nav2 BT Plugin (✅ COMPLETED)
- ✅ Created `CheckAutonomyAllowed` BT condition node
- ✅ Integrated with **sentor_guard** C++ library
- ✅ Added optional BehaviorTree.CPP dependency
- ✅ Created example behavior tree XML files
- ✅ Comprehensive integration documentation
- See: `src/sentor_guard/examples/nav2_examples/`

### Phase 5: Testing & Validation (HIGH PRIORITY)
- Simulation testing
- Hardware validation
- Performance benchmarking

---

## Sentor Configuration Example

```yaml
monitors:
  # Autonomy-critical: Required for navigation
  - name: "/scan"
    message_type: "sensor_msgs/msg/LaserScan"
    rate: 10.0
    signal_when:
      condition: "published"
      timeout: 1.0
      autonomy_critical: true
  
  # Safety-critical: Required for safety
  - name: "/emergency_stop"
    message_type: "std_msgs/msg/Bool"
    rate: 5.0
    signal_lambdas:
      - expression: "lambda x: x.data == False"
        timeout: 0.5
        safety_critical: true

node_monitors:
  - name: "/controller_server"
    timeout: 2.0
    autonomy_critical: true
  
  - name: "/safety_controller"
    timeout: 2.0
    safety_critical: true
```

---

## Failure Modes to Address

1. **Safety Controller crashes** → Nav2 continues without oversight
   - *Mitigation*: Monitor Safety Controller with Sentor, implement watchdog

2. **Topic communication failure** → Stale safety data
   - *Mitigation*: Implement message age checks, use reliable QoS

3. **Nav2 lifecycle service fails** → Nav2 stays active
   - *Mitigation*: Fallback to cmd_vel filter, implement retry logic

4. **Race conditions** → Inconsistent state
   - *Mitigation*: Proper state machine, debouncing, thread-safe access

5. **Network congestion** → Delayed reactions
   - *Mitigation*: QoS policies, DDS priorities, dedicated network

---

## Key Design Principles

1. **Defense in Depth**: Multiple independent safety layers
2. **Fail Safe**: System defaults to stopped/inactive on any failure
3. **Fast Response**: Sub-500ms reaction to safety violations
4. **Standard Patterns**: Uses ROS2 lifecycle, actions, and topics
5. **No Nav2 Modification**: Primary approach doesn't require Nav2 changes
6. **Comprehensive Logging**: All state changes logged for analysis

---

## Quick Start: Using the Nav2 BT Integration

The `CheckAutonomyAllowed` behavior tree condition node is now available for direct integration with Nav2. Here's how to use it:

### 1. Build with BT support
```bash
# Install BehaviorTree.CPP if needed
sudo apt install ros-$ROS_DISTRO-behaviortree-cpp

# Build sentor_guard
cd ~/ros2_ws
colcon build --packages-select sentor_guard
source install/setup.bash
```

### 2. Configure Nav2 to load the plugin

Add to your `bt_navigator` parameters:
```yaml
bt_navigator:
  ros__parameters:
    plugin_lib_names:
      # ... other Nav2 plugins ...
      - sentor_guard_bt_nodes  # Add this line
    default_nav_to_pose_bt_xml: /path/to/your/behavior_tree.xml
```

### 3. Use in your behavior tree

Simple pre-navigation check:
```xml
<Sequence>
  <CheckAutonomyAllowed required_state="active"/>
  <ComputePathToPose goal="{goal}" path="{path}"/>
  <FollowPath path="{path}"/>
</Sequence>
```

Continuous monitoring with pause/resume:
```xml
<PipelineSequence>
  <RateController hz="2.0">
    <CheckAutonomyAllowed required_state="active"/>
  </RateController>
  <ComputePathToPose goal="{goal}" path="{path}"/>
  <FollowPath path="{path}"/>
</PipelineSequence>
```

### 4. See complete examples

Full working examples with launch files and documentation:
- `src/sentor_guard/examples/nav2_examples/navigate_with_guard.xml` - Complete BT with recovery
- `src/sentor_guard/examples/nav2_examples/simple_nav_with_guard.xml` - Minimal example
- `src/sentor_guard/examples/nav2_examples/README.md` - Detailed integration guide

---

## Next Steps

1. **Review and approve** this architecture concept
2. **Create Safety Controller package** with basic functionality
3. **Test in simulation** with mock RobotStateMachine
4. **Develop Sentor configuration** for your specific robot/Nav2 setup
5. **Validate timing** on target hardware
6. **Deploy incrementally** with thorough testing at each phase

---

## Questions to Address

Before implementation, clarify:

1. **State Values**: What are the exact state strings used by RobotStateMachine?
   - e.g., "active", "paused", "emergency_stop", "idle"?

2. **Topic Names**: Confirm final topic names for:
   - `/robot_state` 
   - `/autonomous_mode`
   - Nav2 namespaces

3. **QoS Requirements**: What reliability/durability needed for safety topics?

4. **Hardware Platform**: What is the target compute platform?
   - Affects timing validation

5. **Nav2 Configuration**: Are there specific Nav2 customizations already in place?

6. **Recovery Policy**: Should navigation automatically resume after recovery or wait for new goals?
   - **Recommendation**: Wait for explicit new goals (safer)

---

## References

- **Full Architecture Document**: [ARCHITECTURE_INTEGRATION.md](ARCHITECTURE_INTEGRATION.md)
- **sentor_guard Package Design**: [docs/SENTOR_GUARD_DESIGN.md](docs/SENTOR_GUARD_DESIGN.md)
- **Integration Diagrams**: [docs/INTEGRATION_DIAGRAMS.md](docs/INTEGRATION_DIAGRAMS.md)
- **Sentor Documentation**: [README.md](README.md)
- **RobotStateMachine**: https://github.com/LCAS/RobotStateMachine
- **Nav2 Documentation**: https://docs.nav2.org/
- **ROS2 Lifecycle**: https://design.ros2.org/articles/node_lifecycle.html

---

## Contact and Feedback

For questions or suggestions about this architecture:
- Open an issue in the sentor repository
- Reference issue LCAS/sentor#[issue_number]

---

*Document Version: 1.0*  
*Date: 2025-11-10*  
*Status: Concept Proposal*
