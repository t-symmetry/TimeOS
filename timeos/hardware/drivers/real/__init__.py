"""Real hardware drivers for TimeOS.

This module provides drivers for actual hardware interfaces:
- NI DAQ (National Instruments Data Acquisition)
- LabVIEW TCP/IP bridge
- Custom sensor interfaces
- Real-time data logging

These drivers implement the same interfaces as the emulated drivers,
allowing seamless switching between simulation and real hardware.
"""

from timeos.hardware.drivers.real.base import (
    RealHardwareDriver,
    HardwareConnection,
    ConnectionState,
    HardwareError,
    ConnectionError,
    TimeoutError,
)

from timeos.hardware.drivers.real.ni_daq import (
    NIDAQDriver,
    NIDAQChannel,
    NIDAQTask,
    AnalogInput,
    AnalogOutput,
    DigitalIO,
)

from timeos.hardware.drivers.real.labview_bridge import (
    LabVIEWBridge,
    LabVIEWCommand,
    LabVIEWResponse,
)

from timeos.hardware.drivers.real.data_logger import (
    DataLogger,
    LogChannel,
    LogSession,
)

from timeos.hardware.drivers.real.hil_manager import (
    HILManager,
    HILConfig,
    ModuleType,
)

__all__ = [
    # Base
    "RealHardwareDriver",
    "HardwareConnection",
    "ConnectionState",
    "HardwareError",
    "ConnectionError",
    "TimeoutError",
    # NI DAQ
    "NIDAQDriver",
    "NIDAQChannel",
    "NIDAQTask",
    "AnalogInput",
    "AnalogOutput",
    "DigitalIO",
    # LabVIEW
    "LabVIEWBridge",
    "LabVIEWCommand",
    "LabVIEWResponse",
    # Data Logger
    "DataLogger",
    "LogChannel",
    "LogSession",
    # HIL Manager
    "HILManager",
    "HILConfig",
    "ModuleType",
]
