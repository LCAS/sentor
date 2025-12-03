# Integration Architecture Diagrams

This document contains ASCII diagrams for the Sentor-RobotStateMachine-Nav2 integration. These diagrams complement the main architecture document.

---

## High-Level System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                       Autonomous Navigation System                     │
└────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────┐
                    │  RobotStateMachine  │
                    │                     │
                    │  • State Management │
                    │  • Mode Control     │
                    └──────────┬──────────┘
                               │
                               │ publishes
                               │
                    ┌──────────▼──────────┐
                    │  /robot_state       │
                    │  /autonomous_mode   │
                    └──────────┬──────────┘
                               │
                               │ subscribed by
                               │
        ┌──────────────────────▼───────────────────────┐
        │                                               │
        │            Safety Controller                  │
        │                                               │
        │  Evaluates: state AND mode AND heartbeats    │
        │                                               │
        └──────────┬─────────────────────┬──────────────┘
                   │                     │
         activates │                     │ subscribes
         lifecycle │                     │
                   │          ┌──────────▼──────────┐
                   │          │     Sentor          │
                   │          │                     │
                   │          │  • Topic Monitors   │
                   │          │  • Node Monitors    │
                   │          └──────────┬──────────┘
                   │                     │
                   │                     │ publishes
                   │                     │
                   │          ┌──────────▼──────────┐
                   │          │ /safety/heartbeat   │
                   │          │ /warning/heartbeat  │
                   │          └─────────────────────┘
                   │
        ┌──────────▼───────────┐
        │                      │
        │     Nav2 Stack       │
        │                      │
        │  • BT Navigator      │
        │  • Controller        │
        │  • Planner           │
        │  • Recoveries        │
        │                      │
        └──────────┬───────────┘
                   │
                   │ publishes
                   │
        ┌──────────▼───────────┐
        │     /cmd_vel         │
        └──────────┬───────────┘
                   │
                   │ (optional filter)
                   │
        ┌──────────▼───────────┐
        │    Robot Base        │
        │   (motors/wheels)    │
        └──────────────────────┘
```

---

## Information Flow - Normal Operation

```
┌──────────────────────────────────────────────────────────────────┐
│                    Normal Navigation Flow                         │
└──────────────────────────────────────────────────────────────────┘

Time: t0 (Initialization)
─────────────────────────

RobotStateMachine:     robot_state = "idle"
                       autonomous_mode = false

Sentor:                safety_heartbeat = false (not ready)
                       warning_heartbeat = false

Safety Controller:     Nav2 = INACTIVE

Nav2:                  Lifecycle state = INACTIVE


Time: t1 (Activation Request)
──────────────────────────────

Operator:              "Enable autonomous mode"
                                │
                                ▼
RobotStateMachine:     autonomous_mode = true
                                │
                                ▼
                       "Activate robot"
                                │
                                ▼
                       robot_state = "active"


Time: t2 (System Health Check)
───────────────────────────────

Sentor:                All monitors healthy
                                │
                                ▼
                       (after safe_operation_timeout)
                                │
                                ▼
                       safety_heartbeat = true
                       warning_heartbeat = true


Time: t3 (Safety Controller Evaluation)
────────────────────────────────────────

Safety Controller:     Checks conditions:
                       ✓ robot_state == "active"
                       ✓ autonomous_mode == true
                       ✓ safety_heartbeat == true
                       ✓ warning_heartbeat == true
                                │
                                ▼
                       SAFE_TO_NAVIGATE = TRUE
                                │
                                ▼
                       Activate Nav2 lifecycle


Time: t4 (Navigation Ready)
───────────────────────────

Nav2:                  Lifecycle state = ACTIVE
                                │
                                ▼
                       Ready to receive goals
                                │
                                ▼
Operator/Planner:      Send NavigateToPose goal
                                │
                                ▼
Nav2:                  Execute navigation
                                │
                                ▼
                       Publish /cmd_vel
                                │
                                ▼
Robot:                 Moves autonomously
```

---

## Emergency Stop Sequence

```
┌──────────────────────────────────────────────────────────────────┐
│                    Emergency Stop Flow                            │
└──────────────────────────────────────────────────────────────────┘

Initial State:         Robot navigating autonomously
                       All safety conditions satisfied

Time: t0 (Emergency Event)
──────────────────────────

Emergency Stop:        Button pressed!
                                │
                                ▼
RobotStateMachine:     robot_state = "emergency_stop"
                       (< 10ms)


Time: t0+50ms (Detection)
──────────────────────────

Safety Controller:     Detects state change
                                │
                                ▼
                       SAFE_TO_NAVIGATE = FALSE
                                │
                                ├─────────────────────┐
                                │                     │
                                ▼                     ▼
                       Cancel Nav2 goals      Publish zero cmd_vel
                                │              (if filter enabled)
                                │                     │
                                ▼                     ▼
                       Request Nav2 deactivate   Overrides Nav2 output


Time: t0+200ms (Nav2 Response)
───────────────────────────────

Nav2:                  Goal cancellation received
                                │
                                ▼
                       Stop behavior tree
                                │
                                ▼
                       Stop publishing cmd_vel
                                │
                                ▼
                       Report goal: ABORTED


