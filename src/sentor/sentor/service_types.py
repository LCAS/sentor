#!/usr/bin/env python3

# ✅ Import all services
from action_msgs.srv import CancelGoal
from composition_interfaces.srv import ListNodes, LoadNode, UnloadNode
from control_msgs.srv import QueryCalibrationState, QueryTrajectoryState
from controller_manager_msgs.srv import ConfigureController, ListControllerTypes, ListControllers
from controller_manager_msgs.srv import ListHardwareComponents, ListHardwareInterfaces
from controller_manager_msgs.srv import LoadController, ReloadControllerLibraries, SetHardwareComponentState
from controller_manager_msgs.srv import SwitchController, UnloadController
from diagnostic_msgs.srv import AddDiagnostics, SelfTest
from example_interfaces.srv import AddTwoInts, SetBool, Trigger
from geographic_msgs.srv import GetGeoPath, GetGeographicMap, GetRoutePlan, UpdateGeographicMap
from lifecycle_msgs.srv import ChangeState, GetAvailableStates, GetAvailableTransitions, GetState
from logging_demo.srv import ConfigLogger
from map_msgs.srv import GetMapROI, GetPointMap, GetPointMapROI, ProjectedMapsInfo, SaveMap, SetMapProjections
from nav_msgs.srv import GetMap, GetPlan, LoadMap, SetMap
from pcl_msgs.srv import UpdateFilename
from rcl_interfaces.srv import DescribeParameters, GetParameterTypes, GetParameters
from rcl_interfaces.srv import ListParameters, SetParameters, SetParametersAtomically
from robot_localization.srv import FromLL, GetState, SetDatum, SetPose, ToLL, ToggleFilterProcessing
from rosbag2_interfaces.srv import Burst, GetRate, IsPaused, Pause, PlayNext, Resume, Seek, SetRate, Snapshot, TogglePaused
from sensor_msgs.srv import SetCameraInfo
from std_srvs.srv import Empty
from tf2_msgs.srv import FrameGraph
from turtlesim.srv import Kill, SetPen, Spawn, TeleportAbsolute, TeleportRelative
from visualization_msgs.srv import GetInteractiveMarkers
from zed_msgs.srv import SetPose, SetROI, StartSvoRec
from rcl_interfaces.srv import GetParameters, SetParameters, ListParameters
from lifecycle_msgs.srv import GetState, ChangeState
from nav_msgs.srv import GetPlan

def get_service_type(service_name):
    """ Returns the correct service type based on the service name """
    service_map = {
        "/cancel_goal": CancelGoal,
        "/list_nodes": ListNodes,
        "/load_node": LoadNode,
        "/unload_node": UnloadNode,
        "/query_calibration_state": QueryCalibrationState,
        "/query_trajectory_state": QueryTrajectoryState,
        "/configure_controller": ConfigureController,
        "/list_controller_types": ListControllerTypes,
        "/list_controllers": ListControllers,
        "/list_hardware_components": ListHardwareComponents,
        "/list_hardware_interfaces": ListHardwareInterfaces,
        "/load_controller": LoadController,
        "/reload_controller_libraries": ReloadControllerLibraries,
        "/set_hardware_component_state": SetHardwareComponentState,
        "/switch_controller": SwitchController,
        "/unload_controller": UnloadController,
        "/add_diagnostics": AddDiagnostics,
        "/self_test": SelfTest,
        "/add_two_ints": AddTwoInts,
        "/set_bool": SetBool,
        "/trigger": Trigger,
        "/get_geo_path": GetGeoPath,
        "/get_geographic_map": GetGeographicMap,
        "/get_route_plan": GetRoutePlan,
        "/update_geographic_map": UpdateGeographicMap,
        "/change_state": ChangeState,
        "/get_available_states": GetAvailableStates,
        "/get_available_transitions": GetAvailableTransitions,
        "/get_state": GetState,
        "/config_logger": ConfigLogger,
        "/get_map_roi": GetMapROI,
        "/get_point_map": GetPointMap,
        "/get_point_map_roi": GetPointMapROI,
        "/projected_maps_info": ProjectedMapsInfo,
        "/save_map": SaveMap,
        "/set_map_projections": SetMapProjections,
        "/get_map": GetMap,
        "/get_plan": GetPlan,
        "/load_map": LoadMap,
        "/set_map": SetMap,
        "/update_filename": UpdateFilename,
        "/describe_parameters": DescribeParameters,
        "/get_parameter_types": GetParameterTypes,
        "/get_parameters": GetParameters,
        "/list_parameters": ListParameters,
        "/set_parameters": SetParameters,
        "/set_parameters_atomically": SetParametersAtomically,
        "/from_ll": FromLL,
        "/set_datum": SetDatum,
        "/set_pose": SetPose,
        "/to_ll": ToLL,
        "/toggle_filter_processing": ToggleFilterProcessing,
        "/burst": Burst,
        "/get_rate": GetRate,
        "/is_paused": IsPaused,
        "/pause": Pause,
        "/play_next": PlayNext,
        "/resume": Resume,
        "/seek": Seek,
        "/set_rate": SetRate,
        "/snapshot": Snapshot,
        "/toggle_paused": TogglePaused,
        "/set_camera_info": SetCameraInfo,
        "/empty": Empty,
        "/frame_graph": FrameGraph,
        "/kill": Kill,
        "/set_pen": SetPen,
        "/spawn": Spawn,
        "/teleport_absolute": TeleportAbsolute,
        "/teleport_relative": TeleportRelative,
        "/get_interactive_markers": GetInteractiveMarkers,
        "/zed_set_pose": SetPose,
        "/zed_set_roi": SetROI,
        "/zed_start_svo_rec": StartSvoRec,
        "/map_server/get_parameters": GetParameters,
        "/map_server/set_parameters": SetParameters,
        "/map_server/get_state": GetState,
        "/map_server/list_parameters": ListParameters,
        "/planner_server/get_state": GetState,  # Fix: Add correct service type
        "/planner_server/get_plan": GetPlan,
        "/planner_server/change_state": ChangeState,
    }
    
    if service_name in service_map:
        return service_map[service_name]
    else:
        raise ValueError(f"Unknown service type for {service_name}")