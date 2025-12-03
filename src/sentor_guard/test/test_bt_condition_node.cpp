/**
 * @file test_bt_condition_node.cpp
 * @brief Tests for CheckAutonomyAllowed BT condition node
 */

#include <gtest/gtest.h>
#include <memory>
#include <chrono>
#include <thread>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "std_msgs/msg/bool.hpp"
#include "behaviortree_cpp/bt_factory.h"
#include "sentor_guard/bt_condition_node.hpp"

using namespace std::chrono_literals;

class TestBTConditionNode : public ::testing::Test
{
protected:
  void SetUp() override
  {
    rclcpp::init(0, nullptr);
    test_node_ = std::make_shared<rclcpp::Node>("test_bt_node");
    
    // Create publishers for test topics
    state_pub_ = test_node_->create_publisher<std_msgs::msg::String>("/robot_state", 10);
    mode_pub_ = test_node_->create_publisher<std_msgs::msg::Bool>("/autonomous_mode", 10);
    
    // Wait for subscriptions to connect
    std::this_thread::sleep_for(100ms);
  }

  void TearDown() override
  {
    test_node_.reset();
    rclcpp::shutdown();
  }
  
  void publishAllConditionsMet()
  {
    auto state_msg = std_msgs::msg::String();
    state_msg.data = "active";
    state_pub_->publish(state_msg);
    
    auto mode_msg = std_msgs::msg::Bool();
    mode_msg.data = true;
    mode_pub_->publish(mode_msg);
    
    // Spin to process messages
    rclcpp::spin_some(test_node_);
    std::this_thread::sleep_for(100ms);
  }
  
  void publishWrongState()
  {
    auto state_msg = std_msgs::msg::String();
    state_msg.data = "paused";
    state_pub_->publish(state_msg);
    
    rclcpp::spin_some(test_node_);
    std::this_thread::sleep_for(100ms);
  }

  rclcpp::Node::SharedPtr test_node_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr state_pub_;
  rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr mode_pub_;
};

TEST_F(TestBTConditionNode, FactoryCreation)
{
  BT::BehaviorTreeFactory factory;
  
  // Register the node
  factory.registerBuilder<sentor_guard::CheckAutonomyAllowed>(
    "CheckAutonomyAllowed",
    [this](const std::string & name, const BT::NodeConfiguration & config) {
      return std::make_unique<sentor_guard::CheckAutonomyAllowed>(name, config, test_node_);
    });
  
  // Verify it can be created
  EXPECT_NO_THROW({
    auto tree = factory.createTreeFromText(R"(
      <root BTCPP_format="4">
        <BehaviorTree>
          <CheckAutonomyAllowed name="test"/>
        </BehaviorTree>
      </root>
    )");
  });
}

TEST_F(TestBTConditionNode, AllConditionsMetReturnsSuccess)
{
  BT::BehaviorTreeFactory factory;
  
  factory.registerBuilder<sentor_guard::CheckAutonomyAllowed>(
    "CheckAutonomyAllowed",
    [this](const std::string & name, const BT::NodeConfiguration & config) {
      return std::make_unique<sentor_guard::CheckAutonomyAllowed>(name, config, test_node_);
    });
  
  auto tree = factory.createTreeFromText(R"(
    <root BTCPP_format="4">
      <BehaviorTree>
        <CheckAutonomyAllowed name="test" update_timeout="500"/>
      </BehaviorTree>
    </root>
  )");
  
  // Publish all conditions met
  publishAllConditionsMet();
  
  // Tick the tree
  auto status = tree.tickWhileRunning();
  
  EXPECT_EQ(status, BT::NodeStatus::SUCCESS);
}

TEST_F(TestBTConditionNode, WrongStateReturnsFailure)
{
  BT::BehaviorTreeFactory factory;
  
  factory.registerBuilder<sentor_guard::CheckAutonomyAllowed>(
    "CheckAutonomyAllowed",
    [this](const std::string & name, const BT::NodeConfiguration & config) {
      return std::make_unique<sentor_guard::CheckAutonomyAllowed>(name, config, test_node_);
    });
  
  auto tree = factory.createTreeFromText(R"(
    <root BTCPP_format="4">
      <BehaviorTree>
        <CheckAutonomyAllowed name="test"/>
      </BehaviorTree>
    </root>
  )");
  
  // Publish wrong state
  publishWrongState();
  
  // Tick the tree
  auto status = tree.tickWhileRunning();
  
  EXPECT_EQ(status, BT::NodeStatus::FAILURE);
}

TEST_F(TestBTConditionNode, CustomTopicsWork)
{
  BT::BehaviorTreeFactory factory;
  
  // Create publishers for custom topics
  auto custom_state_pub = test_node_->create_publisher<std_msgs::msg::String>(
    "/custom/state", 10);
  auto custom_mode_pub = test_node_->create_publisher<std_msgs::msg::Bool>(
    "/custom/mode", 10);
  
  std::this_thread::sleep_for(100ms);
  
  factory.registerBuilder<sentor_guard::CheckAutonomyAllowed>(
    "CheckAutonomyAllowed",
    [this](const std::string & name, const BT::NodeConfiguration & config) {
      return std::make_unique<sentor_guard::CheckAutonomyAllowed>(name, config, test_node_);
    });
  
  auto tree = factory.createTreeFromText(R"(
    <root BTCPP_format="4">
      <BehaviorTree>
        <CheckAutonomyAllowed 
          name="test"
          state_topic="/custom/state"
          mode_topic="/custom/mode"
          required_state="running"
          update_timeout="500"/>
      </BehaviorTree>
    </root>
  )");
  
  // Publish on custom topics
  auto state_msg = std_msgs::msg::String();
  state_msg.data = "running";
  custom_state_pub->publish(state_msg);
  
  auto mode_msg = std_msgs::msg::Bool();
  mode_msg.data = true;
  custom_mode_pub->publish(mode_msg);
  
  rclcpp::spin_some(test_node_);
  std::this_thread::sleep_for(150ms);
  
  auto status = tree.tickWhileRunning();
  
  EXPECT_EQ(status, BT::NodeStatus::SUCCESS);
}

TEST_F(TestBTConditionNode, ContinuousCheckingRespondsToChanges)
{
  BT::BehaviorTreeFactory factory;
  
  factory.registerBuilder<sentor_guard::CheckAutonomyAllowed>(
    "CheckAutonomyAllowed",
    [this](const std::string & name, const BT::NodeConfiguration & config) {
      return std::make_unique<sentor_guard::CheckAutonomyAllowed>(name, config, test_node_);
    });
  
  auto tree = factory.createTreeFromText(R"(
    <root BTCPP_format="4">
      <BehaviorTree>
        <CheckAutonomyAllowed name="test" update_timeout="500"/>
      </BehaviorTree>
    </root>
  )");
  
  // Initially all conditions met
  publishAllConditionsMet();
  EXPECT_EQ(tree.tickWhileRunning(), BT::NodeStatus::SUCCESS);
  
  // Change state to paused
  publishWrongState();
  EXPECT_EQ(tree.tickWhileRunning(), BT::NodeStatus::FAILURE);
  
  // Return to active state
  publishAllConditionsMet();
  EXPECT_EQ(tree.tickWhileRunning(), BT::NodeStatus::SUCCESS);
}

int main(int argc, char ** argv)
{
  testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