Time: t0+500ms (Motion Stop)
─────────────────────────────

Robot Base:            cmd_vel = 0
                                │
                                ▼
                       Robot stopped
                                │
                                ▼
System:                SAFE STATE ACHIEVED


Steady State:          robot_state = "emergency_stop"
                       Nav2 = INACTIVE
                       Robot = stationary
                       Waiting for manual recovery
```

---

## Sensor Failure and Recovery

```
┌──────────────────────────────────────────────────────────────────┐
│                  Sensor Failure & Recovery Flow                   │
└──────────────────────────────────────────────────────────────────┘

Phase 1: Normal Operation
─────────────────────────

All Systems:           Healthy and operating

Lidar (/scan):         Publishing at 10 Hz
                                │
                                ▼
Sentor:                Monitor receives messages
                       warning_heartbeat = true


Phase 2: Sensor Failure
───────────────────────

Lidar:                 STOPS PUBLISHING
                                │
                                ▼
Sentor:                Timeout exceeded (1.0s)
                                │
                                ▼
                       warning_heartbeat = false
                                │
                                ▼
Safety Controller:     Detects heartbeat change
                                │
                                ▼
                       SAFE_TO_NAVIGATE = FALSE
                                │
                                ▼
                       Cancel navigation
                       Deactivate Nav2
                                │
                                ▼
Robot:                 Stops moving


Phase 3: Sensor Recovery
────────────────────────

Lidar:                 Resumes publishing
                                │
                                ▼
Sentor:                Messages received again
                                │
                                ▼
                       Wait safe_operation_timeout (10s)
                                │
                                ▼
                       All checks passed
                                │
                                ▼
                       warning_heartbeat = true
                                │
                                ▼
Safety Controller:     All conditions satisfied
                                │
                                ▼
                       SAFE_TO_NAVIGATE = TRUE
                                │
                                ▼
                       Activate Nav2
                                │
                                ▼
System:                Ready for new navigation goals
                       (does NOT resume previous goal)
```

---

## Multi-Layer Safety Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Defense in Depth                                │
└────────────────────────────────────────────────────────────────────────┘

                              Goal Request
                                   │
                                   ▼
                    ╔══════════════════════════════╗
                    ║   Layer 1: Safety Controller ║
                    ║                              ║
                    ║   • Lifecycle Management     ║
                    ║   • Goal Cancellation        ║
                    ║   • Response: 100-500ms      ║
                    ╚══════════════════════════════╝
                                   │
                              ┌────┴────┐
                              │  PASS?  │
                              └────┬────┘
                                   │ YES
                                   ▼
                    ╔══════════════════════════════╗
                    ║   Layer 2: Nav2 BT Plugin    ║
                    ║                              ║
                    ║   • Condition Checks in BT   ║
                    ║   • Graceful Failures        ║
                    ║   • Response: 50-100ms       ║
                    ╚══════════════════════════════╝
                                   │
                              ┌────┴────┐
                              │  PASS?  │
                              └────┬────┘
                                   │ YES
                                   ▼
                        ┌───────────────────┐
                        │   Nav2 Executes   │
                        │   Navigation      │
                        └────────┬──────────┘
                                 │
                                 │ /cmd_vel
                                 ▼
                    ╔══════════════════════════════╗
                    ║   Layer 3: cmd_vel Filter    ║
                    ║                              ║
                    ║   • Last-resort Gate         ║
                    ║   • Zeros unsafe commands    ║
                    ║   • Response: <50ms          ║
                    ╚══════════════════════════════╝
                                   │
                              ┌────┴────┐
                              │  SAFE?  │
                              └────┬────┘
                                   │ YES
                                   ▼
                        ┌───────────────────┐
                        │   Robot Base      │
                        │   Executes Motion │
                        └───────────────────┘

                              │ NO (at any layer)
                              ▼
                        ┌─────────────┐
                        │  STOP       │
                        │  cmd_vel=0  │
                        └─────────────┘
```

---

## Component State Machine

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Safety Controller State Machine                   │
└────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────┐
                              │  STARTING   │
                              └──────┬──────┘
                                     │
                                     ▼
                              ┌─────────────┐
                         ┌────┤   INACTIVE  │
                         │    └──────┬──────┘
                         │           │
                         │           │ Conditions satisfied
                         │           │ (state + mode + beats)
                         │           │
                         │           ▼
                         │    ┌─────────────┐
                         │    │  ACTIVATING │
                         │    └──────┬──────┘
                         │           │
                         │           │ Nav2 activation
                         │           │ successful
                         │           │
                         │           ▼
        Any condition    │    ┌─────────────┐      Conditions
        becomes invalid  │    │   ACTIVE    │      still valid
                         │    │             │◄─────────┐
                         │    │ Nav2 ready  │          │
                         │    │ for goals   │          │
                         │    └──────┬──────┘          │
                         │           │                 │
                         │           │ Condition fails │
                         │           │                 │
                         │           ▼                 │
                         │    ┌─────────────┐          │
                         └───►│ DEACTIVATING│          │
                              └──────┬──────┘          │
                                     │                 │
                                     │ Nav2            │
                                     │ deactivated     │
                                     │                 │
                                     └─────────────────┘


