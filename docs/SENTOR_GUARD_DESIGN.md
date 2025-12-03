# Sentor Guard Package Design

## Overview

The `sentor_guard` package provides a comprehensive set of tools and libraries to implement safe autonomous behavior by integrating sentor's state monitoring with robot control systems. It implements three complementary approaches:

1. **Lifecycle Management** - Control ROS2 lifecycle nodes based on safety conditions
2. **Software Context Guards** - Inline code guards for Python and C++ that block execution until safety conditions are met
3. **Topic Guards** - Transparent topic forwarding that only passes messages when safety conditions are satisfied

This design complements the Safety Controller concept described in ARCHITECTURE_INTEGRATION.md by providing reusable libraries and nodes that can be integrated into any ROS2 system.

---

## Table of Contents

1. [Package Structure](#package-structure)
2. [Core Guard Abstraction](#core-guard-abstraction)
3. [Python Guard Library](#python-guard-library)
4. [C++ Guard Library](#c-guard-library)
5. [Topic Guard Node](#topic-guard-node)
6. [Lifecycle Guard Node](#lifecycle-guard-node)
7. [Configuration](#configuration)
8. [Launch Files](#launch-files)
9. [Usage Examples](#usage-examples)
10. [Testing Strategy](#testing-strategy)

---

## Package Structure

```
sentor_guard/
├── CMakeLists.txt
├── package.xml
├── README.md
│
├── include/
│   └── sentor_guard/
│       ├── guard.hpp              # C++ guard library
│       ├── guard_exception.hpp    # Exception definitions
│       └── lifecycle_guard.hpp    # Lifecycle management
│
├── src/
│   ├── guard.cpp                  # C++ guard implementation
│   ├── topic_guard_node.cpp       # Topic forwarding node
│   └── lifecycle_guard_node.cpp   # Lifecycle management node
│
├── sentor_guard/
│   ├── __init__.py
│   ├── guard.py                   # Python guard library
│   └── topic_guard_node.py        # Python topic guard (optional)
│
├── launch/
│   ├── guard_example.launch.py   # Example launch file
│   └── topic_guards.launch.py    # Topic guard configuration
│
├── config/
│   ├── guard_params.yaml          # Example guard parameters
│   └── topic_guards.yaml          # Topic guard configuration
│
├── test/
│   ├── test_python_guard.py
│   ├── test_cpp_guard.cpp
│   └── test_topic_guard.cpp
│
└── examples/
    ├── python_guard_example.py
    └── cpp_guard_example.cpp
```

---

## Core Guard Abstraction

The guard abstraction monitors sentor's state and heartbeat topics to determine if autonomous operations are permitted. All implementations share common behavior:

### State Conditions

A guard is satisfied when **all** of the following are true:

1. **State Match**: Current state equals the required state (default: "active")
2. **Heartbeat Fresh**: Last heartbeat timestamp is within timeout period (default: 1.0s)
3. **Heartbeat Value**: Heartbeat indicates healthy operation (typically `true`)

### Monitoring Topics

| Topic | Type | Purpose |
|-------|------|---------|
| `/robot_state` | std_msgs/String | Current robot operational state |
| `/autonomous_mode` | std_msgs/Bool | Whether autonomous mode is enabled |
| `/safety/heartbeat` | std_msgs/Bool | Safety-critical system health |
| `/warning/heartbeat` | std_msgs/Bool | Autonomy-critical system health |

### Operating Modes

Guards support three operating modes:

1. **Blocking Wait** - Wait indefinitely until conditions are met
2. **Timed Wait** - Wait with timeout, raise exception on failure
3. **Non-blocking Check** - Immediate check without waiting

---

## Python Guard Library

### Class: `SentorGuard`

The Python guard can be used as a context manager or called directly.

```python
# sentor_guard/guard.py
import rclpy
from rclpy.node import Node
from rclpy.time import Time, Duration
from std_msgs.msg import String, Bool
from threading import Event, Lock
import time

class AutonomyGuardException(Exception):
    """Raised when autonomy guard conditions are not met within timeout"""
    pass

class SentorGuard:
    """
    Guard that checks sentor state and heartbeat before allowing execution.
    
    Can be used as a context manager or called directly.
    """
    
    def __init__(self, node: Node, 
                 state_topic: str = '/robot_state',
                 mode_topic: str = '/autonomous_mode',
                 safety_heartbeat_topic: str = '/safety/heartbeat',
                 warning_heartbeat_topic: str = '/warning/heartbeat',
                 heartbeat_timeout: float = 1.0,
                 required_state: str = 'active',
                 require_autonomous_mode: bool = True,
                 require_safety_heartbeat: bool = True,
                 require_warning_heartbeat: bool = True):
        """
        Args:
            node: ROS2 node to use for subscriptions
            state_topic: Topic publishing robot state
            mode_topic: Topic publishing autonomous mode flag
            safety_heartbeat_topic: Topic for safety heartbeat
            warning_heartbeat_topic: Topic for warning heartbeat
            heartbeat_timeout: Maximum age of heartbeat in seconds
            required_state: State required for autonomy (e.g., 'active')
            require_autonomous_mode: Whether autonomous mode must be true
            require_safety_heartbeat: Whether safety heartbeat must be true
            require_warning_heartbeat: Whether warning heartbeat must be true
        """
        self.node = node
        self.heartbeat_timeout = Duration(seconds=heartbeat_timeout)
        self.required_state = required_state
        self.require_autonomous_mode = require_autonomous_mode
        self.require_safety_heartbeat = require_safety_heartbeat
        self.require_warning_heartbeat = require_warning_heartbeat
        
        self._lock = Lock()
        self._current_state = None
        self._autonomous_mode = None
        self._safety_heartbeat = None
        self._warning_heartbeat = None
        self._last_safety_heartbeat_time = None
        self._last_warning_heartbeat_time = None
        self._condition_met = Event()
        
        # Subscribe to state and mode topics
        self._state_sub = node.create_subscription(
            String,
            state_topic,
            self._state_callback,
            10
        )
        
        self._mode_sub = node.create_subscription(
            Bool,
            mode_topic,
            self._mode_callback,
            10
        )
        
        # Subscribe to heartbeat topics
        self._safety_heartbeat_sub = node.create_subscription(
            Bool,
            safety_heartbeat_topic,
            self._safety_heartbeat_callback,
            10
        )
        
        self._warning_heartbeat_sub = node.create_subscription(
            Bool,
            warning_heartbeat_topic,
            self._warning_heartbeat_callback,
            10
        )
        
        self.node.get_logger().info(
            f"SentorGuard initialized: required_state='{required_state}', "
            f"heartbeat_timeout={heartbeat_timeout}s"
        )
    
    def _state_callback(self, msg):
        with self._lock:
            self._current_state = msg.data
            self._check_conditions()
    
    def _mode_callback(self, msg):
        with self._lock:
            self._autonomous_mode = msg.data
            self._check_conditions()
    
    def _safety_heartbeat_callback(self, msg):
        with self._lock:
            self._safety_heartbeat = msg.data
            self._last_safety_heartbeat_time = self.node.get_clock().now()
            self._check_conditions()
    
    def _warning_heartbeat_callback(self, msg):
        with self._lock:
            self._warning_heartbeat = msg.data
            self._last_warning_heartbeat_time = self.node.get_clock().now()
            self._check_conditions()
    
    def _check_conditions(self):
        """Check if all conditions are met"""
        now = self.node.get_clock().now()
        
        # Check state
        if self._current_state != self.required_state:
            self._condition_met.clear()
            return
        
        # Check autonomous mode
        if self.require_autonomous_mode and not self._autonomous_mode:
            self._condition_met.clear()
            return
        
        # Check safety heartbeat
        if self.require_safety_heartbeat:
            if self._safety_heartbeat is None or not self._safety_heartbeat:
                self._condition_met.clear()
                return
            
            if self._last_safety_heartbeat_time is None:
                self._condition_met.clear()
                return
            
            age = now - self._last_safety_heartbeat_time
            if age > self.heartbeat_timeout:
                self._condition_met.clear()
                return
        
        # Check warning heartbeat
        if self.require_warning_heartbeat:
            if self._warning_heartbeat is None or not self._warning_heartbeat:
                self._condition_met.clear()
                return
            
            if self._last_warning_heartbeat_time is None:
                self._condition_met.clear()
                return
            
            age = now - self._last_warning_heartbeat_time
            if age > self.heartbeat_timeout:
                self._condition_met.clear()
                return
        
        # All conditions met
        self._condition_met.set()
    
    def is_autonomy_allowed(self) -> bool:
        """Check if autonomy is currently allowed (non-blocking)"""
        with self._lock:
            self._check_conditions()  # Recheck heartbeat age
            return self._condition_met.is_set()
    
    def get_blocking_reason(self) -> str:
        """Get human-readable reason why autonomy is blocked"""
        with self._lock:
            now = self.node.get_clock().now()
            
            if self._current_state != self.required_state:
                return f"State is '{self._current_state}', required '{self.required_state}'"
            
            if self.require_autonomous_mode and not self._autonomous_mode:
                return "Autonomous mode is disabled"
            
            if self.require_safety_heartbeat:
                if self._safety_heartbeat is None or not self._safety_heartbeat:
                    return "Safety heartbeat is unhealthy or not received"
                
                if self._last_safety_heartbeat_time:
                    age = now - self._last_safety_heartbeat_time
                    if age > self.heartbeat_timeout:
                        return f"Safety heartbeat stale ({age.nanoseconds / 1e9:.2f}s old)"
            
            if self.require_warning_heartbeat:
                if self._warning_heartbeat is None or not self._warning_heartbeat:
                    return "Warning heartbeat is unhealthy or not received"
                
                if self._last_warning_heartbeat_time:
                    age = now - self._last_warning_heartbeat_time
                    if age > self.heartbeat_timeout:
                        return f"Warning heartbeat stale ({age.nanoseconds / 1e9:.2f}s old)"
            
            return "Unknown reason"
    
    def wait_for_autonomy(self, timeout: float = None) -> bool:
        """
        Wait until autonomy is allowed.
        
        Args:
            timeout: Maximum time to wait in seconds. None for indefinite.
            
        Returns:
            True if autonomy is allowed, False if timeout occurred
        """
        start_time = time.time()
        rate = self.node.create_rate(10)  # 10 Hz check rate
        
        while rclpy.ok():
            if self.is_autonomy_allowed():
                return True
            
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    reason = self.get_blocking_reason()
                    self.node.get_logger().warn(
                        f"Autonomy not granted within {timeout}s: {reason}"
                    )
                    return False
            
            rclpy.spin_once(self.node, timeout_sec=0.1)
            
        return False
    
    def __enter__(self):
        """Context manager entry - waits indefinitely by default"""
        if not self.wait_for_autonomy():
            raise AutonomyGuardException("Autonomy not allowed and node is shutting down")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        return False
    
    def guarded_wait(self, timeout: float = None):
        """
        Wait for autonomy with timeout, raising exception on failure.
        
        Args:
            timeout: Maximum time to wait. None for indefinite.
            
        Raises:
            AutonomyGuardException: If timeout occurs
        """
        if not self.wait_for_autonomy(timeout):
            reason = self.get_blocking_reason()
            if timeout:
                raise AutonomyGuardException(
                    f"Autonomy not granted within {timeout}s timeout: {reason}"
                )
            else:
                raise AutonomyGuardException(
                    f"Autonomy not allowed: {reason}"
                )
```

### Usage Examples

```python
# Example 1: Context manager (indefinite wait)
class MyRobotNode(Node):
    def __init__(self):
        super().__init__('my_robot')
        self.guard = SentorGuard(self, heartbeat_timeout=1.0)
        
    def do_autonomous_action(self):
        """Execute action only when safe"""
        with self.guard:
            self.get_logger().info("Executing autonomous action")
            # Your autonomous code here
            self.publish_command()

# Example 2: Explicit timeout with exception
class TimedActionNode(Node):
    def __init__(self):
        super().__init__('timed_action')
        self.guard = SentorGuard(self)
        
    def do_timed_action(self):
        try:
            self.guard.guarded_wait(timeout=5.0)
            self.get_logger().info("Autonomy granted, proceeding")
            # Your autonomous code here
        except AutonomyGuardException as e:
            self.get_logger().error(f"Cannot proceed: {e}")

# Example 3: Non-blocking check
class NonBlockingNode(Node):
    def __init__(self):
        super().__init__('non_blocking')
        self.guard = SentorGuard(self)
        
    def timer_callback(self):
        if self.guard.is_autonomy_allowed():
            # Proceed with autonomous action
            self.execute_navigation()
        else:
            # Skip or handle not allowed
            reason = self.guard.get_blocking_reason()
            self.get_logger().debug(f"Skipping action: {reason}")
```

---

## C++ Guard Library

### Class: `SentorGuard`

```cpp
// sentor_guard/include/sentor_guard/guard.hpp
#pragma once

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>
#include <std_msgs/msg/bool.hpp>
#include <mutex>
#include <condition_variable>
#include <memory>
#include <string>
#include <chrono>

namespace sentor_guard {

class AutonomyGuardException : public std::runtime_error {
public:
    explicit AutonomyGuardException(const std::string& message)
        : std::runtime_error(message) {}
};

class SentorGuard {
public:
    struct Options {
        std::string state_topic = "/robot_state";
        std::string mode_topic = "/autonomous_mode";
        std::string safety_heartbeat_topic = "/safety/heartbeat";
        std::string warning_heartbeat_topic = "/warning/heartbeat";
        std::chrono::milliseconds heartbeat_timeout{1000};
        std::string required_state = "active";
        bool require_autonomous_mode = true;
        bool require_safety_heartbeat = true;
        bool require_warning_heartbeat = true;
    };

    explicit SentorGuard(rclcpp::Node::SharedPtr node, const Options& options = Options());
    
    ~SentorGuard() = default;

    // Non-blocking check
    bool isAutonomyAllowed();
    
    // Get reason why autonomy is blocked
    std::string getBlockingReason();
    
    // Blocking wait with optional timeout
    bool waitForAutonomy(std::chrono::milliseconds timeout = std::chrono::milliseconds::zero());
    
    // Wait with exception on timeout
    void guardedWait(std::chrono::milliseconds timeout = std::chrono::milliseconds::zero());
    
    // RAII guard class
    class Guard {
    public:
        explicit Guard(SentorGuard& guard, std::chrono::milliseconds timeout = std::chrono::milliseconds::zero())
            : guard_(guard) {
            guard_.guardedWait(timeout);
        }
        ~Guard() = default;
        
        Guard(const Guard&) = delete;
        Guard& operator=(const Guard&) = delete;
        
    private:
        SentorGuard& guard_;
    };

private:
    void stateCallback(const std_msgs::msg::String::SharedPtr msg);
    void modeCallback(const std_msgs::msg::Bool::SharedPtr msg);
    void safetyHeartbeatCallback(const std_msgs::msg::Bool::SharedPtr msg);
    void warningHeartbeatCallback(const std_msgs::msg::Bool::SharedPtr msg);
    
    void checkConditions();
    
    rclcpp::Node::SharedPtr node_;
    Options options_;
    
    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr state_sub_;
    rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr mode_sub_;
    rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr safety_heartbeat_sub_;
    rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr warning_heartbeat_sub_;
    
    std::mutex mutex_;
    std::condition_variable cv_;
    
    std::string current_state_;
    bool autonomous_mode_{false};
    bool safety_heartbeat_{false};
    bool warning_heartbeat_{false};
    rclcpp::Time last_safety_heartbeat_time_;
    rclcpp::Time last_warning_heartbeat_time_;
    bool condition_met_{false};
};

} // namespace sentor_guard
```

### Implementation

```cpp
// sentor_guard/src/guard.cpp
#include "sentor_guard/guard.hpp"

namespace sentor_guard {

SentorGuard::SentorGuard(rclcpp::Node::SharedPtr node, const Options& options)
    : node_(node), options_(options) {
    
    // Create subscriptions
    state_sub_ = node_->create_subscription<std_msgs::msg::String>(
        options_.state_topic, 10,
        std::bind(&SentorGuard::stateCallback, this, std::placeholders::_1));
    
    mode_sub_ = node_->create_subscription<std_msgs::msg::Bool>(
        options_.mode_topic, 10,
        std::bind(&SentorGuard::modeCallback, this, std::placeholders::_1));
    
    safety_heartbeat_sub_ = node_->create_subscription<std_msgs::msg::Bool>(
        options_.safety_heartbeat_topic, 10,
        std::bind(&SentorGuard::safetyHeartbeatCallback, this, std::placeholders::_1));
    
    warning_heartbeat_sub_ = node_->create_subscription<std_msgs::msg::Bool>(
        options_.warning_heartbeat_topic, 10,
        std::bind(&SentorGuard::warningHeartbeatCallback, this, std::placeholders::_1));
    
    RCLCPP_INFO(node_->get_logger(),
        "SentorGuard initialized: required_state='%s', heartbeat_timeout=%ldms",
        options_.required_state.c_str(), options_.heartbeat_timeout.count());
}

void SentorGuard::stateCallback(const std_msgs::msg::String::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(mutex_);
    current_state_ = msg->data;
    checkConditions();
}

void SentorGuard::modeCallback(const std_msgs::msg::Bool::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(mutex_);
    autonomous_mode_ = msg->data;
    checkConditions();
}

void SentorGuard::safetyHeartbeatCallback(const std_msgs::msg::Bool::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(mutex_);
    safety_heartbeat_ = msg->data;
    last_safety_heartbeat_time_ = node_->get_clock()->now();
    checkConditions();
}

void SentorGuard::warningHeartbeatCallback(const std_msgs::msg::Bool::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(mutex_);
    warning_heartbeat_ = msg->data;
    last_warning_heartbeat_time_ = node_->get_clock()->now();
    checkConditions();
}

void SentorGuard::checkConditions() {
    auto now = node_->get_clock()->now();
    
    // Check state
    if (current_state_ != options_.required_state) {
        condition_met_ = false;
        return;
    }
    
    // Check autonomous mode
    if (options_.require_autonomous_mode && !autonomous_mode_) {
        condition_met_ = false;
        return;
    }
    
    // Check safety heartbeat
    if (options_.require_safety_heartbeat) {
        if (!safety_heartbeat_) {
            condition_met_ = false;
            return;
        }
        
        auto age = now - last_safety_heartbeat_time_;
        if (age > rclcpp::Duration(options_.heartbeat_timeout)) {
            condition_met_ = false;
            return;
        }
    }
    
    // Check warning heartbeat
    if (options_.require_warning_heartbeat) {
        if (!warning_heartbeat_) {
            condition_met_ = false;
            return;
        }
        
        auto age = now - last_warning_heartbeat_time_;
        if (age > rclcpp::Duration(options_.heartbeat_timeout)) {
            condition_met_ = false;
            return;
        }
    }
    
    // All conditions met
    bool was_met = condition_met_;
    condition_met_ = true;
    
    if (!was_met && condition_met_) {
        cv_.notify_all();
    }
}

bool SentorGuard::isAutonomyAllowed() {
    std::lock_guard<std::mutex> lock(mutex_);
    checkConditions();  // Recheck heartbeat age
    return condition_met_;
}

std::string SentorGuard::getBlockingReason() {
    std::lock_guard<std::mutex> lock(mutex_);
    auto now = node_->get_clock()->now();
    
    if (current_state_ != options_.required_state) {
        return "State is '" + current_state_ + "', required '" + options_.required_state + "'";
    }
    
    if (options_.require_autonomous_mode && !autonomous_mode_) {
        return "Autonomous mode is disabled";
    }
    
    if (options_.require_safety_heartbeat) {
        if (!safety_heartbeat_) {
            return "Safety heartbeat is unhealthy or not received";
        }
        
        auto age = now - last_safety_heartbeat_time_;
        if (age > rclcpp::Duration(options_.heartbeat_timeout)) {
            return "Safety heartbeat stale (" + std::to_string(age.seconds()) + "s old)";
        }
    }
    
    if (options_.require_warning_heartbeat) {
        if (!warning_heartbeat_) {
            return "Warning heartbeat is unhealthy or not received";
        }
        
        auto age = now - last_warning_heartbeat_time_;
        if (age > rclcpp::Duration(options_.heartbeat_timeout)) {
            return "Warning heartbeat stale (" + std::to_string(age.seconds()) + "s old)";
        }
    }
    
    return "Unknown reason";
}

bool SentorGuard::waitForAutonomy(std::chrono::milliseconds timeout) {
    auto start = std::chrono::steady_clock::now();
    
    while (rclcpp::ok()) {
        {
            std::unique_lock<std::mutex> lock(mutex_);
            checkConditions();
            
            if (condition_met_) {
                return true;
            }
            
            if (timeout.count() > 0) {
                auto elapsed = std::chrono::steady_clock::now() - start;
                auto remaining = timeout - std::chrono::duration_cast<std::chrono::milliseconds>(elapsed);
                
                if (remaining.count() <= 0) {
                    auto reason = getBlockingReason();
                    RCLCPP_WARN(node_->get_logger(),
                        "Autonomy not granted within %ldms: %s",
                        timeout.count(), reason.c_str());
                    return false;
                }
                
                cv_.wait_for(lock, std::chrono::milliseconds(100));
            } else {
                cv_.wait_for(lock, std::chrono::milliseconds(100));
            }
        }
        
        // Spin once to process callbacks
        rclcpp::spin_some(node_);
    }
    
    return false;
}

void SentorGuard::guardedWait(std::chrono::milliseconds timeout) {
    if (!waitForAutonomy(timeout)) {
        auto reason = getBlockingReason();
        if (timeout.count() > 0) {
            throw AutonomyGuardException(
                "Autonomy not granted within " + std::to_string(timeout.count()) + 
                "ms timeout: " + reason);
        } else {
            throw AutonomyGuardException("Autonomy not allowed: " + reason);
        }
    }
}

} // namespace sentor_guard
```

### C++ Usage Examples

```cpp
// Example 1: RAII guard (recommended)
class MyRobotNode : public rclcpp::Node {
public:
    MyRobotNode() : Node("my_robot"), guard_(shared_from_this()) {}
    
    void doAutonomousAction() {
        // Automatically waits and throws on failure
        sentor_guard::SentorGuard::Guard guard(guard_);
        
        RCLCPP_INFO(get_logger(), "Executing autonomous action");
        // Your autonomous code here
        publishCommand();
    }
    
private:
    sentor_guard::SentorGuard guard_;
};

// Example 2: Explicit timeout
class TimedActionNode : public rclcpp::Node {
public:
    TimedActionNode() : Node("timed_action"), guard_(shared_from_this()) {}
    
    void doTimedAction() {
        try {
            guard_.guardedWait(std::chrono::seconds(5));
            RCLCPP_INFO(get_logger(), "Autonomy granted, proceeding");
            // Your autonomous code here
        } catch (const sentor_guard::AutonomyGuardException& e) {
            RCLCPP_ERROR(get_logger(), "Cannot proceed: %s", e.what());
        }
    }
    
private:
    sentor_guard::SentorGuard guard_;
};

// Example 3: Non-blocking check
class NonBlockingNode : public rclcpp::Node {
public:
    NonBlockingNode() : Node("non_blocking"), guard_(shared_from_this()) {
        timer_ = create_wall_timer(
            std::chrono::seconds(1),
            std::bind(&NonBlockingNode::timerCallback, this));
    }
    
    void timerCallback() {
        if (guard_.isAutonomyAllowed()) {
            // Proceed with autonomous action
            executeNavigation();
        } else {
            // Skip or handle not allowed
            auto reason = guard_.getBlockingReason();
            RCLCPP_DEBUG(get_logger(), "Skipping action: %s", reason.c_str());
        }
    }
    
private:
    sentor_guard::SentorGuard guard_;
    rclcpp::TimerBase::SharedPtr timer_;
};
```

---

## Topic Guard Node

The Topic Guard Node provides transparent topic forwarding that only passes messages when safety conditions are met. This is useful for adding safety to existing systems without modifying their code.

### Concept

```
Input Topic ──> Topic Guard Node ──> Output Topic
                      │
                      └─> Only forwards when guard conditions met
                      └─> Otherwise drops messages
```

### Node Implementation

```cpp
// sentor_guard/src/topic_guard_node.cpp
#include <rclcpp/rclcpp.hpp>
#include "sentor_guard/guard.hpp"
#include <topic_tools/shape_shifter.h>

class TopicGuardNode : public rclcpp::Node {
public:
    TopicGuardNode() : Node("topic_guard_node") {
        // Declare parameters
        declare_parameter("input_topic", "");
        declare_parameter("output_topic", "");
        declare_parameter("message_type", "");
        declare_parameter("required_state", "active");
        declare_parameter("heartbeat_timeout", 1.0);
        
        // Get parameters
        std::string input_topic = get_parameter("input_topic").as_string();
        std::string output_topic = get_parameter("output_topic").as_string();
        std::string message_type = get_parameter("message_type").as_string();
        
        // Initialize guard
        sentor_guard::SentorGuard::Options guard_options;
        guard_options.required_state = get_parameter("required_state").as_string();
        guard_options.heartbeat_timeout = std::chrono::milliseconds(
            static_cast<int>(get_parameter("heartbeat_timeout").as_double() * 1000));
        
        guard_ = std::make_unique<sentor_guard::SentorGuard>(shared_from_this(), guard_options);
        
        // Create generic publisher and subscriber
        // Implementation depends on topic_tools or similar for type-agnostic forwarding
        
        RCLCPP_INFO(get_logger(),
            "Topic guard initialized: %s -> %s (type: %s)",
            input_topic.c_str(), output_topic.c_str(), message_type.c_str());
    }
    
private:
    void messageCallback(const std::shared_ptr<rclcpp::SerializedMessage>& msg) {
        if (guard_->isAutonomyAllowed()) {
            // Forward message
            publisher_->publish(*msg);
            messages_forwarded_++;
        } else {
            // Drop message
            messages_dropped_++;
            
            if (messages_dropped_ % 100 == 0) {
                RCLCPP_WARN(get_logger(),
                    "Dropped %ld messages: %s",
                    messages_dropped_, guard_->getBlockingReason().c_str());
            }
        }
    }
    
    std::unique_ptr<sentor_guard::SentorGuard> guard_;
    rclcpp::GenericPublisher::SharedPtr publisher_;
    rclcpp::GenericSubscription::SharedPtr subscriber_;
    size_t messages_forwarded_{0};
    size_t messages_dropped_{0};
};
```

---

## Lifecycle Guard Node

Manages lifecycle state of other nodes based on guard conditions.

```cpp
// sentor_guard/src/lifecycle_guard_node.cpp
#include <rclcpp/rclcpp.hpp>
#include <lifecycle_msgs/srv/change_state.hpp>
#include <lifecycle_msgs/msg/transition.hpp>
#include "sentor_guard/guard.hpp"

class LifecycleGuardNode : public rclcpp::Node {
public:
    LifecycleGuardNode() : Node("lifecycle_guard_node") {
        // Declare parameters
        declare_parameter("managed_nodes", std::vector<std::string>{});
        declare_parameter("check_rate", 10.0);
        
        auto managed_nodes = get_parameter("managed_nodes").as_string_array();
        
        // Initialize guard
        guard_ = std::make_unique<sentor_guard::SentorGuard>(shared_from_this());
        
        // Create service clients for each managed node
        for (const auto& node_name : managed_nodes) {
            auto client = create_client<lifecycle_msgs::srv::ChangeState>(
                node_name + "/change_state");
            lifecycle_clients_[node_name] = client;
        }
        
        // Create timer to check conditions periodically
        double rate = get_parameter("check_rate").as_double();
        timer_ = create_wall_timer(
            std::chrono::milliseconds(static_cast<int>(1000.0 / rate)),
            std::bind(&LifecycleGuardNode::checkCallback, this));
        
        RCLCPP_INFO(get_logger(), "Lifecycle guard managing %zu nodes", managed_nodes.size());
    }
    
private:
    void checkCallback() {
        bool allowed = guard_->isAutonomyAllowed();
        
        if (allowed && !currently_active_) {
            activateNodes();
        } else if (!allowed && currently_active_) {
            deactivateNodes();
        }
    }
    
    void activateNodes() {
        RCLCPP_INFO(get_logger(), "Activating managed nodes");
        
        for (auto& [node_name, client] : lifecycle_clients_) {
            auto request = std::make_shared<lifecycle_msgs::srv::ChangeState::Request>();
            request->transition.id = lifecycle_msgs::msg::Transition::TRANSITION_ACTIVATE;
            
            if (client->wait_for_service(std::chrono::seconds(1))) {
                client->async_send_request(request);
            } else {
                RCLCPP_WARN(get_logger(), "Service not available for %s", node_name.c_str());
            }
        }
        
        currently_active_ = true;
    }
    
    void deactivateNodes() {
        RCLCPP_INFO(get_logger(), "Deactivating managed nodes: %s",
            guard_->getBlockingReason().c_str());
        
        for (auto& [node_name, client] : lifecycle_clients_) {
            auto request = std::make_shared<lifecycle_msgs::srv::ChangeState::Request>();
            request->transition.id = lifecycle_msgs::msg::Transition::TRANSITION_DEACTIVATE;
            
            if (client->wait_for_service(std::chrono::seconds(1))) {
                client->async_send_request(request);
            }
        }
        
        currently_active_ = false;
    }
    
    std::unique_ptr<sentor_guard::SentorGuard> guard_;
    std::map<std::string, rclcpp::Client<lifecycle_msgs::srv::ChangeState>::SharedPtr> lifecycle_clients_;
    rclcpp::TimerBase::SharedPtr timer_;
    bool currently_active_{false};
};
```

---

## Configuration

### Guard Parameters YAML

```yaml
# config/guard_params.yaml

/**:
  ros__parameters:
    # Topics to monitor
    state_topic: "/robot_state"
    mode_topic: "/autonomous_mode"
    safety_heartbeat_topic: "/safety/heartbeat"
    warning_heartbeat_topic: "/warning/heartbeat"
    
    # Guard conditions
    required_state: "active"
    heartbeat_timeout: 1.0  # seconds
    
    # Which conditions to enforce
    require_autonomous_mode: true
    require_safety_heartbeat: true
    require_warning_heartbeat: true
```

### Topic Guards Configuration

```yaml
# config/topic_guards.yaml

topic_guards:
  - name: "cmd_vel_guard"
    input_topic: "/nav2/cmd_vel"
    output_topic: "/cmd_vel"
    message_type: "geometry_msgs/msg/Twist"
    required_state: "active"
    heartbeat_timeout: 1.0
  
  - name: "goal_guard"
    input_topic: "/goal_pose_unguarded"
    output_topic: "/goal_pose"
    message_type: "geometry_msgs/msg/PoseStamped"
    required_state: "active"
    heartbeat_timeout: 1.0
```

### Lifecycle Management Configuration

```yaml
# config/lifecycle_guards.yaml

lifecycle_guard:
  ros__parameters:
    managed_nodes:
      - "/controller_server"
      - "/planner_server"
      - "/bt_navigator"
    
    check_rate: 10.0  # Hz
    required_state: "active"
    heartbeat_timeout: 1.0
```

---

## Launch Files

### Example Launch File

```python
# launch/guard_example.launch.py
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    pkg_share = get_package_share_directory('sentor_guard')
    
    guard_params_file = os.path.join(pkg_share, 'config', 'guard_params.yaml')
    
    return LaunchDescription([
        DeclareLaunchArgument(
            'guard_params',
            default_value=guard_params_file,
            description='Path to guard parameters file'
        ),
        
        # Launch lifecycle guard node
        Node(
            package='sentor_guard',
            executable='lifecycle_guard_node',
            name='lifecycle_guard',
            output='screen',
            parameters=[LaunchConfiguration('guard_params')],
        ),
        
        # Example user node with guard
        Node(
            package='sentor_guard',
            executable='example_guarded_node',
            name='example_node',
            output='screen',
            parameters=[LaunchConfiguration('guard_params')],
        ),
    ])
```

### Topic Guards Launch File

```python
# launch/topic_guards.launch.py
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
import yaml
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    pkg_share = get_package_share_directory('sentor_guard')
    topic_guards_file = os.path.join(pkg_share, 'config', 'topic_guards.yaml')
    
    # Load topic guards configuration
    with open(topic_guards_file, 'r') as f:
        config = yaml.safe_load(f)
    
    nodes = []
    
    # Create a topic guard node for each configured guard
    for guard_config in config['topic_guards']:
        node = Node(
            package='sentor_guard',
            executable='topic_guard_node',
            name=guard_config['name'],
            output='screen',
            parameters=[{
                'input_topic': guard_config['input_topic'],
                'output_topic': guard_config['output_topic'],
                'message_type': guard_config['message_type'],
                'required_state': guard_config.get('required_state', 'active'),
                'heartbeat_timeout': guard_config.get('heartbeat_timeout', 1.0),
            }]
        )
        nodes.append(node)
    
    return LaunchDescription(nodes)
```

---

## Usage Examples

### Python Application Example

```python
# examples/python_guard_example.py
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sentor_guard.guard import SentorGuard, AutonomyGuardException

class GuardedNavigationNode(Node):
    def __init__(self):
        super().__init__('guarded_navigation')
        
        # Initialize guard
        self.guard = SentorGuard(
            self,
            required_state='active',
            heartbeat_timeout=1.0,
            require_autonomous_mode=True,
            require_safety_heartbeat=True,
            require_warning_heartbeat=True
        )
        
        # Create publisher
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Create timer for periodic action
        self.timer = self.create_timer(0.1, self.timer_callback)
        
        self.get_logger().info("Guarded navigation node started")
    
    def timer_callback(self):
        """Periodic callback - only publishes if guard allows"""
        if self.guard.is_autonomy_allowed():
            # Autonomy allowed, publish command
            msg = Twist()
            msg.linear.x = 0.5
            self.cmd_vel_pub.publish(msg)
        else:
            # Not allowed, log reason
            reason = self.guard.get_blocking_reason()
            self.get_logger().debug(f"Navigation blocked: {reason}")
    
    def execute_mission(self):
        """Execute a mission with timeout"""
        try:
            # Wait up to 10 seconds for autonomy
            self.guard.guarded_wait(timeout=10.0)
            
            # Proceed with mission
            self.get_logger().info("Starting mission")
            self.run_mission_steps()
            
        except AutonomyGuardException as e:
            self.get_logger().error(f"Mission aborted: {e}")
    
    def critical_action(self):
        """Critical action that must wait indefinitely"""
        with self.guard:
            self.get_logger().info("Executing critical action")
            # This code only runs when guard conditions are met
            self.perform_action()

def main():
    rclpy.init()
    node = GuardedNavigationNode()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
```

### C++ Application Example

```cpp
// examples/cpp_guard_example.cpp
#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include "sentor_guard/guard.hpp"

class GuardedNavigationNode : public rclcpp::Node {
public:
    GuardedNavigationNode() : Node("guarded_navigation") {
        // Initialize guard
        sentor_guard::SentorGuard::Options options;
        options.required_state = "active";
        options.heartbeat_timeout = std::chrono::seconds(1);
        options.require_autonomous_mode = true;
        options.require_safety_heartbeat = true;
        options.require_warning_heartbeat = true;
        
        guard_ = std::make_unique<sentor_guard::SentorGuard>(shared_from_this(), options);
        
        // Create publisher
        cmd_vel_pub_ = create_publisher<geometry_msgs::msg::Twist>("/cmd_vel", 10);
        
        // Create timer for periodic action
        timer_ = create_wall_timer(
            std::chrono::milliseconds(100),
            std::bind(&GuardedNavigationNode::timerCallback, this));
        
        RCLCPP_INFO(get_logger(), "Guarded navigation node started");
    }
    
    void timerCallback() {
        if (guard_->isAutonomyAllowed()) {
            // Autonomy allowed, publish command
            auto msg = geometry_msgs::msg::Twist();
            msg.linear.x = 0.5;
            cmd_vel_pub_->publish(msg);
        } else {
            // Not allowed, log reason
            auto reason = guard_->getBlockingReason();
            RCLCPP_DEBUG(get_logger(), "Navigation blocked: %s", reason.c_str());
        }
    }
    
    void executeMission() {
        try {
            // Wait up to 10 seconds for autonomy
            guard_->guardedWait(std::chrono::seconds(10));
            
            // Proceed with mission
            RCLCPP_INFO(get_logger(), "Starting mission");
            runMissionSteps();
            
        } catch (const sentor_guard::AutonomyGuardException& e) {
            RCLCPP_ERROR(get_logger(), "Mission aborted: %s", e.what());
        }
    }
    
    void criticalAction() {
        // RAII guard - automatically waits
        sentor_guard::SentorGuard::Guard guard(*guard_);
        
        RCLCPP_INFO(get_logger(), "Executing critical action");
        // This code only runs when guard conditions are met
        performAction();
    }
    
private:
    std::unique_ptr<sentor_guard::SentorGuard> guard_;
    rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr cmd_vel_pub_;
    rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char** argv) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<GuardedNavigationNode>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
```

---

## Testing Strategy

### Unit Tests

```python
# test/test_python_guard.py
import unittest
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
from sentor_guard.guard import SentorGuard, AutonomyGuardException
import time

class TestSentorGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()
    
    @classmethod
    def tearDownClass(cls):
        rclcpp.shutdown()
    
    def setUp(self):
        self.node = Node('test_guard_node')
        self.guard = SentorGuard(self.node, heartbeat_timeout=0.5)
        
        # Create test publishers
        self.state_pub = self.node.create_publisher(String, '/robot_state', 10)
        self.mode_pub = self.node.create_publisher(Bool, '/autonomous_mode', 10)
        self.safety_pub = self.node.create_publisher(Bool, '/safety/heartbeat', 10)
        self.warning_pub = self.node.create_publisher(Bool, '/warning/heartbeat', 10)
        
        time.sleep(0.1)  # Allow subscriptions to connect
    
    def test_all_conditions_met(self):
        """Test that guard allows when all conditions are met"""
        # Publish required state
        msg = String()
        msg.data = 'active'
        self.state_pub.publish(msg)
        
        # Publish autonomous mode
        mode_msg = Bool()
        mode_msg.data = True
        self.mode_pub.publish(mode_msg)
        
        # Publish heartbeats
        hb_msg = Bool()
        hb_msg.data = True
        self.safety_pub.publish(hb_msg)
        self.warning_pub.publish(hb_msg)
        
        # Spin to process messages
        rclpy.spin_once(self.node, timeout_sec=0.1)
        
        # Check that autonomy is allowed
        self.assertTrue(self.guard.is_autonomy_allowed())
    
    def test_wrong_state_blocks(self):
        """Test that wrong state blocks autonomy"""
        msg = String()
        msg.data = 'paused'
        self.state_pub.publish(msg)
        
        rclpy.spin_once(self.node, timeout_sec=0.1)
        
        self.assertFalse(self.guard.is_autonomy_allowed())
        self.assertIn("State is", self.guard.get_blocking_reason())
    
    def test_heartbeat_timeout(self):
        """Test that stale heartbeat blocks autonomy"""
        # Set up valid state
        msg = String()
        msg.data = 'active'
        self.state_pub.publish(msg)
        
        mode_msg = Bool()
        mode_msg.data = True
        self.mode_pub.publish(mode_msg)
        
        hb_msg = Bool()
        hb_msg.data = True
        self.safety_pub.publish(hb_msg)
        self.warning_pub.publish(hb_msg)
        
        rclpy.spin_once(self.node, timeout_sec=0.1)
        self.assertTrue(self.guard.is_autonomy_allowed())
        
        # Wait for heartbeat timeout
        time.sleep(0.6)
        rclpy.spin_once(self.node, timeout_sec=0.1)
        
        self.assertFalse(self.guard.is_autonomy_allowed())
        self.assertIn("stale", self.guard.get_blocking_reason())
    
    def test_timeout_exception(self):
        """Test that timeout raises exception"""
        with self.assertRaises(AutonomyGuardException):
            self.guard.guarded_wait(timeout=0.1)
```

### Integration Tests

```cpp
// test/test_cpp_guard.cpp
#include <gtest/gtest.h>
#include <rclcpp/rclcpp.hpp>
#include "sentor_guard/guard.hpp"
#include <std_msgs/msg/string.hpp>
#include <std_msgs/msg/bool.hpp>

class TestSentorGuard : public ::testing::Test {
protected:
    void SetUp() override {
        rclcpp::init(0, nullptr);
        node_ = std::make_shared<rclcpp::Node>("test_guard_node");
        
        sentor_guard::SentorGuard::Options options;
        options.heartbeat_timeout = std::chrono::milliseconds(500);
        guard_ = std::make_unique<sentor_guard::SentorGuard>(node_, options);
        
        // Create test publishers
        state_pub_ = node_->create_publisher<std_msgs::msg::String>("/robot_state", 10);
        mode_pub_ = node_->create_publisher<std_msgs::msg::Bool>("/autonomous_mode", 10);
        safety_pub_ = node_->create_publisher<std_msgs::msg::Bool>("/safety/heartbeat", 10);
        warning_pub_ = node_->create_publisher<std_msgs::msg::Bool>("/warning/heartbeat", 10);
        
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    
    void TearDown() override {
        rclcpp::shutdown();
    }
    
    rclcpp::Node::SharedPtr node_;
    std::unique_ptr<sentor_guard::SentorGuard> guard_;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr state_pub_;
    rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr mode_pub_;
    rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr safety_pub_;
    rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr warning_pub_;
};

TEST_F(TestSentorGuard, AllConditionsMet) {
    // Publish required state
    auto state_msg = std_msgs::msg::String();
    state_msg.data = "active";
    state_pub_->publish(state_msg);
    
    // Publish autonomous mode
    auto mode_msg = std_msgs::msg::Bool();
    mode_msg.data = true;
    mode_pub_->publish(mode_msg);
    
    // Publish heartbeats
    auto hb_msg = std_msgs::msg::Bool();
    hb_msg.data = true;
    safety_pub_->publish(hb_msg);
    warning_pub_->publish(hb_msg);
    
    rclcpp::spin_some(node_);
    
    EXPECT_TRUE(guard_->isAutonomyAllowed());
}

TEST_F(TestSentorGuard, WrongStateBlocks) {
    auto state_msg = std_msgs::msg::String();
    state_msg.data = "paused";
    state_pub_->publish(state_msg);
    
    rclcpp::spin_some(node_);
    
    EXPECT_FALSE(guard_->isAutonomyAllowed());
    EXPECT_THAT(guard_->getBlockingReason(), ::testing::HasSubstr("State is"));
}

TEST_F(TestSentorGuard, HeartbeatTimeout) {
    // Set up valid state
    auto state_msg = std_msgs::msg::String();
    state_msg.data = "active";
    state_pub_->publish(state_msg);
    
    auto mode_msg = std_msgs::msg::Bool();
    mode_msg.data = true;
    mode_pub_->publish(mode_msg);
    
    auto hb_msg = std_msgs::msg::Bool();
    hb_msg.data = true;
    safety_pub_->publish(hb_msg);
    warning_pub_->publish(hb_msg);
    
    rclcpp::spin_some(node_);
    EXPECT_TRUE(guard_->isAutonomyAllowed());
    
    // Wait for heartbeat timeout
    std::this_thread::sleep_for(std::chrono::milliseconds(600));
    rclcpp::spin_some(node_);
    
    EXPECT_FALSE(guard_->isAutonomyAllowed());
    EXPECT_THAT(guard_->getBlockingReason(), ::testing::HasSubstr("stale"));
}
```

---

## Integration with Existing Architecture

The `sentor_guard` package complements the Safety Controller architecture described in ARCHITECTURE_INTEGRATION.md:

### Relationship Diagram

```
┌────────────────────────────────────────────────────────────┐
│                    Complete System                          │
└────────────────────────────────────────────────────────────┘

RobotStateMachine ──┐
  /robot_state      │
  /autonomous_mode  │
                    ├──> Sentor ──> /safety/heartbeat
                    │               /warning/heartbeat
                    │                      │
                    │                      ↓
                    │              ┌───────────────────┐
                    │              │  sentor_guard     │
                    │              │  (This Package)   │
                    │              │                   │
                    │              │  • Python Guard   │
                    │              │  • C++ Guard      │
                    │              │  • Topic Guards   │
                    │              │  • Lifecycle Mgr  │
                    │              └─────────┬─────────┘
                    │                        │
                    ↓                        ↓
            ┌──────────────────┐    ┌──────────────────┐
            │ Safety Controller│    │  User Code with  │
            │    (Central)     │    │  Guard Libraries │
            └────────┬─────────┘    └────────┬─────────┘
                     │                       │
                     ↓                       ↓
                   Nav2 ────────────> Robot Actions
```

### Usage Scenarios

1. **Centralized Safety Controller** (Strategy 1 from ARCHITECTURE_INTEGRATION.md)
   - Use Safety Controller node with sentor_guard libraries
   - Safety Controller uses C++ Guard for condition checking
   - Manages Nav2 lifecycle based on guard state

2. **Distributed Application Guards** (Complementary approach)
   - Individual nodes use Python/C++ Guard libraries
   - Each node independently checks conditions before actions
   - Defense in depth with local safety checks

3. **Topic-Level Safety** (Strategy 4 from ARCHITECTURE_INTEGRATION.md)
   - Use Topic Guard nodes to filter cmd_vel
   - Transparent integration with existing systems
   - No code changes required

4. **Hybrid Approach** (Recommended)
   - Safety Controller for lifecycle management
   - Topic Guards for cmd_vel filtering
   - Application code uses Guard libraries for critical sections

---

## Summary

The `sentor_guard` package provides a complete toolkit for implementing safe autonomous behavior:

- **Reusable Libraries**: Python and C++ guard classes for inline safety checks
- **Infrastructure Nodes**: Topic guards and lifecycle managers for system-level safety
- **Configuration Driven**: YAML-based configuration for easy deployment
- **Multiple Patterns**: Context managers, RAII, timeouts, and non-blocking checks
- **Well Tested**: Comprehensive unit and integration tests
- **Documented**: Examples and usage patterns for common scenarios

This package complements the Safety Controller architecture by providing the building blocks needed to implement safe autonomy at all levels of the system, from low-level topic filtering to high-level application logic.

---

## Next Steps for Implementation

1. **Package Setup**
   - Create package structure with CMakeLists.txt and package.xml
   - Set up dependencies (rclcpp, rclpy, std_msgs, lifecycle_msgs)

2. **Core Library Development**
   - Implement Python SentorGuard class
   - Implement C++ SentorGuard class
   - Add comprehensive error handling and logging

3. **Node Development**
   - Implement Topic Guard node
   - Implement Lifecycle Guard node
   - Create example user nodes

4. **Configuration and Launch**
   - Create parameter YAML files
   - Implement launch files
   - Document configuration options

5. **Testing**
   - Write unit tests for guard libraries
   - Create integration tests with mock sentor
   - Perform system tests with actual sentor

6. **Documentation**
   - API documentation
   - Tutorial documentation
   - Migration guide for existing systems

7. **Integration**
   - Test with Nav2 stack
   - Validate with RobotStateMachine
   - Benchmark performance and latency
