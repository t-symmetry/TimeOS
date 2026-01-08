"""TimeOS GUI - Mission Control Interface.

A desktop application for monitoring and controlling temporal operations.
Clean engineering aesthetic with real-time data from simulated hardware.

Usage:
    timeos gui        # Launch GUI
    timeos gui --demo # Launch with demo data
"""

from timeos.gui.app import launch

__all__ = ["launch"]
