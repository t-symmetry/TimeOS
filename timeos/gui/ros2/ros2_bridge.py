"""ROS2 Bridge - Subprocess-based interface to ROS2 CLI tools.

This module provides a Qt-friendly interface to ROS2 without requiring
rclpy in the GUI process. All ROS2 communication happens through
subprocess calls to ROS2 CLI tools.

The bridge automatically detects and sources the timeos-ros conda
environment if ROS2 is not directly available in PATH.
"""

import json
import os
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QProcess, QTimer, QProcessEnvironment


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

# State topics - these are polled regularly for machine state
STATE_TOPICS = {
    'field': '/timeos/field_state',
    'thermal': '/timeos/thermal_state',
    'safety': '/timeos/safety_state',
    'tdu': '/timeos/tdu_state',
    'system': '/timeos/system_status',
}

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
        state_updated(dict): Combined machine state from all topics
        field_state_updated(dict): Field generator state
        thermal_state_updated(dict): Thermal system state
        safety_state_updated(dict): Safety system state
    """

    ros2_available_changed = Signal(bool)
    nodes_updated = Signal(list)
    topics_updated = Signal(list)
    state_updated = Signal(dict)
    field_state_updated = Signal(dict)
    thermal_state_updated = Signal(dict)
    safety_state_updated = Signal(dict)
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
        self._conda_env_path: Optional[Path] = None
        self._ros2_env: Optional[QProcessEnvironment] = None

        # Active processes
        self._launch_processes: Dict[str, QProcess] = {}
        self._echo_processes: Dict[str, QProcess] = {}
        self._service_processes: Dict[str, QProcess] = {}

        # Cached data
        self._nodes: List[NodeInfo] = []
        self._topics: List[TopicInfo] = []
        self._services: List[ServiceInfo] = []

        # Cached machine state from ROS2 topics
        self._state_cache: Dict[str, Dict[str, Any]] = {
            'field': {},
            'thermal': {},
            'safety': {},
            'tdu': {},
            'system': {},
        }
        self._state_poll_processes: Dict[str, QProcess] = {}

        # Auto-refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_refresh_timeout)

        # State polling timer (faster rate for machine state)
        self._state_timer = QTimer(self)
        self._state_timer.timeout.connect(self._poll_state_topics)

        # Check ROS2 availability (also finds conda env if needed)
        self._check_ros2_available()

    @property
    def ros2_available(self) -> bool:
        """Whether ROS2 CLI tools are available."""
        return self._ros2_available

    @property
    def ros2_source(self) -> str:
        """Description of where ROS2 is being used from."""
        if not self._ros2_available:
            return "Not available"
        if self._conda_env_path:
            return f"timeos-ros conda ({self._conda_env_path})"
        return f"System PATH ({self._ros2_path})"

    @property
    def using_conda(self) -> bool:
        """Whether ROS2 is being used from a conda environment."""
        return self._conda_env_path is not None

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
        """Check if ROS2 CLI tools are available.

        First checks if ros2 is in PATH. If not, looks for the timeos-ros
        conda environment and sets up the environment for ROS2 commands.
        """
        # First, check if ros2 is directly available
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
                self.ros2_available_changed.emit(self._ros2_available)
                return self._ros2_available
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
                pass

        # Try to find timeos-ros conda environment
        if self._find_conda_ros2_env():
            self._ros2_available = True
            self._find_workspace()
            self.ros2_available_changed.emit(self._ros2_available)
            return self._ros2_available

        self._ros2_available = False
        self.ros2_available_changed.emit(self._ros2_available)
        return self._ros2_available

    def _find_conda_ros2_env(self) -> bool:
        """Find and configure the timeos-ros conda environment.

        Returns:
            True if conda environment was found and configured.
        """
        # Look for conda installation
        conda_base = None
        for path in [
            Path.home() / 'miniconda3',
            Path.home() / 'anaconda3',
            Path.home() / 'mambaforge',
            Path.home() / 'miniforge3',
            Path('/opt/conda'),
            Path('/usr/local/conda'),
        ]:
            if path.exists():
                conda_base = path
                break

        if not conda_base:
            return False

        # Look for timeos-ros environment
        env_path = conda_base / 'envs' / 'timeos-ros'
        if not env_path.exists():
            return False

        # Check if ros2 exists in that environment
        ros2_bin = env_path / 'bin' / 'ros2'
        if not ros2_bin.exists():
            return False

        self._conda_env_path = env_path
        self._ros2_path = str(ros2_bin)

        # Build environment for ROS2 processes
        self._ros2_env = self._build_ros2_environment(env_path)

        # Test that it works
        try:
            result = subprocess.run(
                [str(ros2_bin), 'node', 'list'],
                capture_output=True,
                timeout=5,
                env=self._get_ros2_env_dict(),
            )
            return True
        except Exception:
            self._conda_env_path = None
            self._ros2_path = None
            self._ros2_env = None
            return False

    def _build_ros2_environment(self, env_path: Path) -> QProcessEnvironment:
        """Build QProcessEnvironment for ROS2 commands.

        Args:
            env_path: Path to the conda environment.

        Returns:
            Configured QProcessEnvironment.
        """
        env = QProcessEnvironment.systemEnvironment()

        # Add conda environment to PATH
        current_path = env.value('PATH', '')
        new_path = f"{env_path}/bin:{current_path}"
        env.insert('PATH', new_path)

        # Set conda environment variables
        env.insert('CONDA_PREFIX', str(env_path))
        env.insert('CONDA_DEFAULT_ENV', 'timeos-ros')

        # ROS2-specific environment variables
        env.insert('ROS_VERSION', '2')
        env.insert('ROS_PYTHON_VERSION', '3')
        env.insert('ROS_DISTRO', 'humble')

        # AMENT environment
        env.insert('AMENT_PREFIX_PATH', str(env_path))
        env.insert('CMAKE_PREFIX_PATH', str(env_path))
        env.insert('COLCON_PREFIX_PATH', str(env_path))

        # Python path for ROS2 packages
        python_path = env.value('PYTHONPATH', '')
        ros2_python = f"{env_path}/lib/python3.11/site-packages"
        if python_path:
            env.insert('PYTHONPATH', f"{ros2_python}:{python_path}")
        else:
            env.insert('PYTHONPATH', ros2_python)

        # Also add the TimeOS workspace if found
        if self._workspace_path:
            install_path = self._workspace_path / 'install'
            if install_path.exists():
                ament = env.value('AMENT_PREFIX_PATH', '')
                env.insert('AMENT_PREFIX_PATH', f"{install_path}/timeos_msgs:{install_path}/timeos_ros:{ament}")

        return env

    def _get_ros2_env_dict(self) -> dict:
        """Get ROS2 environment as a dictionary for subprocess.run()."""
        if self._ros2_env is None:
            return os.environ.copy()

        env_dict = os.environ.copy()
        for key in self._ros2_env.keys():
            env_dict[key] = self._ros2_env.value(key)
        return env_dict

    def _configure_process_env(self, process: QProcess) -> None:
        """Configure a QProcess with ROS2 environment."""
        if self._ros2_env is not None:
            process.setProcessEnvironment(self._ros2_env)

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
        self._configure_process_env(process)
        process.finished.connect(lambda: self._on_node_list_finished(process))
        process.start(self._ros2_path or 'ros2', ['node', 'list'])

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
        self._configure_process_env(process)
        process.finished.connect(lambda: self._on_topic_list_finished(process))
        process.start(self._ros2_path or 'ros2', ['topic', 'list', '-t'])

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
        self._configure_process_env(process)
        process.finished.connect(lambda: self._on_service_list_finished(process))
        process.start(self._ros2_path or 'ros2', ['service', 'list', '-t'])

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
        self._configure_process_env(process)
        process.readyReadStandardOutput.connect(
            lambda: self._on_topic_data(topic, process, callback)
        )
        process.finished.connect(
            lambda: self._on_echo_finished(topic, process)
        )

        # Echo with YAML output for easier parsing
        process.start(self._ros2_path or 'ros2', ['topic', 'echo', '--once', topic])
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
        self._configure_process_env(process)
        process.finished.connect(
            lambda: self._on_service_finished(service, process)
        )

        # Convert request to YAML format
        request_yaml = json.dumps(request)

        process.start(self._ros2_path or 'ros2', [
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
        self._configure_process_env(process)
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

        process.start(self._ros2_path or 'ros2', cmd_args)
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

    # =========================================================================
    # State Polling - Continuous machine state from ROS2 topics
    # =========================================================================

    def start_state_polling(self, interval_ms: int = 500) -> None:
        """Start polling state topics for machine state.

        Args:
            interval_ms: Polling interval in milliseconds.
        """
        if not self._ros2_available:
            return
        self._state_timer.start(interval_ms)
        self._poll_state_topics()  # Immediate first poll

    def stop_state_polling(self) -> None:
        """Stop polling state topics."""
        self._state_timer.stop()
        # Clean up any active poll processes
        for key, process in list(self._state_poll_processes.items()):
            process.terminate()
            process.deleteLater()
        self._state_poll_processes.clear()

    def _poll_state_topics(self) -> None:
        """Poll all state topics once."""
        if not self._ros2_available:
            return

        for key, topic in STATE_TOPICS.items():
            # Skip if already polling this topic
            if key in self._state_poll_processes:
                continue
            self._poll_single_topic(key, topic)

    def _poll_single_topic(self, key: str, topic: str) -> None:
        """Poll a single topic for state."""
        process = QProcess(self)
        self._configure_process_env(process)
        process.finished.connect(
            lambda code, status, k=key, p=process: self._on_state_poll_finished(k, p)
        )

        process.start(self._ros2_path or 'ros2', ['topic', 'echo', '--once', topic])
        self._state_poll_processes[key] = process

    def _on_state_poll_finished(self, key: str, process: QProcess) -> None:
        """Handle state poll completion."""
        if key in self._state_poll_processes:
            del self._state_poll_processes[key]

        if process.exitCode() != 0:
            process.deleteLater()
            return

        output = process.readAllStandardOutput().data().decode('utf-8')
        process.deleteLater()

        # Parse YAML output to dict
        state = self._parse_yaml_output(output)
        if state:
            old_state = self._state_cache.get(key, {})
            self._state_cache[key] = state

            # Emit specific signal if state changed
            if state != old_state:
                if key == 'field':
                    self.field_state_updated.emit(state)
                elif key == 'thermal':
                    self.thermal_state_updated.emit(state)
                elif key == 'safety':
                    self.safety_state_updated.emit(state)

                # Always emit combined state update
                self.state_updated.emit(self.get_machine_state())

    def _parse_yaml_output(self, output: str) -> Dict[str, Any]:
        """Parse ROS2 echo YAML output to dictionary.

        Args:
            output: YAML formatted output from ros2 topic echo.

        Returns:
            Parsed dictionary.
        """
        try:
            import yaml
            # ROS2 echo outputs YAML with --- separators
            # Take the first document
            docs = output.split('---')
            if docs:
                doc = docs[0].strip()
                if doc:
                    return yaml.safe_load(doc) or {}
        except Exception:
            pass
        return {}

    @property
    def field_state(self) -> Dict[str, Any]:
        """Current field generator state from cache."""
        return self._state_cache.get('field', {})

    @property
    def thermal_state(self) -> Dict[str, Any]:
        """Current thermal state from cache."""
        return self._state_cache.get('thermal', {})

    @property
    def safety_state(self) -> Dict[str, Any]:
        """Current safety state from cache."""
        return self._state_cache.get('safety', {})

    @property
    def tdu_state(self) -> Dict[str, Any]:
        """Current TDU state from cache."""
        return self._state_cache.get('tdu', {})

    def get_machine_state(self) -> Dict[str, Any]:
        """Get combined machine state matching MachineModel.get_state() format.

        Returns:
            Dictionary with all machine state.
        """
        field = self._state_cache.get('field', {})
        thermal = self._state_cache.get('thermal', {})
        safety = self._state_cache.get('safety', {})
        tdu = self._state_cache.get('tdu', {})

        # Map ROS2 states to expected format
        return {
            # Module statuses
            "tdu_status": self._map_status(tdu.get('state', 'offline')),
            "field_status": "active" if field.get('active') else "standby",
            "causality_status": "active",
            "safety_status": "active" if safety.get('all_interlocks_ok') else "warning",
            "anchor_status": "active",

            # Position
            "current_time": 0.0,
            "frame": "origin",
            "uncertainty": 0.0,

            # Field
            "field_active": field.get('active', False),
            "field_strength": field.get('field_strength', 0.0),
            "field_symmetry": 0.0,
            "power_consumption": field.get('power_watts', 0.0),

            # Thermal
            "temperature_kelvin": thermal.get('temperature_kelvin', 4.2),
            "quench_risk": thermal.get('quench_risk', 0.0),

            # Causality
            "causality": "NOMINAL" if safety.get('all_interlocks_ok') else "WARNING",
            "paradox_risk": thermal.get('quench_risk', 0.0),
            "causal_violations": safety.get('active_faults', []),

            # Anchor
            "anchor_connected": True,
            "anchor_time": 0.0,
            "anchor_strength": 1.0,

            # Overall
            "initialized": self._ros2_available and bool(field),
            "is_displacing": tdu.get('state') == 'displacing',

            # Relativistic quantities (would come from physics node)
            "velocity_beta": 0.0,
            "lorentz_gamma": 1.0,
            "proper_time": 0.0,

            # Emulated-specific
            "machine_state": tdu.get('state', 'unknown'),
            "ramp_state": self._map_ramp_state(field.get('ramp_state', 0)),
        }

    def _map_status(self, state: str) -> str:
        """Map ROS2 state string to status."""
        mapping = {
            'idle': 'standby',
            'displacing': 'active',
            'offline': 'offline',
            'fault': 'error',
        }
        return mapping.get(state, 'unknown')

    def _map_ramp_state(self, state: int) -> str:
        """Map ramp state integer to string."""
        mapping = {
            0: 'idle',
            1: 'ramp_up',
            2: 'ramp_down',
            3: 'holding',
            4: 'quenching',
        }
        return mapping.get(state, 'unknown')

    def shutdown(self) -> None:
        """Clean shutdown of all processes."""
        self._refresh_timer.stop()
        self._state_timer.stop()

        # Stop state polling
        self.stop_state_polling()

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
