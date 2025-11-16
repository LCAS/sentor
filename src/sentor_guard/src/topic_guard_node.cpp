#include <rclcpp/rclcpp.hpp>
#include <rclcpp/serialization.hpp>
#include <rclcpp/serialized_message.hpp>
#include "sentor_guard/guard.hpp"

/**
 * @brief Topic Guard Node - forwards messages only when guard conditions are met
 * 
 * This is a simplified prototype that forwards serialized messages.
 */
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
        
        if (input_topic.empty() || output_topic.empty() || message_type.empty()) {
            RCLCPP_ERROR(get_logger(), 
                "Required parameters: input_topic, output_topic, message_type");
            throw std::runtime_error("Missing required parameters");
        }
        
        // Initialize guard
        sentor_guard::SentorGuard::Options guard_options;
        guard_options.required_state = get_parameter("required_state").as_string();
        guard_options.heartbeat_timeout = std::chrono::milliseconds(
            static_cast<int>(get_parameter("heartbeat_timeout").as_double() * 1000));
        
        guard_ = std::make_unique<sentor_guard::SentorGuard>(shared_from_this(), guard_options);
        
        // Create generic publisher and subscriber
        publisher_ = create_generic_publisher(output_topic, message_type, 10);
        subscriber_ = create_generic_subscription(
            input_topic, message_type, 10,
            std::bind(&TopicGuardNode::messageCallback, this, std::placeholders::_1));
        
        RCLCPP_INFO(get_logger(),
            "Topic guard initialized: %s -> %s (type: %s)",
            input_topic.c_str(), output_topic.c_str(), message_type.c_str());
    }
    
private:
    void messageCallback(std::shared_ptr<rclcpp::SerializedMessage> msg) {
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

int main(int argc, char** argv) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<TopicGuardNode>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
