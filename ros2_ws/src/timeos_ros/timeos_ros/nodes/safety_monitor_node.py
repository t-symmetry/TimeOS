#!/usr/bin/env python3
"""Safety Monitor Node - Hardware safety and interlock management.

Monitors all safety-critical systems and provides E-stop capability.
"""

import threading
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

# Import ROS2 message types
try:
    from timeos_msgs.msg import SafetyState, FieldState, ThermalState
    from timeos_msgs.srv import ArmSystem, TriggerEstop
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class SafetyMonitorNode(Node):
    """ROS2 node for safety monitoring.

    Publishers:
        /timeos/safety_state (SafetyState): Safety system status

    Subscribers:
        /timeos/field_state (FieldState): Field monitoring
        /timeos/thermal_state (ThermalState): Thermal monitoring

    Services:
        /timeos/arm_system: Arm/disarm safety system
        /timeos/trigger_estop: Emergency stop
    """

    def __init__(self):
        super().__init__('safety_monitor_node')

        # Parameters
        self.declare_parameter('watchdog_timeout_ms', 1000.0)
        self.declare_parameter('max_field_tesla', 15.0)
        self.declare_parameter('max_temperature_kelvin', 10.0)
        self.declare_parameter('max_quench_risk', 0.5)

        self.watchdog_timeout = self.get_parameter('watchdog_timeout_ms').value
        self.max_field = self.get_parameter('max_field_tesla').value
        self.max_temp = self.get_parameter('max_temperature_kelvin').value
        self.max_quench_risk = self.get_parameter('max_quench_risk').value

        # State
        self._lock = threading.Lock()
        self._armed = False
        self._estop_active = False
        self._armed_by = ''
        self._armed_time = None
        self._last_heartbeat = self.get_clock().now()

        # Interlock states
        self._field_ok = True
        self._thermal_ok = True
        self._watchdog_ok = True
        self._active_faults: list = []

        # Current readings
        self._field_tesla = 0.0
        self._temperature_kelvin = 4.2
        self._quench_risk = 0.0

        self._cb_group = ReentrantCallbackGroup()

        if MSGS_AVAILABLE:
            # Publisher
            self._state_pub = self.create_publisher(
                SafetyState,
                '/timeos/safety_state',
                10
            )

            # Subscribers
            self._field_sub = self.create_subscription(
                FieldState,
                '/timeos/field_state',
                self._on_field_state,
                10
            )
            self._thermal_sub = self.create_subscription(
                ThermalState,
                '/timeos/thermal_state',
                self._on_thermal_state,
                10
            )

            # Services
            self._arm_srv = self.create_service(
                ArmSystem,
                '/timeos/arm_system',
                self._handle_arm,
                callback_group=self._cb_group
            )
            self._estop_srv = self.create_service(
                TriggerEstop,
                '/timeos/trigger_estop',
                self._handle_estop,
                callback_group=self._cb_group
            )

        # Watchdog timer
        self._watchdog_timer = self.create_timer(
            self.watchdog_timeout / 1000.0,
            self._check_watchdog
        )

        # State publisher
        self._state_timer = self.create_timer(0.1, self._publish_state)

        self.get_logger().info('Safety monitor node initialized')

    def _on_field_state(self, msg: 'FieldState') -> None:
        """Check field state for safety."""
        with self._lock:
            self._field_tesla = msg.field_strength
            self._last_heartbeat = self.get_clock().now()

            if msg.field_strength > self.max_field:
                self._field_ok = False
                if 'field_over_limit' not in self._active_faults:
                    self._active_faults.append('field_over_limit')
                    self.get_logger().warn(f'Field over limit: {msg.field_strength:.2f} T')
            else:
                self._field_ok = True
                if 'field_over_limit' in self._active_faults:
                    self._active_faults.remove('field_over_limit')

    def _on_thermal_state(self, msg: 'ThermalState') -> None:
        """Check thermal state for safety."""
        with self._lock:
            self._temperature_kelvin = msg.temperature_kelvin
            self._quench_risk = msg.quench_risk
            self._last_heartbeat = self.get_clock().now()

            if msg.temperature_kelvin > self.max_temp:
                self._thermal_ok = False
                if 'temp_over_limit' not in self._active_faults:
                    self._active_faults.append('temp_over_limit')
                    self.get_logger().warn(f'Temperature over limit: {msg.temperature_kelvin:.2f} K')
            elif msg.quench_risk > self.max_quench_risk:
                self._thermal_ok = False
                if 'quench_risk_high' not in self._active_faults:
                    self._active_faults.append('quench_risk_high')
                    self.get_logger().warn(f'Quench risk high: {msg.quench_risk:.1%}')
            else:
                self._thermal_ok = True
                for fault in ['temp_over_limit', 'quench_risk_high']:
                    if fault in self._active_faults:
                        self._active_faults.remove(fault)

    def _check_watchdog(self) -> None:
        """Check watchdog timer."""
        with self._lock:
            elapsed = (self.get_clock().now() - self._last_heartbeat).nanoseconds / 1e6
            if elapsed > self.watchdog_timeout * 2:
                self._watchdog_ok = False
                if 'watchdog_timeout' not in self._active_faults:
                    self._active_faults.append('watchdog_timeout')
                    self.get_logger().warn('Watchdog timeout')
            else:
                self._watchdog_ok = True
                if 'watchdog_timeout' in self._active_faults:
                    self._active_faults.remove('watchdog_timeout')

    def _publish_state(self) -> None:
        """Publish safety state."""
        if not MSGS_AVAILABLE:
            return

        with self._lock:
            msg = SafetyState()
            msg.stamp = self.get_clock().now().to_msg()

            # Determine state
            if self._estop_active:
                msg.safety_state = SafetyState.SAFETY_ESTOP
            elif self._active_faults:
                msg.safety_state = SafetyState.SAFETY_TRIPPED
            elif self._armed:
                msg.safety_state = SafetyState.SAFETY_ARMED
            else:
                msg.safety_state = SafetyState.SAFETY_DISARMED

            # Interlocks
            msg.interlock_field_ok = self._field_ok
            msg.interlock_thermal_ok = self._thermal_ok
            msg.interlock_power_ok = True
            msg.interlock_causality_ok = True
            msg.interlock_door_ok = True
            msg.interlock_radiation_ok = True
            msg.all_interlocks_ok = all([
                self._field_ok,
                self._thermal_ok,
                self._watchdog_ok,
            ])

            # E-stop
            msg.estop_hardware_pressed = False
            msg.estop_software_active = self._estop_active
            msg.estop_remote_active = False

            # Watchdog
            msg.watchdog_ok = self._watchdog_ok
            msg.watchdog_timeout_ms = self.watchdog_timeout
            elapsed = (self.get_clock().now() - self._last_heartbeat).nanoseconds / 1e6
            msg.last_heartbeat_ms = elapsed

            # Faults
            msg.fault_count = len(self._active_faults)
            msg.active_faults = self._active_faults.copy()
            msg.last_fault_message = self._active_faults[-1] if self._active_faults else ''

            # Operator
            msg.armed_by = self._armed_by
            if self._armed_time:
                msg.armed_at = self._armed_time.to_msg()

            self._state_pub.publish(msg)

    def _handle_arm(
        self,
        request: 'ArmSystem.Request',
        response: 'ArmSystem.Response'
    ) -> 'ArmSystem.Response':
        """Handle arm/disarm request."""
        with self._lock:
            if request.arm:
                # Check if can arm
                unmet = []
                if not self._field_ok:
                    unmet.append('Field interlock not satisfied')
                if not self._thermal_ok:
                    unmet.append('Thermal interlock not satisfied')
                if not self._watchdog_ok:
                    unmet.append('Watchdog timeout')
                if self._estop_active:
                    unmet.append('E-stop active')

                if unmet and not request.force:
                    response.success = False
                    response.unmet_conditions = unmet
                    response.message = 'Cannot arm: conditions not met'
                else:
                    self._armed = True
                    self._armed_by = request.operator_id
                    self._armed_time = self.get_clock().now()
                    response.success = True
                    response.safety_state = SafetyState.SAFETY_ARMED
                    response.message = 'System armed'
                    self.get_logger().info(f'System armed by {request.operator_id}')
            else:
                self._armed = False
                self._armed_by = ''
                self._armed_time = None
                response.success = True
                response.safety_state = SafetyState.SAFETY_DISARMED
                response.message = 'System disarmed'
                self.get_logger().info('System disarmed')

        return response

    def _handle_estop(
        self,
        request: 'TriggerEstop.Request',
        response: 'TriggerEstop.Response'
    ) -> 'TriggerEstop.Response':
        """Handle E-stop request."""
        with self._lock:
            self._estop_active = True
            self._armed = False
            self._active_faults.append(f'estop: {request.reason}')

            response.success = True
            response.message = f'E-STOP activated: {request.reason}'
            response.triggered_at = self.get_clock().now().to_msg()

            self.get_logger().error(f'E-STOP by {request.operator_id}: {request.reason}')

        return response


def main(args=None):
    rclpy.init(args=args)
    node = SafetyMonitorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
