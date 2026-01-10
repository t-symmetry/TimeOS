#!/usr/bin/env python3
"""Field Generator Node - Controls electromagnetic field generation.

This node interfaces with real or emulated field generator hardware,
providing field control and monitoring for T-symmetry experiments.
"""

import threading
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

# Try to import timeos hardware
try:
    from timeos.hardware.drivers.emulated.field_generator import EmulatedFieldGenerator
    from timeos.hardware.drivers.emulated.interfaces import FieldType
    EMULATED_AVAILABLE = True
except ImportError:
    EMULATED_AVAILABLE = False

# Import ROS2 message types
try:
    from timeos_msgs.msg import FieldState
    from timeos_msgs.srv import SetField
    from timeos_msgs.action import RampField
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class FieldGeneratorNode(Node):
    """ROS2 node for field generator control.

    Publishers:
        /timeos/field_state (FieldState): Current field status at 10Hz

    Services:
        /timeos/set_field: Set target field strength

    Actions:
        /timeos/ramp_field: Ramp field to target (with feedback)
    """

    def __init__(self):
        super().__init__('field_generator_node')

        # Parameters
        self.declare_parameter('use_emulated', True)
        self.declare_parameter('publish_rate', 10.0)
        self.declare_parameter('max_field_tesla', 15.0)
        self.declare_parameter('max_ramp_rate', 0.1)  # T/s

        self.use_emulated = self.get_parameter('use_emulated').value
        self.publish_rate = self.get_parameter('publish_rate').value
        self.max_field = self.get_parameter('max_field_tesla').value
        self.max_ramp_rate = self.get_parameter('max_ramp_rate').value

        # Initialize hardware
        self._field_gen: Optional[EmulatedFieldGenerator] = None
        self._lock = threading.Lock()

        if EMULATED_AVAILABLE and self.use_emulated:
            try:
                self._field_gen = EmulatedFieldGenerator(
                    max_field=self.max_field,
                    ramp_rate=self.max_ramp_rate,
                )
                self._field_gen.initialize()
                self.get_logger().info('Emulated field generator initialized')
            except Exception as e:
                self.get_logger().error(f'Failed to initialize field generator: {e}')
        else:
            self.get_logger().warn('Field generator hardware not available, running in stub mode')

        # Simulated state for stub mode
        self._stub_field = 0.0
        self._stub_setpoint = 0.0
        self._stub_ramping = False

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        if MSGS_AVAILABLE:
            # Publisher
            self._state_pub = self.create_publisher(
                FieldState,
                '/timeos/field_state',
                10
            )

            # Service
            self._set_field_srv = self.create_service(
                SetField,
                '/timeos/set_field',
                self._handle_set_field,
                callback_group=self._cb_group
            )

            # Action server
            self._ramp_action = ActionServer(
                self,
                RampField,
                '/timeos/ramp_field',
                self._execute_ramp,
                callback_group=self._cb_group
            )

        # State publisher timer
        self._state_timer = self.create_timer(
            1.0 / self.publish_rate,
            self._publish_state
        )

        # Update timer for emulated hardware
        self._update_timer = self.create_timer(
            0.01,  # 100Hz update
            self._update_hardware
        )

        self.get_logger().info('Field generator node initialized')

    def _update_hardware(self) -> None:
        """Update emulated hardware state."""
        if self._field_gen:
            with self._lock:
                self._field_gen.update(0.01)

    def _get_current_state(self) -> dict:
        """Get current field state."""
        if self._field_gen:
            with self._lock:
                state = self._field_gen.get_field_state()
                return {
                    'field_strength': state.current_field,
                    'setpoint': state.target_field,
                    'ramp_state': 1 if state.ramping else (3 if state.active else 0),
                    'ramp_rate': self._field_gen._ramp_rate,
                    'power_watts': state.power_watts,
                    'active': state.active,
                    'at_setpoint': abs(state.current_field - state.target_field) < 0.001,
                    'stability': state.stability,
                }
        else:
            # Stub mode
            return {
                'field_strength': self._stub_field,
                'setpoint': self._stub_setpoint,
                'ramp_state': 1 if self._stub_ramping else 0,
                'ramp_rate': self.max_ramp_rate,
                'power_watts': self._stub_field * 1000,
                'active': self._stub_field > 0,
                'at_setpoint': abs(self._stub_field - self._stub_setpoint) < 0.001,
                'stability': 1.0,
            }

    def _publish_state(self) -> None:
        """Publish current field state."""
        if not MSGS_AVAILABLE:
            return

        state = self._get_current_state()

        msg = FieldState()
        msg.stamp = self.get_clock().now().to_msg()
        msg.field_strength = state['field_strength']
        msg.field_setpoint = state['setpoint']
        msg.field_error = state['setpoint'] - state['field_strength']
        msg.bx = 0.0
        msg.by = 0.0
        msg.bz = state['field_strength']  # Assume z-axis field
        msg.ramp_state = state['ramp_state']
        msg.ramp_rate = state['ramp_rate']
        msg.ramp_progress = 0.0  # TODO: Calculate
        msg.power_watts = state['power_watts']
        msg.current_amps = state['power_watts'] / 10.0  # Approximate
        msg.voltage_volts = 10.0
        msg.stability = state['stability']
        msg.homogeneity = 0.99
        msg.ripple_ppm = 10.0
        msg.active = state['active']
        msg.at_setpoint = state['at_setpoint']
        msg.interlock_ok = True
        msg.fault_message = ''

        self._state_pub.publish(msg)

    def _handle_set_field(
        self,
        request: 'SetField.Request',
        response: 'SetField.Response'
    ) -> 'SetField.Response':
        """Handle set field service request."""
        try:
            # Limit field to maximum
            target = min(request.field_strength_tesla, self.max_field)
            ramp_rate = request.ramp_rate_tesla_per_sec or self.max_ramp_rate

            if self._field_gen:
                with self._lock:
                    self._field_gen.set_field(target)
                response.success = True
                response.actual_setpoint = target
            else:
                # Stub mode
                self._stub_setpoint = target
                self._stub_ramping = True
                response.success = True
                response.actual_setpoint = target

            state = self._get_current_state()
            response.at_setpoint = state['at_setpoint']
            response.estimated_time_sec = abs(target - state['field_strength']) / ramp_rate
            response.message = f'Field setpoint set to {target:.3f} T'

        except Exception as e:
            response.success = False
            response.message = str(e)
            self.get_logger().error(f'Failed to set field: {e}')

        return response

    def _execute_ramp(self, goal_handle) -> 'RampField.Result':
        """Execute field ramp action."""
        request = goal_handle.request
        result = RampField.Result()

        try:
            target = min(request.target_tesla, self.max_field)
            ramp_rate = request.ramp_rate_tesla_per_sec or self.max_ramp_rate

            # Start ramp
            if self._field_gen:
                with self._lock:
                    self._field_gen.set_field(target)
            else:
                self._stub_setpoint = target
                self._stub_ramping = True

            start_field = self._get_current_state()['field_strength']
            start_time = self.get_clock().now()

            # Monitor ramp progress
            while rclpy.ok():
                state = self._get_current_state()
                current = state['field_strength']

                # Calculate progress
                total_delta = abs(target - start_field)
                current_delta = abs(current - start_field)
                progress = current_delta / total_delta if total_delta > 0 else 1.0

                # Publish feedback
                if MSGS_AVAILABLE:
                    feedback = RampField.Feedback()
                    feedback.current_field_tesla = current
                    feedback.progress = min(progress, 1.0)
                    feedback.estimated_remaining_sec = abs(target - current) / ramp_rate
                    feedback.ramp_rate_actual = ramp_rate
                    feedback.temperature_kelvin = 4.2  # TODO: Get from thermal
                    feedback.power_watts = state['power_watts']
                    feedback.quench_risk = 0.0
                    feedback.status_message = f'Ramping: {current:.3f} T -> {target:.3f} T'
                    goal_handle.publish_feedback(feedback)

                # Check if at target
                if abs(current - target) < 0.001:
                    break

                # Check for cancellation
                if goal_handle.is_cancel_requested:
                    goal_handle.canceled()
                    result.success = False
                    result.message = 'Ramp cancelled'
                    return result

                # Sleep briefly
                rclpy.spin_once(self, timeout_sec=0.1)

            # Complete
            goal_handle.succeed()
            end_time = self.get_clock().now()
            duration = (end_time - start_time).nanoseconds / 1e9

            result.success = True
            result.final_field_tesla = self._get_current_state()['field_strength']
            result.ramp_duration_sec = duration
            result.energy_used_joules = duration * state['power_watts']
            result.peak_temperature_kelvin = 4.2
            result.message = f'Ramp complete: {result.final_field_tesla:.3f} T'

        except Exception as e:
            goal_handle.abort()
            result.success = False
            result.message = str(e)
            self.get_logger().error(f'Ramp failed: {e}')

        return result


def main(args=None):
    rclpy.init(args=args)

    node = FieldGeneratorNode()

    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if node._field_gen:
            node._field_gen.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
