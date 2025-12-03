#include <rclcpp/rclcpp.hpp>
#include <lifecycle_msgs/srv/change_state.hpp>
#include <lifecycle_msgs/msg/transition.hpp>
#include "sentor_guard/guard.hpp"
#include <map>

/**
 * @brief Lifecycle Guard Node - manages lifecycle state of other nodes based on guard conditions
 */
class LifecycleGuardNode : public rclcpp::Node {
public:
    LifecycleGuardNode() : Node("lifecycle_guard_node") {
        // Declare parameters
        declare_parameter("managed_nodes", std::vector<std::string>{});
        declare_parameter("check_rate", 10.0);
    }
    
    void initialize() {
        auto managed_nodes = get_parameter("managed_nodes").as_string_array();
        
        if (managed_nodes.empty()) {
            RCLCPP_WARN(get_logger(), "No managed nodes specified");
        }
        
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
                auto future = client->async_send_request(request);
                // Note: In production, you'd want to wait for the response
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
                auto future = client->async_send_request(request);
                // Note: In production, you'd want to wait for the response
            }
        }
        
        currently_active_ = false;
    }
    
    std::unique_ptr<sentor_guard::SentorGuard> guard_;
    std::map<std::string, rclcpp::Client<lifecycle_msgs::srv::ChangeState>::SharedPtr> lifecycle_clients_;
    rclcpp::TimerBase::SharedPtr timer_;
    bool currently_active_{false};
};

int main(int argc, char** argv) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<LifecycleGuardNode>();
    node->initialize();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
