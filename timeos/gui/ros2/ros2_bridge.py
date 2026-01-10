"""ROS2 Bridge - Subprocess-based interface to ROS2 CLI tools.

This module provides a Qt-friendly interface to ROS2 without requiring
rclpy in the GUI process. All ROS2 communication happens through
subprocess calls to ROS2 CLI tools.
"""

import json
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QProcess, QTimer


@dataclass
class NodeInfo:
    """Information about a ROS2 node."""
    name: str
    namespace: str = '/'
    status: str = 'unknown'  # running, stopped, not_responding
    full_name: str = ''

    def __post_init__(self):
        if not self.full_name:
            self.full_name = f"{self.namespace.rstrip('/')}/{self.name}"


@dataclass
class TopicInfo:
    """Information about a ROS2 topic."""
    name: str
    msg_type: str = ''
    publishers: int = 0
    subscribers: int = 0


@dataclass
class ServiceInfo:
    """Information about a ROS2 service."""
    name: str
    srv_type: str = ''
    node: str = ''


# TimeOS-specific node configurations
TIMEOS_NODES = {
    'timeline': 'timeline_node',
    'field_generator': 'field_generator_node',
    'safety_monitor': 'safety_monitor_node',
    'thermal_monitor': 'thermal_monitor_node',
    'anchor': 'anchor_node',
    'tdu': 'tdu_node',
    'causality_monitor': 'causality_monitor_node',
    't_symmetry_analyzer': 't_symmetry_analyzer_node',
    'sensor_aggregator': 'sensor_aggregator_node',
    'experiment_controller': 'experiment_controller_node',
    'data_recorder': 'data_recorder_node',
}

# Launch configurations
LAUNCH_CONFIGS = {
    'minimal': {
        'name': 'Minimal (Core)',
        'description': 'Core nodes for basic testing',
        'launch_file': 'minimal.launch.py',
        'nodes': ['timeline', 'safety_monitor', 'field_generator'],
    },
    't_symmetry': {
        'name': 'T-Symmetry Experiment',
        'description': 'Full T-symmetry research platform',
        'launch_file': 't_symmetry_experiment.launch.py',
        'nodes': [
            'timeline', 'field_generator', 'thermal_monitor',
            'safety_monitor', 'anchor', 'sensor_aggregator',
            't_symmetry_analyzer', 'experiment_controller',
            'data_recorder', 'causality_monitor',
        ],
    },
}

# Key topics for monitoring
PRIORITY_TOPICS = [
    '/timeos/field_state',
    '/timeos/thermal_state',
    '/timeos/safety_state',
    '/timeos/timeline_status',
    '/timeos/t_symmetry/result',
]

# Key services
PRIORITY_SERVICES = [
    ('/timeos/set_field', 'timeos_msgs/srv/SetField'),
    ('/timeos/arm_system', 'timeos_msgs/srv/ArmSystem'),
    ('/timeos/trigger_estop', 'timeos_msgs/srv/TriggerEstop'),
    ('/timeos/start_experiment', 'timeos_msgs/srv/StartExperiment'),
    ('/timeos/create_event', 'timeos_msgs/srv/CreateEvent'),
]


