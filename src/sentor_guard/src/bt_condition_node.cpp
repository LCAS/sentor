#include "sentor_guard/bt_condition_node.hpp"

namespace sentor_guard
{

CheckAutonomyAllowed::CheckAutonomyAllowed(
  const std::string & name,
  const BT::NodeConfiguration & config,
  rclcpp::Node::SharedPtr node)
: BT::ConditionNode(name, config),
  node_(node)
{
  // Get configuration from ports (or use defaults)
  getInput("state_topic", state_topic_);
  getInput("mode_topic", mode_topic_);
  getInput("required_state", required_state_);
  
  // Get timeout in milliseconds
  int timeout_ms;
  if (getInput("update_timeout", timeout_ms)) {
    update_timeout_ = std::chrono::milliseconds(timeout_ms);
  } else {
    update_timeout_ = std::chrono::milliseconds(1000);
  }
  
  // Get optional boolean flag
  getInput("require_autonomous_mode", require_autonomous_mode_);
  
  // Create guard with configuration
  SentorGuard::Options options;
  
  if (!state_topic_.empty()) {
    options.state_topic = state_topic_;
  }
  if (!mode_topic_.empty()) {
    options.mode_topic = mode_topic_;
  }
  if (!required_state_.empty()) {
    options.required_state = required_state_;
  }
  
  options.update_timeout = update_timeout_;
  options.require_autonomous_mode = require_autonomous_mode_;
  
  guard_ = std::make_shared<SentorGuard>(node_, options);
  
  RCLCPP_INFO(node_->get_logger(),
    "CheckAutonomyAllowed BT node initialized: required_state='%s'",
    options.required_state.c_str());
}

BT::PortsList CheckAutonomyAllowed::providedPorts()
{
  return {
    BT::InputPort<std::string>("state_topic", "/robot_state", 
                                "Topic publishing robot state"),
    BT::InputPort<std::string>("mode_topic", "/autonomous_mode",
                                "Topic publishing autonomous mode"),
    BT::InputPort<std::string>("required_state", "active",
                                "Required robot state for autonomy"),
    BT::InputPort<int>("update_timeout", 1000,
                       "Message update timeout in milliseconds"),
    BT::InputPort<bool>("require_autonomous_mode", true,
                        "Whether autonomous mode must be enabled")
  };
}

BT::NodeStatus CheckAutonomyAllowed::tick()
{
  // Check if autonomy is currently allowed
  if (guard_->isAutonomyAllowed()) {
    return BT::NodeStatus::SUCCESS;
  } else {
    // Log reason for debugging (at debug level to avoid spam)
    std::string reason = guard_->getBlockingReason();
    RCLCPP_DEBUG(node_->get_logger(),
      "Autonomy not allowed: %s", reason.c_str());
    return BT::NodeStatus::FAILURE;
  }
}

} // namespace sentor_guard
