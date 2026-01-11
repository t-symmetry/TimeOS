"""TimeOS GUI Dialogs.

Modal dialogs for user interaction.
"""

from timeos.gui.dialogs.displacement import DisplacementDialog
from timeos.gui.dialogs.event_details import EventDetailsDialog
from timeos.gui.dialogs.hil_config_dialog import HILConfigDialog
from timeos.gui.dialogs.failure_injection_dialog import FailureInjectionDialog
from timeos.gui.dialogs.correlation_dialog import CorrelationDialog
from timeos.gui.dialogs.mode_selector import ModeSelector

__all__ = [
    "DisplacementDialog",
    "EventDetailsDialog",
    "HILConfigDialog",
    "FailureInjectionDialog",
    "CorrelationDialog",
    "ModeSelector",
]
