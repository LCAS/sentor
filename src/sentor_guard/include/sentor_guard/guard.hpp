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

/**
 * @brief Exception thrown when autonomy guard conditions are not met
 */
class AutonomyGuardException : public std::runtime_error {
public:
    explicit AutonomyGuardException(const std::string& message)
        : std::runtime_error(message) {}
};

/**
 * @brief Guard that checks sentor state and heartbeat before allowing execution
 * 
 * Can be used with RAII pattern via the Guard nested class.
 */
class SentorGuard {
public:
    /**
     * @brief Configuration options for the guard
     */
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

    /**
     * @brief Construct a new Sentor Guard object
     * 
     * @param node ROS2 node to use for subscriptions
     * @param options Configuration options
     */
    explicit SentorGuard(rclcpp::Node::SharedPtr node, const Options& options = Options());
    
    ~SentorGuard() = default;

    /**
     * @brief Check if autonomy is currently allowed (non-blocking)
     * 
     * @return true if all guard conditions are satisfied
     */
    bool isAutonomyAllowed();
    
    /**
     * @brief Get reason why autonomy is blocked
     * 
     * @return String describing why autonomy is not allowed
     */
    std::string getBlockingReason() const;
    
    /**
     * @brief Wait until autonomy is allowed
     * 
     * @param timeout Maximum time to wait (zero means indefinite)
     * @return true if autonomy is allowed, false if timeout occurred
     */
    bool waitForAutonomy(std::chrono::milliseconds timeout = std::chrono::milliseconds::zero());
    
    /**
     * @brief Wait with exception on timeout
     * 
     * @param timeout Maximum time to wait (zero means indefinite)
     * @throws AutonomyGuardException if timeout occurs
     */
    void guardedWait(std::chrono::milliseconds timeout = std::chrono::milliseconds::zero());
    
    /**
     * @brief RAII guard class for automatic safety checking
     * 
     * Usage:
     *   SentorGuard::Guard guard(my_guard);
     *   // Code here only executes when safe
     */
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
    
    mutable std::mutex mutex_;
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