State Definitions:
──────────────────

INACTIVE:       Nav2 is not active, robot cannot navigate
ACTIVATING:     Transitioning Nav2 to active state
ACTIVE:         Nav2 is active and ready for navigation goals
DEACTIVATING:   Shutting down Nav2 due to condition failure
```

---

## Topic and Service Interactions

```
┌────────────────────────────────────────────────────────────────────────┐
│                     ROS2 Communication Diagram                         │
└────────────────────────────────────────────────────────────────────────┘

Topics (Publishers → Subscribers)
──────────────────────────────────

RobotStateMachine
    │
    ├─[/robot_state]────────────────────┐
    │   (std_msgs/String)                │
    │                                    ▼
    └─[/autonomous_mode]─────────►  Safety Controller
        (std_msgs/Bool)


Sentor
    │
    ├─[/safety/heartbeat]───────────────┐
    │   (std_msgs/Bool)                  │
    │                                    ▼
    └─[/warning/heartbeat]──────────►  Safety Controller
        (std_msgs/Bool)


Nav2 Controller
    │
    └─[/cmd_vel]────────────────────┐
        (geometry_msgs/Twist)        │
                                     ▼
                                cmd_vel Filter (optional)
                                     │
                                     ▼
                                Robot Base


Services (Client → Server)
──────────────────────────

Safety Controller ──[ChangeState]──► Nav2 Lifecycle Nodes
                                      • /controller_server
                                      • /planner_server
                                      • /bt_navigator

Safety Controller ──[SetOverride]──► Sentor
                                      • /sentor/override_safety
                                      • /sentor/override_warning


Actions (Client → Server)
─────────────────────────

Safety Controller ──[CancelGoal]───► Nav2 Action Servers
                                      • NavigateToPose
                                      • FollowPath

Mission Planner ────[NavigateToPose]─► Nav2
```

---

## Timing Diagram - Emergency Stop

```
┌────────────────────────────────────────────────────────────────────────┐
│                     Emergency Stop Timing Diagram                      │
└────────────────────────────────────────────────────────────────────────┘

Time (ms)   Event                                    Component
─────────   ─────────────────────────────────────    ─────────────────

    0       Emergency button pressed                 Hardware
    │
   10       robot_state → "emergency_stop"           RobotStateMachine
    │       └─ Message published
    │
   50       State change detected                    Safety Controller
    │       └─ SAFE_TO_NAVIGATE → FALSE
    │
   60       Cancel goal request sent                 Safety Controller
    │       └─ CancelGoal action call
    │
  100       Zero cmd_vel published                   Safety Controller
    │       └─ (if velocity filter enabled)
    │
  150       Lifecycle deactivate request sent        Safety Controller
    │       └─ ChangeState service call
    │
  200       Goal cancellation acknowledged           Nav2
    │       └─ Goal status: ABORTED
    │
  250       Nav2 stops publishing cmd_vel            Nav2
    │
  300       Lifecycle transition complete            Nav2
    │       └─ State: INACTIVE
    │
  500       Robot motion stops                       Robot Base
    │       └─ Velocity: 0.0 m/s
    │
    ▼       
          System in safe state

═══════════════════════════════════════════════════════════════════════════

Maximum Acceptable Latencies:
────────────────────────────

Detection:          < 100 ms
Goal Cancellation:  < 200 ms
Total Stop Time:    < 500 ms
```

---

## Configuration Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                     System Configuration Flow                          │
└────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────────┐
                        │  Configuration      │
                        │  Files              │
                        └──┬──────────┬───────┘
                           │          │
              ┌────────────┘          └────────────┐
              │                                    │
              ▼                                    ▼
    ┌─────────────────┐                 ┌─────────────────┐
    │ sentor_config   │                 │ safety_config   │
    │     .yaml       │                 │     .yaml       │
    └────────┬────────┘                 └────────┬────────┘
             │                                    │
             │ Defines:                           │ Defines:
             │ • Topic monitors                   │ • Topic names
             │ • Node monitors                    │ • Thresholds
             │ • Timeouts                         │ • Nav2 nodes
             │ • Critical flags                   │ • Filter enable
             │                                    │
             ▼                                    ▼
    ┌─────────────────┐                 ┌─────────────────┐
    │     Sentor      │                 │  Safety         │
    │     Node        │                 │  Controller     │
    └────────┬────────┘                 └────────┬────────┘
             │                                    │
             │ Publishes:                         │ Subscribes:
             │ • /safety/heartbeat                │ • /robot_state
             │ • /warning/heartbeat               │ • /autonomous_mode
             │                                    │ • /safety/heartbeat
             │                                    │ • /warning/heartbeat
             │                                    │
             └────────────┬───────────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │  Runtime        │
                 │  Parameters     │
                 │  via ROS2       │
                 └─────────────────┘
```

---

*These diagrams are ASCII representations for easy viewing and editing. For presentation purposes, consider creating graphical versions using tools like draw.io, PlantUML, or similar.*
