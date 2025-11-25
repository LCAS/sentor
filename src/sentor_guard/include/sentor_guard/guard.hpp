#pragma once

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>
#include <std_msgs/msg/bool.hpp>
#include <mutex>
#include <condition_variable>
#include <memory>
#include <string>
#include <chrono>
#include <vector>
#include <execinfo.h>
#include <cxxabi.h>

// Forward declare the generated message type
namespace sentor_guard { namespace msg { class GuardStatus; } }

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
 * @brief Guard that checks robot state and autonomous mode before allowing execution
 * 
 * Monitors /robot_state and /autonomous_mode topics from RobotStateMachine.
 * The guard ensures these messages are recent (within update_timeout).
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
        std::chrono::milliseconds update_timeout{1000};
        std::string required_state = "active";
        bool require_autonomous_mode = true;
    };

    /**
     * @brief Construct a new Sentor Guard object with default options
     * 
     * @param node ROS2 node to use for subscriptions
     */
    explicit SentorGuard(rclcpp::Node::SharedPtr node);
    
    /**
     * @brief Construct a new Sentor Guard object
     * 
     * @param node ROS2 node to use for subscriptions
     * @param options Configuration options
     */
    SentorGuard(rclcpp::Node::SharedPtr node, const Options& options);
    
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
    
    void checkConditions();
    void publishBlockingStatus(bool is_blocking, const std::vector<std::string>& call_stack = {});
    std::vector<std::string> getTruncatedCallStack(int max_frames = 10);
    
    rclcpp::Node::SharedPtr node_;
    Options options_;
    
    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr state_sub_;
    rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr mode_sub_;
    rclcpp::Publisher<sentor_guard::msg::GuardStatus>::SharedPtr status_publisher_;
    
    mutable std::mutex mutex_;
    std::condition_variable cv_;
    
    std::string current_state_;
    bool autonomous_mode_{false};
    rclcpp::Time last_state_time_;
    rclcpp::Time last_mode_time_;
    bool condition_met_{false};
    
    // Blocking status tracking
    bool is_currently_blocking_{false};
    rclcpp::Time blocking_start_time_;
    std::vector<std::string> blocking_call_stack_;
};

} // namespace sentor_guard
