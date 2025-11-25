#include "sentor_guard/guard.hpp"
#include "sentor_guard/msg/guard_status.hpp"
#include <sstream>

namespace sentor_guard {

SentorGuard::SentorGuard(rclcpp::Node::SharedPtr node)
    : SentorGuard(node, Options()) {
}

SentorGuard::SentorGuard(rclcpp::Node::SharedPtr node, const Options& options)
    : node_(node), options_(options),
      last_state_time_(node->get_clock()->now()),
      last_mode_time_(node->get_clock()->now()) {
    
    // Create subscriptions
    state_sub_ = node_->create_subscription<std_msgs::msg::String>(
        options_.state_topic, 10,
        std::bind(&SentorGuard::stateCallback, this, std::placeholders::_1));
    
    mode_sub_ = node_->create_subscription<std_msgs::msg::Bool>(
        options_.mode_topic, 10,
        std::bind(&SentorGuard::modeCallback, this, std::placeholders::_1));
    
    // Create publisher for blocking status
    status_publisher_ = node_->create_publisher<sentor_guard::msg::GuardStatus>(
        "/sentor_guard/blocking_reason", 10);
    
    RCLCPP_INFO(node_->get_logger(),
        "SentorGuard initialized: required_state='%s', update_timeout=%ldms",
        options_.required_state.c_str(), options_.update_timeout.count());
}

void SentorGuard::stateCallback(const std_msgs::msg::String::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(mutex_);
    current_state_ = msg->data;
    last_state_time_ = node_->get_clock()->now();
    checkConditions();
}

void SentorGuard::modeCallback(const std_msgs::msg::Bool::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(mutex_);
    autonomous_mode_ = msg->data;
    last_mode_time_ = node_->get_clock()->now();
    checkConditions();
}

void SentorGuard::checkConditions() {
    auto now = node_->get_clock()->now();
    
    // Check if we have received state message
    if (current_state_.empty()) {
        condition_met_ = false;
        return;
    }
    
    // Check if state message is recent
    auto state_age = now - last_state_time_;
    if (state_age > rclcpp::Duration(options_.update_timeout)) {
        condition_met_ = false;
        return;
    }
    
    // Check state value
    if (current_state_ != options_.required_state) {
        condition_met_ = false;
        return;
    }
    
    // Check if mode message is recent
    auto mode_age = now - last_mode_time_;
    if (mode_age > rclcpp::Duration(options_.update_timeout)) {
        condition_met_ = false;
        return;
    }
    
    // Check autonomous mode
    if (options_.require_autonomous_mode && !autonomous_mode_) {
        condition_met_ = false;
        return;
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
    
    // Check state
    if (current_state_.empty()) {
        return "Robot state not received";
    }
    
    auto state_age = now - last_state_time_;
    if (state_age > rclcpp::Duration(options_.update_timeout)) {
        return "Robot state stale (" + std::to_string(state_age.seconds()) + "s old)";
    }
    
    if (current_state_ != options_.required_state) {
        return "State is '" + current_state_ + "', required '" + options_.required_state + "'";
    }
    
    // Check mode
    auto mode_age = now - last_mode_time_;
    if (mode_age > rclcpp::Duration(options_.update_timeout)) {
        return "Autonomous mode stale (" + std::to_string(mode_age.seconds()) + "s old)";
    }
    
    if (options_.require_autonomous_mode && !autonomous_mode_) {
        return "Autonomous mode is disabled";
    }
    
    return "Unknown reason";
}

std::vector<std::string> SentorGuard::getTruncatedCallStack(int max_frames) {
    std::vector<std::string> result;
    
    #ifdef __GNUC__
    void* addresses[max_frames + 5];  // Extra frames to skip
    int size = backtrace(addresses, max_frames + 5);
    char** symbols = backtrace_symbols(addresses, size);
    
    // Skip first 3 frames (this function and guard methods)
    for (int i = 3; i < std::min(size, max_frames + 3); ++i) {
        std::string frame = symbols[i];
        
        // Try to demangle C++ symbols
        size_t begin = frame.find('(');
        size_t end = frame.find('+', begin);
        if (begin != std::string::npos && end != std::string::npos) {
            std::string mangled = frame.substr(begin + 1, end - begin - 1);
            int status;
            char* demangled = abi::__cxa_demangle(mangled.c_str(), nullptr, nullptr, &status);
            if (status == 0 && demangled) {
                result.push_back(demangled);
                free(demangled);
            } else {
                result.push_back(frame);
            }
        } else {
            result.push_back(frame);
        }
    }
    
    free(symbols);
    #else
    result.push_back("Call stack not available on this platform");
    #endif
    
    return result;
}

void SentorGuard::publishBlockingStatus(bool is_blocking, const std::vector<std::string>& call_stack) {
    if (!status_publisher_) {
        return;
    }
    
    try {
        sentor_guard::msg::GuardStatus msg;
        msg.node_name = node_->get_name();
        msg.is_blocking = is_blocking;
        
        if (is_blocking) {
            msg.blocking_reason = getBlockingReason();
            msg.call_stack = call_stack;
            auto now = node_->get_clock()->now();
            msg.blocked_at = now;
            msg.blocked_duration = 0.0;
        } else {
            // Guard is passing after being blocked
            msg.blocking_reason = "";
            msg.call_stack.clear();
            if (is_currently_blocking_) {
                auto now = node_->get_clock()->now();
                auto duration = now - blocking_start_time_;
                msg.blocked_duration = duration.seconds();
                msg.blocked_at = blocking_start_time_;
            } else {
                msg.blocked_duration = 0.0;
                msg.blocked_at = rclcpp::Time(0);
            }
        }
        
        status_publisher_->publish(msg);
        
    } catch (const std::exception& e) {
        RCLCPP_WARN(node_->get_logger(), "Failed to publish blocking status: %s", e.what());
    }
}

bool SentorGuard::waitForAutonomy(std::chrono::milliseconds timeout) {
    auto start = std::chrono::steady_clock::now();
    bool first_block = true;
    
    while (rclcpp::ok()) {
        {
            std::unique_lock<std::mutex> lock(mutex_);
            checkConditions();
            
            if (condition_met_) {
                // If we were previously blocking, publish that we're now passing
                if (is_currently_blocking_) {
                    publishBlockingStatus(false);
                    is_currently_blocking_ = false;
                    blocking_call_stack_.clear();
                }
                return true;
            }
            
            // We're blocking - publish status on first block
            if (first_block) {
                first_block = false;
                is_currently_blocking_ = true;
                blocking_start_time_ = node_->get_clock()->now();
                blocking_call_stack_ = getTruncatedCallStack();
                publishBlockingStatus(true, blocking_call_stack_);
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
