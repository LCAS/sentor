# Sentor: A ROS messages monitoring node

Continuously monitor topic messages. Send warnings and execute other processes when certain conditions on the messages are satisfied. See the [wiki](https://github.com/LCAS/sentor/wiki/sentor).

# Sentor Monitoring Configuration

This document explains how to structure your YAML config file for **Sentor**’s topic- and node-monitoring, and how the two “heartbeats” (`safety/heartbeat` and `warning/heartbeat`) are driven by your *safety-critical* and *autonomy-critical* flags.

---

## Table of Contents
1. [Overview](#overview)  
2. [Top-Level Structure](#top-level-structure)  
3. [`monitors:` (TopicMonitors)](#monitors-topicmonitors)  
   * [Common fields](#common-fields)  
   * [`signal_when`](#signal_when)  
   * [`signal_lambdas`](#signal_lambdas)  
   * [Example](#example-topic-monitor)  
4. [`node_monitors:` (NodeMonitors)](#node_monitors-nodemonitors)  
   * [Fields](#fields)  
   * [Example](#example-node-monitor)  
5. [Heartbeats](#heartbeats)  
   * [Safety heartbeat (`safety/heartbeat`)](#safety-heartbeat-safetyheartbeat)  
   * [Warning heartbeat (`warning/heartbeat`)](#warning-heartbeat-warningheartbeat)  

---

## Overview<a name="overview"></a>

| Component        | What it watches                                    | Critical flags in YAML                     | Feeds into |
|------------------|----------------------------------------------------|--------------------------------------------|------------|
| **TopicMonitor** | Rate + message content of one topic                | `safety_critical`, `autonomy_critical`     | both beats |
| **NodeMonitor**  | Presence of a node on the ROS graph                | `safety_critical`, `autonomy_critical`     | both beats |
| **SafetyMonitor**| Aggregates monitors and publishes a Boolean topic  | —                                          | one beat   |

If **all** linked monitors are healthy for at least `safe_operation_timeout` seconds, the heartbeat publishes **`true`**; otherwise it immediately publishes **`false`**.

---

## Top-Level Structure<a name="top-level-structure"></a>

~~~yaml
monitors:       # list of topic monitors
  - …           # one map per topic
node_monitors:  # list of node monitors
  - …           # one map per node
~~~

*(Spaces only, no tabs.)*

---

## `monitors:` (TopicMonitors)<a name="monitors-topicmonitors"></a>

### Common fields<a name="common-fields"></a>

| Field | Type | Req | Description |
|-------|------|-----|-------------|
| `name` | string | ✔ | Full topic name (`/camera/image_raw`) |
| `message_type` | string | ✔ | Package/type (`sensor_msgs/msg/Image`) |
| `rate` | number | ✔ | Minimum acceptable publish rate (Hz) |
| `N` | int | • | Window size for rate (default `5`) |
| `qos` | map | • | Override QoS (`reliability`, `durability`, `depth`) |
| `timeout` | sec | • | Default lambda / signal timeout (default `10`) |
| `default_notifications` | bool | • | Log flips automatically? (default `true`) |
| `enable_internal_logs` | bool | • | Extra per-topic debug (default `false`) |

### `signal_when`<a name="signal_when"></a>

~~~yaml
signal_when:
  condition: "published"        # or "not published"
  timeout: 2.0                  # seconds before failure
  safety_critical:   false
  autonomy_critical: true
  tags: ["camera", "liveliness"]  # optional free-text labels
~~~

### `signal_lambdas`<a name="signal_lambdas"></a>

~~~yaml
signal_lambdas:
  - expression: "lambda x: x.height == 480"
    timeout: 2.0
    safety_critical: true      # affects safety beat
    autonomy_critical: false   # doesn’t affect warning beat
    process_indices: [2]       # indexes into `execute` list (optional)
    repeat_exec: false         # run every time satisfied?
    tags: ["resolution"]
~~~

### Example Topic Monitor<a name="example-topic-monitor"></a>

~~~yaml
- name: "/front_camera/camera_info"
  message_type: "sensor_msgs/msg/CameraInfo"
  rate: 8
  N: 5
  qos:
    reliability: "reliable"
    durability: "volatile"
    depth: 5
  signal_when:
    condition: "published"
    timeout: 2
    safety_critical: false
    autonomy_critical: true
  signal_lambdas:
    - expression: "lambda x: x.height < 480"
      timeout: 2
      safety_critical: true
      autonomy_critical: false
  execute: []                  # optional shell / ROS actions
  timeout: 10
  default_notifications: false
~~~

---

## `node_monitors:` (NodeMonitors)<a name="node_monitors-nodemonitors"></a>

### Fields<a name="fields"></a>

| Field | Type | Req | Description |
|-------|------|-----|-------------|
| `name` | string | ✔ | Exact node name (`/camera_driver`) |
| `timeout` | sec | ✔ | Max age since last seen |
| `safety_critical` | bool | • | Flip safety beat when missing |
| `autonomy_critical` | bool | • | Flip warning beat when missing |
| `poll_rate` | Hz | • | Graph query rate (default `1.0`) |
| `tags` | list | • | Labels |

### Example Node Monitor<a name="example-node-monitor"></a>

~~~yaml
node_monitors:
  - name: "/front_camera_camera_controller"
    timeout: 2.0
    safety_critical: true
    autonomy_critical: false

  - name: "/back_camera_camera_controller"
    timeout: 1.0
    safety_critical: false
    autonomy_critical: true
~~~

---

## Heartbeats<a name="heartbeats"></a>

### Safety heartbeat (`safety/heartbeat`)<a name="safety-heartbeat-safetyheartbeat"></a>

* Publishes `std_msgs/Bool`
* **TRUE** when **all** safety-critical monitors are satisfied for `safe_operation_timeout`
* **FALSE** immediately on first safety-critical failure

### Warning heartbeat (`warning/heartbeat`)<a name="warning-heartbeat-warningheartbeat"></a>

* Publishes `std_msgs/Bool`
* **TRUE** when all autonomy-critical monitors are satisfied
* **FALSE** on first autonomy-critical failure  
  (use for degradations that allow limp-home operation)

---

## Quick checklist

* ✔ Every topic lists `message_type` **and** `rate`.  
* ✔ Mark each rule/node as `safety_critical` or `autonomy_critical` (or both).  
* ✔ No critical flag ⇒ the rule is informational only.  
* ✔ Adjust parameters at launch:

```bash
ros2 run sentor test_sentor.py \
  --ros-args \
    -p config_file:=/path/to/monitor.yaml \
    -p safety_pub_rate:=1.0 \
    -p safe_operation_timeout:=5.0
```

 **Note**

- /safety/heartbeat toggles **TRUE** only when all safety-critical items pass.

- /warning/heartbeat toggles **TRUE** when autonomy-critical items pass.

- Killing a safety-critical publisher flips both beats to FALSE immediately.

- Killing only an autonomy-critical node flips warning beat but leaves safety unchanged.

- If desired, run ros2 topic echo /safety/heartbeat and /warning/heartbeat in separate terminals to verify.
