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
- Clean, well-defined ROS2 pattern
- ~100-500ms response time

### Layer 2: Behavior Tree Integration (Secondary)
- Custom BT plugins check safety conditions within Nav2
- Faster response (~50-100ms)
- Requires Nav2 customization

### Layer 3: cmd_vel Filter (Emergency Backup)
- Filter node between Nav2 and robot base
- Zeros velocity commands when unsafe
- <50ms response time
- Last line of defense

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

### Phase 1: Core Safety Controller (HIGH PRIORITY)
- Create `sentor_safety_controller` package
- Implement safety condition evaluation
- Add Nav2 lifecycle management
- Add goal cancellation capability

### Phase 2: Sentor Configuration (HIGH PRIORITY)
- Create Nav2-specific monitoring configuration
- Define which topics/nodes are safety-critical vs autonomy-critical
- Set appropriate timeouts

### Phase 3: Nav2 BT Plugin (MEDIUM PRIORITY)
- Create custom BT condition nodes
- Integrate safety checks into navigation logic

### Phase 4: cmd_vel Filter (MEDIUM PRIORITY)
- Create velocity filter as safety backup
- Add telemetry and diagnostics

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
