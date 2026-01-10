#!/usr/bin/env python3
"""T-Symmetry Analyzer Node - Performs T-symmetry measurements and analysis.

This is the core research node for micro T-symmetry experiments.
It coordinates field reversals, sensor measurements, and statistical analysis
to detect potential T-symmetry violations.
"""

import numpy as np
from collections import deque
from dataclasses import dataclass
from typing import Optional, List
import threading
import json

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

# Import ROS2 message types
try:
    from timeos_msgs.msg import (
        SensorReading,
        FieldState,
        MeasurementResult,
        ExperimentConfig,
    )
    from timeos_msgs.srv import GetMeasurement, StartExperiment, StopExperiment
    from timeos_msgs.action import RunExperiment
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


@dataclass
class TSample:
    """A single T-symmetry measurement sample."""
    timestamp: float
    field_direction: int  # +1 forward, -1 backward
    sensor_values: dict
    field_strength: float
    temperature: float


@dataclass
class TSymmetryResult:
    """Result of T-symmetry analysis."""
    t_score: float          # -1 to +1 (0 = symmetric)
    uncertainty: float
    forward_mean: float
    backward_mean: float
    asymmetry: float
    significance_sigma: float
    sample_count: int
    p_value: float
    is_significant: bool
    conclusion: str


class TSymmetryAnalyzerNode(Node):
    """ROS2 node for T-symmetry analysis.

    This node:
    1. Subscribes to sensor data and field state
    2. Coordinates forward/backward measurement phases
    3. Performs statistical analysis on collected data
    4. Publishes measurement results

    Publishers:
        /timeos/t_symmetry/result (MeasurementResult): Analysis results
        /timeos/t_symmetry/status (String): Current analysis status

    Subscribers:
        /timeos/sensors/+ (SensorReading): Sensor data
        /timeos/field_state (FieldState): Field state

    Services:
        /timeos/t_symmetry/get_measurement: Get measurement results

    Actions:
        /timeos/t_symmetry/run_experiment: Run full T-symmetry experiment
    """

    def __init__(self):
        super().__init__('t_symmetry_analyzer_node')

        # Parameters
        self.declare_parameter('sample_window_sec', 10.0)
        self.declare_parameter('min_samples', 100)
        self.declare_parameter('significance_threshold', 3.0)  # sigma
        self.declare_parameter('sensor_topics', ['/timeos/sensors/magnetometer'])

        self.sample_window = self.get_parameter('sample_window_sec').value
        self.min_samples = self.get_parameter('min_samples').value
        self.significance_threshold = self.get_parameter('significance_threshold').value
        self.sensor_topics = self.get_parameter('sensor_topics').value

        # State
        self._lock = threading.Lock()
        self._forward_samples: deque = deque(maxlen=10000)
        self._backward_samples: deque = deque(maxlen=10000)
        self._current_field_direction = 1  # +1 or -1
        self._current_field_strength = 0.0
        self._current_temperature = 4.2
        self._experiment_running = False
        self._experiment_id: Optional[str] = None
        self._results: List[TSymmetryResult] = []

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        if MSGS_AVAILABLE:
            # Publisher
            self._result_pub = self.create_publisher(
                MeasurementResult,
                '/timeos/t_symmetry/result',
                10
            )

            # Subscribers
            self._field_sub = self.create_subscription(
                FieldState,
                '/timeos/field_state',
                self._on_field_state,
                10
            )

            # Dynamic sensor subscriptions
            self._sensor_subs = []
            for topic in self.sensor_topics:
                sub = self.create_subscription(
                    SensorReading,
                    topic,
                    self._on_sensor_reading,
                    10
                )
                self._sensor_subs.append(sub)

            # Services
            self._get_measurement_srv = self.create_service(
                GetMeasurement,
                '/timeos/t_symmetry/get_measurement',
                self._handle_get_measurement,
                callback_group=self._cb_group
            )

            # Action server
            self._experiment_action = ActionServer(
                self,
                RunExperiment,
                '/timeos/t_symmetry/run_experiment',
                self._execute_experiment,
                callback_group=self._cb_group
            )

        # Analysis timer
        self._analysis_timer = self.create_timer(
            1.0,  # Analyze every second
            self._run_analysis
        )

        self.get_logger().info('T-symmetry analyzer node initialized')

    def _on_field_state(self, msg: 'FieldState') -> None:
        """Handle field state update."""
        with self._lock:
            self._current_field_strength = msg.field_strength
            # Determine field direction from Bz sign
            self._current_field_direction = 1 if msg.bz >= 0 else -1

    def _on_sensor_reading(self, msg: 'SensorReading') -> None:
        """Handle incoming sensor reading."""
        if not self._experiment_running:
            return

        with self._lock:
            sample = TSample(
                timestamp=msg.stamp.sec + msg.stamp.nanosec * 1e-9,
                field_direction=self._current_field_direction,
                sensor_values={msg.sensor_id: msg.value},
                field_strength=self._current_field_strength,
                temperature=self._current_temperature,
            )

            if self._current_field_direction > 0:
                self._forward_samples.append(sample)
            else:
                self._backward_samples.append(sample)

    def _run_analysis(self) -> None:
        """Periodically analyze collected samples."""
        if not self._experiment_running:
            return

        with self._lock:
            if len(self._forward_samples) < self.min_samples // 2:
                return
            if len(self._backward_samples) < self.min_samples // 2:
                return

            result = self._analyze_samples(
                list(self._forward_samples),
                list(self._backward_samples)
            )

            if result:
                self._results.append(result)
                self._publish_result(result)

    def _analyze_samples(
        self,
        forward: List[TSample],
        backward: List[TSample]
    ) -> Optional[TSymmetryResult]:
        """Perform T-symmetry statistical analysis."""
        if not forward or not backward:
            return None

        try:
            # Extract sensor values
            # Assuming single sensor for simplicity
            forward_values = []
            backward_values = []

            for s in forward:
                for v in s.sensor_values.values():
                    forward_values.append(v)

            for s in backward:
                for v in s.sensor_values.values():
                    backward_values.append(v)

            if not forward_values or not backward_values:
                return None

            # Calculate statistics
            forward_mean = np.mean(forward_values)
            backward_mean = np.mean(backward_values)
            forward_std = np.std(forward_values)
            backward_std = np.std(backward_values)

            # Combined uncertainty
            n_forward = len(forward_values)
            n_backward = len(backward_values)
            combined_uncertainty = np.sqrt(
                (forward_std**2 / n_forward) + (backward_std**2 / n_backward)
            )

            # Asymmetry
            asymmetry = forward_mean - backward_mean
            asymmetry_norm = asymmetry / (abs(forward_mean) + abs(backward_mean) + 1e-10)

            # T-score: normalized to -1 to +1 range
            t_score = np.clip(asymmetry_norm, -1.0, 1.0)

            # Statistical significance
            if combined_uncertainty > 0:
                significance = abs(asymmetry) / combined_uncertainty
            else:
                significance = 0.0

            # P-value (approximate, assuming normal distribution)
            from scipy import stats
            t_stat, p_value = stats.ttest_ind(forward_values, backward_values)

            is_significant = significance >= self.significance_threshold

            # Generate conclusion
            if is_significant:
                if t_score > 0:
                    conclusion = f"Potential T-asymmetry detected (forward > backward by {significance:.1f}σ)"
                else:
                    conclusion = f"Potential T-asymmetry detected (backward > forward by {significance:.1f}σ)"
            else:
                conclusion = f"No significant T-asymmetry (Δ = {significance:.1f}σ)"

            return TSymmetryResult(
                t_score=float(t_score),
                uncertainty=float(combined_uncertainty),
                forward_mean=float(forward_mean),
                backward_mean=float(backward_mean),
                asymmetry=float(asymmetry),
                significance_sigma=float(significance),
                sample_count=n_forward + n_backward,
                p_value=float(p_value),
                is_significant=is_significant,
                conclusion=conclusion,
            )

        except Exception as e:
            self.get_logger().error(f'Analysis failed: {e}')
            return None

    def _publish_result(self, result: TSymmetryResult) -> None:
        """Publish analysis result."""
        if not MSGS_AVAILABLE:
            return

        msg = MeasurementResult()
        msg.stamp = self.get_clock().now().to_msg()
        msg.experiment_id = self._experiment_id or ''
        msg.measurement_id = f'{self._experiment_id}_{len(self._results)}'

        msg.t_symmetry_score = result.t_score
        msg.t_symmetry_uncertainty = result.uncertainty
        msg.asymmetry_magnitude = result.asymmetry
        msg.asymmetry_significance = result.significance_sigma

        msg.forward_value = result.forward_mean
        msg.forward_uncertainty = result.uncertainty
        msg.backward_value = result.backward_mean
        msg.backward_uncertainty = result.uncertainty
        msg.difference = result.asymmetry
        msg.difference_uncertainty = result.uncertainty * np.sqrt(2)

        msg.sample_count = result.sample_count
        msg.mean = (result.forward_mean + result.backward_mean) / 2
        msg.std_dev = result.uncertainty
        msg.p_value = result.p_value

        msg.measurement_valid = True
        msg.conclusion = result.conclusion
        msg.confidence = min(result.significance_sigma / 5.0, 1.0)

        msg.field_strength_tesla = self._current_field_strength
        msg.temperature_kelvin = self._current_temperature

        self._result_pub.publish(msg)
        self.get_logger().info(f'Published result: {result.conclusion}')

    def _handle_get_measurement(
        self,
        request: 'GetMeasurement.Request',
        response: 'GetMeasurement.Response'
    ) -> 'GetMeasurement.Response':
        """Handle get measurement service request."""
        with self._lock:
            if self._results:
                latest = self._results[-1]
                result_msg = MeasurementResult()
                result_msg.t_symmetry_score = latest.t_score
                result_msg.t_symmetry_uncertainty = latest.uncertainty
                result_msg.sample_count = latest.sample_count
                result_msg.conclusion = latest.conclusion
                result_msg.measurement_valid = True

                response.result = result_msg
                response.success = True
                response.message = 'Latest measurement retrieved'
            else:
                response.success = False
                response.message = 'No measurements available'

        return response

    def _execute_experiment(self, goal_handle) -> 'RunExperiment.Result':
        """Execute T-symmetry experiment action."""
        request = goal_handle.request
        config = request.config
        result = RunExperiment.Result()

        try:
            import uuid
            self._experiment_id = str(uuid.uuid4())[:8]

            with self._lock:
                self._forward_samples.clear()
                self._backward_samples.clear()
                self._results.clear()
                self._experiment_running = True

            self.get_logger().info(f'Starting T-symmetry experiment: {self._experiment_id}')

            # Run for specified duration
            duration = config.duration_seconds if config.duration_seconds > 0 else 60.0
            iterations = config.num_iterations if config.num_iterations > 0 else 1

            start_time = self.get_clock().now()

            for iteration in range(iterations):
                if goal_handle.is_cancel_requested:
                    goal_handle.canceled()
                    result.success = False
                    result.message = 'Experiment cancelled'
                    self._experiment_running = False
                    return result

                elapsed = (self.get_clock().now() - start_time).nanoseconds / 1e9
                progress = elapsed / (duration * iterations)

                # Publish feedback
                if MSGS_AVAILABLE:
                    feedback = RunExperiment.Feedback()
                    feedback.phase = 'measuring'
                    feedback.progress = min(progress, 1.0)
                    feedback.iteration = iteration + 1
                    feedback.total_iterations = iterations
                    feedback.samples_collected = len(self._forward_samples) + len(self._backward_samples)
                    feedback.elapsed_sec = elapsed
                    feedback.remaining_sec = (duration * iterations) - elapsed
                    feedback.field_tesla = self._current_field_strength
                    feedback.temperature_kelvin = self._current_temperature

                    if self._results:
                        feedback.preliminary_t_score = self._results[-1].t_score

                    feedback.status_message = f'Iteration {iteration + 1}/{iterations}'
                    goal_handle.publish_feedback(feedback)

                # Sleep for iteration
                iter_duration = duration / iterations
                rclpy.spin_once(self, timeout_sec=iter_duration)

            # Final analysis
            with self._lock:
                self._experiment_running = False

                if self._forward_samples and self._backward_samples:
                    final_result = self._analyze_samples(
                        list(self._forward_samples),
                        list(self._backward_samples)
                    )

                    if final_result:
                        self._results.append(final_result)
                        self._publish_result(final_result)

            # Build result
            goal_handle.succeed()
            result.success = True
            result.experiment_id = self._experiment_id

            if self._results:
                final = self._results[-1]
                result.t_symmetry_score = final.t_score
                result.total_samples = final.sample_count
                result.conclusion = final.conclusion
            else:
                result.conclusion = 'Insufficient data for analysis'

            result.duration_sec = (self.get_clock().now() - start_time).nanoseconds / 1e9
            result.message = f'Experiment {self._experiment_id} complete'

        except Exception as e:
            goal_handle.abort()
            result.success = False
            result.message = str(e)
            self._experiment_running = False
            self.get_logger().error(f'Experiment failed: {e}')

        return result


def main(args=None):
    rclpy.init(args=args)

    node = TSymmetryAnalyzerNode()

    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
