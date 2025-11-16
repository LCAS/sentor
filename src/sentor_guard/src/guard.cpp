#include "sentor_guard/guard.hpp"

namespace sentor_guard {

SentorGuard::SentorGuard(rclcpp::Node::SharedPtr node, const Options& options)
    : node_(node), options_(options),
      last_safety_heartbeat_time_(node->get_clock()->now()),
      last_warning_heartbeat_time_(node->get_clock()->now()) {
    
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

std::string SentorGuard::getBlockingReason() const {
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
