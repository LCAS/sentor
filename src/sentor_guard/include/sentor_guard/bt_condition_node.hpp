#pragma once

#include <string>
#include <memory>
#include <chrono>

#include "behaviortree_cpp/condition_node.h"
#include "rclcpp/rclcpp.hpp"
#include "sentor_guard/guard.hpp"

namespace sentor_guard
{

/**
 * @brief BehaviorTree condition node that checks sentor guard status
 * 
 * This condition node continuously checks if autonomy is allowed based on
 * RobotStateMachine state and mode. It returns SUCCESS when autonomy is 
 * allowed and FAILURE otherwise.
 * 
 * This enables behavior trees to respond to safety conditions in real-time,
 * allowing navigation to pause when conditions are not met and resume when
 * they are satisfied again.
 * 
 * Example usage in BT XML:
 * @code{.xml}
 * <CheckAutonomyAllowed 
 *   state_topic="/robot_state"
 *   mode_topic="/autonomous_mode"
 *   required_state="active"
 *   update_timeout="1000"/>
 * @endcode
 */
class CheckAutonomyAllowed : public BT::ConditionNode
{
public:
  /**
   * @brief Constructor for the BT condition node
   * 
   * @param name Name of the node in the behavior tree
   * @param config Configuration object containing node parameters
   * @param node ROS2 node pointer for subscriptions
   */
  CheckAutonomyAllowed(
    const std::string & name,
    const BT::NodeConfiguration & config,
    rclcpp::Node::SharedPtr node);

  /**
   * @brief Provides the list of ports (inputs/outputs) for this BT node
   */
  static BT::PortsList providedPorts();

  /**
   * @brief Called when the node is executed by the behavior tree
   * 
   * @return SUCCESS if autonomy is allowed, FAILURE otherwise
   */
  BT::NodeStatus tick() override;

private:
  rclcpp::Node::SharedPtr node_;
  std::shared_ptr<SentorGuard> guard_;
  
  // Configuration
  std::string state_topic_;
  std::string mode_topic_;
  std::string required_state_;
  std::chrono::milliseconds update_timeout_;
  bool require_autonomous_mode_;
};

/**
 * @brief Factory function for creating CheckAutonomyAllowed nodes
 * 
 * This is used by the BehaviorTree.CPP factory to create instances of the node.
 * The node pointer must be passed via the blackboard with key "node".
 */
inline std::unique_ptr<BT::TreeNode> CheckAutonomyAllowedFactory(
  const std::string & name,
  const BT::NodeConfiguration & config)
{
  rclcpp::Node::SharedPtr node;
  if (!config.blackboard->get("node", node)) {
    throw std::runtime_error("Failed to get 'node' from blackboard");
  }
  
  if (!node) {
    throw BT::RuntimeError("CheckAutonomyAllowed requires a ROS2 node in blackboard");
  }
  
  return std::make_unique<CheckAutonomyAllowed>(name, config, node);
}

} // namespace sentor_guard
