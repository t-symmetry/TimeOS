"""National Instruments DAQ driver interface.

Provides a Python interface to NI-DAQmx hardware for:
- Analog input (voltage, current, temperature)
- Analog output (control signals)
- Digital I/O (interlocks, status)
- Counter/timer operations

Requires: nidaqmx package (pip install nidaqmx)
Hardware: NI USB-6001, USB-6008, USB-6009, PCI/PCIe-6xxx, etc.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

from timeos.hardware.drivers.real.base import (
    RealHardwareDriver,
    HardwareConnection,
    HardwareError,
    ConfigurationError,
)

logger = logging.getLogger(__name__)

# Try to import nidaqmx
try:
    import nidaqmx
    from nidaqmx.constants import (
        AcquisitionType,
        TerminalConfiguration,
        Edge,
        LineGrouping,
    )
    NIDAQMX_AVAILABLE = True
except ImportError:
    NIDAQMX_AVAILABLE = False
    nidaqmx = None
    logger.warning("nidaqmx not available - NI DAQ will run in simulation mode")


class ChannelType(Enum):
    """DAQ channel types."""
    ANALOG_INPUT = auto()
    ANALOG_OUTPUT = auto()
    DIGITAL_INPUT = auto()
    DIGITAL_OUTPUT = auto()
    COUNTER_INPUT = auto()
    COUNTER_OUTPUT = auto()


@dataclass
class NIDAQChannel:
    """Configuration for a single DAQ channel.

    Attributes:
        name: Logical name for the channel
        physical_channel: NI channel path (e.g., "Dev1/ai0")
        channel_type: Type of channel
        min_value: Minimum expected value
        max_value: Maximum expected value
        units: Engineering units
        scale_factor: Multiply raw value by this
        offset: Add to scaled value
    """
    name: str
    physical_channel: str
    channel_type: ChannelType
    min_value: float = -10.0
    max_value: float = 10.0
    units: str = "V"
    scale_factor: float = 1.0
    offset: float = 0.0

    # Runtime
    last_value: float = 0.0
    last_read_time: float = 0.0


@dataclass
class NIDAQTask:
    """Configuration for a DAQ task (group of channels).

    Attributes:
        name: Task name
        channels: List of channels in this task
        sample_rate: Samples per second
        samples_per_channel: Number of samples to acquire
        continuous: Whether to run continuously
    """
    name: str
    channels: list[NIDAQChannel] = field(default_factory=list)
    sample_rate: float = 1000.0
    samples_per_channel: int = 100
    continuous: bool = False

    # Runtime
    _task: Any = None  # nidaqmx.Task


@dataclass
class AnalogInput:
    """Analog input reading."""
    channel: str
    value: float
    timestamp: float
    units: str = "V"


@dataclass
class AnalogOutput:
    """Analog output setting."""
    channel: str
    value: float
    units: str = "V"


@dataclass
class DigitalIO:
    """Digital I/O state."""
    channel: str
    value: bool
    is_input: bool


@dataclass
class NIDAQState:
    """Complete DAQ state."""
    analog_inputs: dict[str, float] = field(default_factory=dict)
    analog_outputs: dict[str, float] = field(default_factory=dict)
    digital_inputs: dict[str, bool] = field(default_factory=dict)
    digital_outputs: dict[str, bool] = field(default_factory=dict)
    timestamp: float = 0.0


class NIDAQDriver(RealHardwareDriver[NIDAQState]):
    """Driver for National Instruments DAQ devices.

    Supports:
    - Multiple analog input channels
    - Multiple analog output channels
    - Digital I/O
    - Continuous and finite acquisition
    - Hardware timing

    Example usage:
        # Configure channels
        ai0 = NIDAQChannel(
            name="field_sensor",
            physical_channel="Dev1/ai0",
            channel_type=ChannelType.ANALOG_INPUT,
            min_value=-10.0,
            max_value=10.0,
            scale_factor=1.0,  # 1 V = 1 T
            units="T",
        )

        # Create driver
        connection = HardwareConnection(
            device_id="Dev1",
            connection_string="Dev1",
        )
        driver = NIDAQDriver(connection, channels=[ai0])

        # Connect and read
        driver.connect()
        state = driver.read()
        print(f"Field: {state.analog_inputs['field_sensor']} T")
    """

    def __init__(
        self,
        connection: HardwareConnection,
        channels: list[NIDAQChannel] | None = None,
        sample_rate: float = 1000.0,
        simulation_mode: bool = False,
    ):
        """Initialize NI DAQ driver.

        Args:
            connection: Hardware connection config
            channels: List of channel configurations
            sample_rate: Default sample rate in Hz
            simulation_mode: Force simulation mode even if hardware available
        """
        super().__init__(connection)

        self._channels = channels or []
        self._sample_rate = sample_rate
        self._simulation_mode = simulation_mode or not NIDAQMX_AVAILABLE

        # Tasks (grouped by type)
        self._ai_task: Any = None
        self._ao_task: Any = None
        self._di_task: Any = None
        self._do_task: Any = None

        # Current state
        self._state = NIDAQState()

        # Simulation state
        self._sim_values: dict[str, float] = {}

        if self._simulation_mode:
            logger.info("NI DAQ running in simulation mode")

    def add_channel(self, channel: NIDAQChannel) -> None:
        """Add a channel configuration.

        Args:
            channel: Channel to add
        """
        self._channels.append(channel)

    def get_channel(self, name: str) -> NIDAQChannel | None:
        """Get channel by name.

        Args:
            name: Channel name

        Returns:
            Channel or None if not found
        """
        for ch in self._channels:
            if ch.name == name:
                return ch
        return None

    # =========================================================================
    # RealHardwareDriver Implementation
    # =========================================================================

    def _do_connect(self) -> bool:
        """Connect to NI DAQ hardware."""
        if self._simulation_mode:
            logger.info("NI DAQ simulation mode - no hardware connection")
            return True

        try:
            # Verify device exists
            system = nidaqmx.system.System.local()
            device_names = [d.name for d in system.devices]

            if self._connection.device_id not in device_names:
                raise ConfigurationError(
                    f"Device {self._connection.device_id} not found. "
                    f"Available: {device_names}"
                )

            # Create tasks for each channel type
            self._create_tasks()

            logger.info(f"Connected to NI DAQ {self._connection.device_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to NI DAQ: {e}")
            raise

    def _do_disconnect(self) -> None:
        """Disconnect from NI DAQ hardware."""
        self._cleanup_tasks()

    def _do_read(self) -> NIDAQState:
        """Read all channels."""
        self._state.timestamp = time.time()

        if self._simulation_mode:
            return self._read_simulated()

        # Read analog inputs
        if self._ai_task:
            try:
                values = self._ai_task.read()
                if isinstance(values, float):
                    values = [values]

                ai_channels = [
                    ch for ch in self._channels
                    if ch.channel_type == ChannelType.ANALOG_INPUT
                ]
                for ch, val in zip(ai_channels, values):
                    scaled = val * ch.scale_factor + ch.offset
                    self._state.analog_inputs[ch.name] = scaled
                    ch.last_value = scaled
                    ch.last_read_time = time.time()

            except Exception as e:
                logger.error(f"AI read error: {e}")

        # Read digital inputs
        if self._di_task:
            try:
                values = self._di_task.read()
                if isinstance(values, bool):
                    values = [values]

                di_channels = [
                    ch for ch in self._channels
                    if ch.channel_type == ChannelType.DIGITAL_INPUT
                ]
                for ch, val in zip(di_channels, values):
                    self._state.digital_inputs[ch.name] = val

            except Exception as e:
                logger.error(f"DI read error: {e}")

        return self._state

    def _do_write(self, command: Any) -> bool:
        """Write to output channels.

        Args:
            command: AnalogOutput, DigitalIO, or dict of outputs
        """
        if isinstance(command, AnalogOutput):
            return self._write_analog(command)
        elif isinstance(command, DigitalIO):
            return self._write_digital(command)
        elif isinstance(command, dict):
            success = True
            for name, value in command.items():
                ch = self.get_channel(name)
                if ch:
                    if ch.channel_type == ChannelType.ANALOG_OUTPUT:
                        success &= self._write_analog(
                            AnalogOutput(name, value, ch.units)
                        )
                    elif ch.channel_type == ChannelType.DIGITAL_OUTPUT:
                        success &= self._write_digital(
                            DigitalIO(name, bool(value), False)
                        )
            return success
        else:
            logger.error(f"Unknown command type: {type(command)}")
            return False

    def _validate_connection(self) -> bool:
        """Validate DAQ connection is alive."""
        if self._simulation_mode:
            return True

        try:
            # Simple check - try to read device name
            if self._ai_task:
                _ = self._ai_task.name
            return True
        except Exception:
            return False

    # =========================================================================
    # Analog I/O
    # =========================================================================

    def _write_analog(self, output: AnalogOutput) -> bool:
        """Write analog output.

        Args:
            output: Output configuration
        """
        ch = self.get_channel(output.channel)
        if not ch:
            logger.error(f"Unknown channel: {output.channel}")
            return False

        # Apply inverse scaling
        raw_value = (output.value - ch.offset) / ch.scale_factor

        if self._simulation_mode:
            self._sim_values[output.channel] = raw_value
            self._state.analog_outputs[output.channel] = output.value
            return True

        if not self._ao_task:
            logger.error("No analog output task configured")
            return False

        try:
            # Find channel index in task
            ao_channels = [
                c for c in self._channels
                if c.channel_type == ChannelType.ANALOG_OUTPUT
            ]
            idx = next(
                i for i, c in enumerate(ao_channels)
                if c.name == output.channel
            )

            # Write single channel (simplified)
            self._ao_task.write(raw_value)
            self._state.analog_outputs[output.channel] = output.value
            return True

        except Exception as e:
            logger.error(f"Analog write error: {e}")
            return False

    def read_analog(self, channel_name: str) -> float | None:
        """Read a single analog channel.

        Args:
            channel_name: Channel to read

        Returns:
            Scaled value or None on error
        """
        state = self.read()
        if state:
            return state.analog_inputs.get(channel_name)
        return None

    # =========================================================================
    # Digital I/O
    # =========================================================================

    def _write_digital(self, output: DigitalIO) -> bool:
        """Write digital output.

        Args:
            output: Output configuration
        """
        if self._simulation_mode:
            self._state.digital_outputs[output.channel] = output.value
            return True

        if not self._do_task:
            logger.error("No digital output task configured")
            return False

        try:
            self._do_task.write(output.value)
            self._state.digital_outputs[output.channel] = output.value
            return True

        except Exception as e:
            logger.error(f"Digital write error: {e}")
            return False

    def read_digital(self, channel_name: str) -> bool | None:
        """Read a single digital channel.

        Args:
            channel_name: Channel to read

        Returns:
            Digital value or None on error
        """
        state = self.read()
        if state:
            return state.digital_inputs.get(channel_name)
        return None

    # =========================================================================
    # Task Management
    # =========================================================================

    def _create_tasks(self) -> None:
        """Create NI-DAQmx tasks for configured channels."""
        # Group channels by type
        ai_channels = [
            ch for ch in self._channels
            if ch.channel_type == ChannelType.ANALOG_INPUT
        ]
        ao_channels = [
            ch for ch in self._channels
            if ch.channel_type == ChannelType.ANALOG_OUTPUT
        ]
        di_channels = [
            ch for ch in self._channels
            if ch.channel_type == ChannelType.DIGITAL_INPUT
        ]
        do_channels = [
            ch for ch in self._channels
            if ch.channel_type == ChannelType.DIGITAL_OUTPUT
        ]

        # Create analog input task
        if ai_channels:
            self._ai_task = nidaqmx.Task("TimeOS_AI")
            for ch in ai_channels:
                self._ai_task.ai_channels.add_ai_voltage_chan(
                    ch.physical_channel,
                    name_to_assign_to_channel=ch.name,
                    min_val=ch.min_value,
                    max_val=ch.max_value,
                )
            logger.info(f"Created AI task with {len(ai_channels)} channels")

        # Create analog output task
        if ao_channels:
            self._ao_task = nidaqmx.Task("TimeOS_AO")
            for ch in ao_channels:
                self._ao_task.ao_channels.add_ao_voltage_chan(
                    ch.physical_channel,
                    name_to_assign_to_channel=ch.name,
                    min_val=ch.min_value,
                    max_val=ch.max_value,
                )
            logger.info(f"Created AO task with {len(ao_channels)} channels")

        # Create digital input task
        if di_channels:
            self._di_task = nidaqmx.Task("TimeOS_DI")
            for ch in di_channels:
                self._di_task.di_channels.add_di_chan(
                    ch.physical_channel,
                    name_to_assign_to_channel=ch.name,
                )
            logger.info(f"Created DI task with {len(di_channels)} channels")

        # Create digital output task
        if do_channels:
            self._do_task = nidaqmx.Task("TimeOS_DO")
            for ch in do_channels:
                self._do_task.do_channels.add_do_chan(
                    ch.physical_channel,
                    name_to_assign_to_channel=ch.name,
                )
            logger.info(f"Created DO task with {len(do_channels)} channels")

    def _cleanup_tasks(self) -> None:
        """Clean up NI-DAQmx tasks."""
        for task in [self._ai_task, self._ao_task, self._di_task, self._do_task]:
            if task:
                try:
                    task.stop()
                    task.close()
                except Exception as e:
                    logger.error(f"Error closing task: {e}")

        self._ai_task = None
        self._ao_task = None
        self._di_task = None
        self._do_task = None

    # =========================================================================
    # Simulation
    # =========================================================================

    def _read_simulated(self) -> NIDAQState:
        """Generate simulated readings."""
        import math
        import random

        t = time.time()

        for ch in self._channels:
            if ch.channel_type == ChannelType.ANALOG_INPUT:
                # Generate realistic sensor values with noise
                base = (ch.max_value + ch.min_value) / 2
                amplitude = (ch.max_value - ch.min_value) / 4
                noise = random.gauss(0, amplitude * 0.01)

                value = base + amplitude * math.sin(t * 0.1) + noise
                scaled = value * ch.scale_factor + ch.offset
                self._state.analog_inputs[ch.name] = scaled

            elif ch.channel_type == ChannelType.DIGITAL_INPUT:
                # Simulate interlock states
                self._state.digital_inputs[ch.name] = random.random() > 0.1

        return self._state

    def set_simulated_value(self, channel_name: str, value: float) -> None:
        """Set a simulated input value (for testing).

        Args:
            channel_name: Channel to set
            value: Value to simulate
        """
        if not self._simulation_mode:
            logger.warning("set_simulated_value only works in simulation mode")
            return

        ch = self.get_channel(channel_name)
        if ch and ch.channel_type == ChannelType.ANALOG_INPUT:
            self._state.analog_inputs[channel_name] = value
        elif ch and ch.channel_type == ChannelType.DIGITAL_INPUT:
            self._state.digital_inputs[channel_name] = bool(value)