class ROS2Bridge(QObject):
    """Subprocess-based interface to ROS2 CLI tools.

    Signals:
        ros2_available_changed(bool): ROS2 availability changed
        nodes_updated(list): Node list refreshed
        topics_updated(list): Topic list refreshed
        services_updated(list): Service list refreshed
        topic_data_received(str, str): topic_name, json_data
        service_response(str, bool, str): service_name, success, response
        launch_started(str): launch_name
        launch_stopped(str): launch_name
        error_occurred(str): error message
    """

    ros2_available_changed = Signal(bool)
    nodes_updated = Signal(list)
    topics_updated = Signal(list)
    services_updated = Signal(list)
    topic_data_received = Signal(str, str)
    service_response = Signal(str, bool, str)
    launch_started = Signal(str)
    launch_stopped = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._ros2_available = False
        self._ros2_path: Optional[str] = None
        self._workspace_path: Optional[Path] = None

        # Active processes
        self._launch_processes: Dict[str, QProcess] = {}
        self._echo_processes: Dict[str, QProcess] = {}
        self._service_processes: Dict[str, QProcess] = {}

        # Cached data
        self._nodes: List[NodeInfo] = []
        self._topics: List[TopicInfo] = []
        self._services: List[ServiceInfo] = []

        # Auto-refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_refresh_timeout)

        # Check ROS2 availability
        self._check_ros2_available()

    @property
    def ros2_available(self) -> bool:
        """Whether ROS2 CLI tools are available."""
        return self._ros2_available

    @property
    def nodes(self) -> List[NodeInfo]:
        """Current list of known nodes."""
        return self._nodes

    @property
    def topics(self) -> List[TopicInfo]:
        """Current list of known topics."""
        return self._topics

    @property
    def services(self) -> List[ServiceInfo]:
        """Current list of known services."""
        return self._services

    def _check_ros2_available(self) -> bool:
        """Check if ROS2 CLI tools are available."""
        ros2_path = shutil.which('ros2')
        if ros2_path:
            try:
                result = subprocess.run(
                    ['ros2', 'node', 'list'],
                    capture_output=True,
                    timeout=5,
                )
                self._ros2_available = True
                self._ros2_path = ros2_path
                self._find_workspace()
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
                self._ros2_available = False
        else:
            self._ros2_available = False

        self.ros2_available_changed.emit(self._ros2_available)
        return self._ros2_available

    def _find_workspace(self) -> None:
        """Find TimeOS ROS2 workspace."""
        # Look for ros2_ws relative to timeos package
        try:
            import timeos
            pkg_path = Path(timeos.__file__).parent.parent
            ws_path = pkg_path / 'ros2_ws'
            if ws_path.exists():
                self._workspace_path = ws_path
                return
        except Exception:
            pass

        # Check common locations
        common_paths = [
            Path.home() / 'development/projects/gitprojects/TimeOS/ros2_ws',
            Path.home() / 'ros2_ws',
            Path('/opt/timeos/ros2_ws'),
        ]
        for path in common_paths:
            if path.exists():
                self._workspace_path = path
                return

    def start_refresh(self, interval_ms: int = 2000) -> None:
        """Start auto-refreshing node/topic/service lists."""
        self._refresh_timer.start(interval_ms)
        self.refresh_all()

    def stop_refresh(self) -> None:
        """Stop auto-refreshing."""
        self._refresh_timer.stop()

    def _on_refresh_timeout(self) -> None:
        """Handle refresh timer."""
        self.refresh_all()

    def refresh_all(self) -> None:
        """Refresh all lists."""
        if not self._ros2_available:
            return
        self.get_node_list()
        self.get_topic_list()
        self.get_service_list()

    def get_node_list(self) -> None:
        """Get list of running ROS2 nodes asynchronously."""
        if not self._ros2_available:
            return

        process = QProcess(self)
        process.finished.connect(lambda: self._on_node_list_finished(process))
        process.start('ros2', ['node', 'list'])

    def _on_node_list_finished(self, process: QProcess) -> None:
        """Handle node list completion."""
        if process.exitCode() != 0:
            return

        output = process.readAllStandardOutput().data().decode('utf-8')
        nodes = []

        for line in output.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            # Parse node name (format: /namespace/node_name or /node_name)
            parts = line.rsplit('/', 1)
            if len(parts) == 2:
                namespace = '/' + parts[0].lstrip('/') if parts[0] else '/'
                name = parts[1]
            else:
                namespace = '/'
                name = line.lstrip('/')

            nodes.append(NodeInfo(
                name=name,
                namespace=namespace,
                status='running',
                full_name=line,
            ))

        self._nodes = nodes
        self.nodes_updated.emit(nodes)
        process.deleteLater()

    def get_topic_list(self) -> None:
        """Get list of ROS2 topics asynchronously."""
        if not self._ros2_available:
            return

        process = QProcess(self)
        process.finished.connect(lambda: self._on_topic_list_finished(process))
        process.start('ros2', ['topic', 'list', '-t'])

    def _on_topic_list_finished(self, process: QProcess) -> None:
        """Handle topic list completion."""
        if process.exitCode() != 0:
            return

        output = process.readAllStandardOutput().data().decode('utf-8')
        topics = []

        for line in output.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            # Parse topic (format: /topic_name [msg_type])
            if '[' in line:
                parts = line.split('[')
                name = parts[0].strip()
                msg_type = parts[1].rstrip(']').strip()
            else:
                name = line
                msg_type = ''

            topics.append(TopicInfo(name=name, msg_type=msg_type))

        self._topics = topics
        self.topics_updated.emit(topics)
        process.deleteLater()

    def get_service_list(self) -> None:
        """Get list of ROS2 services asynchronously."""
        if not self._ros2_available:
            return

        process = QProcess(self)
        process.finished.connect(lambda: self._on_service_list_finished(process))
        process.start('ros2', ['service', 'list', '-t'])

    def _on_service_list_finished(self, process: QProcess) -> None:
        """Handle service list completion."""
        if process.exitCode() != 0:
            return

        output = process.readAllStandardOutput().data().decode('utf-8')
        services = []

        for line in output.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            # Parse service (format: /service_name [srv_type])
            if '[' in line:
                parts = line.split('[')
                name = parts[0].strip()
                srv_type = parts[1].rstrip(']').strip()
            else:
                name = line
                srv_type = ''

            services.append(ServiceInfo(name=name, srv_type=srv_type))

        self._services = services
        self.services_updated.emit(services)
        process.deleteLater()

    def echo_topic(self, topic: str, callback: Optional[Callable] = None) -> bool:
        """Start echoing a topic.

        Args:
            topic: Topic name to echo
            callback: Optional callback for each message

        Returns:
            True if started successfully
        """
        if not self._ros2_available:
            return False

        if topic in self._echo_processes:
            self.stop_echo_topic(topic)

        process = QProcess(self)
        process.readyReadStandardOutput.connect(
            lambda: self._on_topic_data(topic, process, callback)
        )
        process.finished.connect(
            lambda: self._on_echo_finished(topic, process)
        )

        # Echo with YAML output for easier parsing
        process.start('ros2', ['topic', 'echo', '--once', topic])
        self._echo_processes[topic] = process
        return True

    def _on_topic_data(
        self,
        topic: str,
        process: QProcess,
        callback: Optional[Callable]
    ) -> None:
        """Handle incoming topic data."""
        data = process.readAllStandardOutput().data().decode('utf-8')
        self.topic_data_received.emit(topic, data)
        if callback:
            callback(topic, data)

    def _on_echo_finished(self, topic: str, process: QProcess) -> None:
        """Handle echo process finished."""
        if topic in self._echo_processes:
            del self._echo_processes[topic]
        process.deleteLater()

    def stop_echo_topic(self, topic: str) -> None:
        """Stop echoing a topic."""
        if topic in self._echo_processes:
            process = self._echo_processes[topic]
            process.terminate()
            if not process.waitForFinished(1000):
                process.kill()
            del self._echo_processes[topic]

    def call_service(
        self,
        service: str,
        srv_type: str,
        request: Dict[str, Any],
    ) -> None:
        """Call a ROS2 service asynchronously.

        Args:
            service: Service name
            srv_type: Service type (e.g., 'timeos_msgs/srv/SetField')
            request: Request data as dictionary
        """
        if not self._ros2_available:
            self.service_response.emit(service, False, "ROS2 not available")
            return

        process = QProcess(self)
        process.finished.connect(
            lambda: self._on_service_finished(service, process)
        )

        # Convert request to YAML format
        request_yaml = json.dumps(request)

        process.start('ros2', [
            'service', 'call',
            service,
            srv_type,
            request_yaml,
        ])
        self._service_processes[service] = process

    def _on_service_finished(self, service: str, process: QProcess) -> None:
        """Handle service call completion."""
        success = process.exitCode() == 0
        output = process.readAllStandardOutput().data().decode('utf-8')
        error = process.readAllStandardError().data().decode('utf-8')

        response = output if success else error
        self.service_response.emit(service, success, response)

        if service in self._service_processes:
            del self._service_processes[service]
        process.deleteLater()

    def launch(
        self,
        config_name: str,
        args: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Launch nodes using a launch configuration.

        Args:
            config_name: Name of launch config ('minimal', 't_symmetry')
            args: Optional launch arguments

        Returns:
            True if launch started
        """
        if not self._ros2_available:
            return False

        if config_name not in LAUNCH_CONFIGS:
            self.error_occurred.emit(f"Unknown launch config: {config_name}")
            return False

        if config_name in self._launch_processes:
            self.error_occurred.emit(f"Launch {config_name} already running")
            return False

        config = LAUNCH_CONFIGS[config_name]
        launch_file = config['launch_file']

        process = QProcess(self)
        process.finished.connect(
            lambda: self._on_launch_finished(config_name, process)
        )
        process.readyReadStandardOutput.connect(
            lambda: self._on_launch_output(config_name, process)
        )
        process.readyReadStandardError.connect(
            lambda: self._on_launch_error(config_name, process)
        )

        cmd_args = ['launch', 'timeos_ros', launch_file]
        if args:
            for key, value in args.items():
                cmd_args.append(f'{key}:={value}')

        process.start('ros2', cmd_args)
        self._launch_processes[config_name] = process
        self.launch_started.emit(config_name)
        return True

    def _on_launch_output(self, config_name: str, process: QProcess) -> None:
        """Handle launch stdout."""
        # Could be used to parse node startup messages
        pass

    def _on_launch_error(self, config_name: str, process: QProcess) -> None:
        """Handle launch stderr."""
        error = process.readAllStandardError().data().decode('utf-8')
        if error.strip():
            # Filter out INFO/WARN messages from stderr
            for line in error.split('\n'):
                if 'ERROR' in line or 'error' in line.lower():
                    self.error_occurred.emit(line)

    def _on_launch_finished(self, config_name: str, process: QProcess) -> None:
        """Handle launch termination."""
        if config_name in self._launch_processes:
            del self._launch_processes[config_name]
        self.launch_stopped.emit(config_name)
        process.deleteLater()

    def stop_launch(self, config_name: str) -> bool:
        """Stop a running launch.

        Args:
            config_name: Name of launch config to stop

        Returns:
            True if stopped
        """
        if config_name not in self._launch_processes:
            return False

        process = self._launch_processes[config_name]
        process.terminate()
        if not process.waitForFinished(3000):
            process.kill()
            process.waitForFinished(1000)

        return True

    def is_launch_running(self, config_name: str) -> bool:
        """Check if a launch is running."""
        return config_name in self._launch_processes

    def get_running_launches(self) -> List[str]:
        """Get list of running launch configurations."""
        return list(self._launch_processes.keys())

    def get_timeos_nodes_status(self) -> Dict[str, str]:
        """Get status of all TimeOS nodes.

        Returns:
            Dictionary of node_name -> status
        """
        running_names = {n.name for n in self._nodes}

        status = {}
        for short_name, full_name in TIMEOS_NODES.items():
            if full_name in running_names or short_name in running_names:
                status[short_name] = 'running'
            else:
                status[short_name] = 'stopped'

        return status

    def shutdown(self) -> None:
        """Clean shutdown of all processes."""
        self._refresh_timer.stop()

        # Stop all echo processes
        for topic in list(self._echo_processes.keys()):
            self.stop_echo_topic(topic)

        # Stop all launches
        for config_name in list(self._launch_processes.keys()):
            self.stop_launch(config_name)

        # Kill any remaining service processes
        for service, process in self._service_processes.items():
            process.terminate()
            if not process.waitForFinished(1000):
                process.kill()
