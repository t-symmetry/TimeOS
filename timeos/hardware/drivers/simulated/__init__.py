"""Simulated hardware drivers for TimeOS.

These implementations provide software simulation of all hardware
modules, enabling development and testing without physical hardware.

The simulated drivers:
- Follow the same interfaces as real hardware
- Provide realistic behavior for testing
- Include configurable parameters for different scenarios
- Log all operations for debugging

Usage:
    from timeos.hardware.drivers.simulated import SimulatedTimeMachine

    machine = SimulatedTimeMachine()
    machine.initialize()
    # Use like real hardware
"""

from timeos.hardware.drivers.simulated.time_machine import SimulatedTimeMachine

__all__ = ["SimulatedTimeMachine"]
