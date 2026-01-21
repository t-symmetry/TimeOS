"""Simultaneity Widget - Andromeda Paradox / Relativity of Simultaneity Display."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QFrame,
    QComboBox,
    QDoubleSpinBox,
)
from PySide6.QtCore import Qt

from timeos.gui.models.machine_model import MachineModel


# Target distance presets (name, distance in light-years, display string)
TARGET_PRESETS = [
    ("Moon", 1.28 / 31557600, "1.28 ls"),  # 1.28 light-seconds
    ("Mars (avg)", 12.5 * 60 / 31557600, "12.5 min"),  # 12.5 light-minutes
    ("Proxima Centauri", 4.24, "4.24 ly"),
    ("Andromeda Galaxy", 2.5e6, "2.5 Mly"),
    ("Custom...", None, None),
]


class SimultaneityWidget(QGroupBox):
    """Display simultaneity offset based on observer velocity and target distance.

    Demonstrates the Andromeda Paradox: for spacelike-separated events,
    the order of "now" depends on the observer's velocity.

    The simultaneity offset is calculated as:
        Δt = γ × β × D
    where:
        γ = Lorentz factor
        β = v/c velocity
        D = distance to target (in light-time units)
    """

    def __init__(self, model: MachineModel, parent: QWidget | None = None):
        super().__init__("SIMULTANEITY", parent)

        self._model = model
        self._custom_distance_ly = 2.5e6  # Default custom distance: Andromeda
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the display UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Target selector
        target_layout = QHBoxLayout()
        target_label = QLabel("Target:")
        target_label.setStyleSheet("color: #808080;")
        target_label.setToolTip(
            "<b>Target Distance</b><br><br>"
            "The distance to a distant object or location.<br><br>"
            "Due to the relativity of simultaneity, observers moving<br>"
            "at different velocities will disagree about what is<br>"
            "happening 'now' at distant locations.<br><br>"
            "This is the <b>Andromeda Paradox</b>: two people walking<br>"
            "past each other on Earth may disagree about 'now' on<br>"
            "Andromeda by tens of thousands of years."
        )
        target_layout.addWidget(target_label)

        self._target_combo = QComboBox()
        self._target_combo.setStyleSheet(
            "QComboBox { background-color: #2a2a2a; color: #00ff88; }"
        )
        for name, _, display in TARGET_PRESETS:
            if display:
                self._target_combo.addItem(f"{name} ({display})")
            else:
                self._target_combo.addItem(name)
        self._target_combo.setCurrentIndex(3)  # Default to Andromeda
        self._target_combo.currentIndexChanged.connect(self._on_target_changed)
        target_layout.addWidget(self._target_combo)

        layout.addLayout(target_layout)

        # Custom distance input (hidden by default)
        self._custom_layout = QHBoxLayout()
        custom_label = QLabel("Distance:")
        custom_label.setStyleSheet("color: #808080;")
        self._custom_layout.addWidget(custom_label)

        self._custom_spinbox = QDoubleSpinBox()
        self._custom_spinbox.setRange(1e-10, 1e12)
        self._custom_spinbox.setDecimals(6)
        self._custom_spinbox.setValue(self._custom_distance_ly)
        self._custom_spinbox.setSuffix(" ly")
        self._custom_spinbox.setStyleSheet(
            "QDoubleSpinBox { background-color: #2a2a2a; color: #00ff88; }"
        )
        self._custom_spinbox.valueChanged.connect(self._on_custom_distance_changed)
        self._custom_layout.addWidget(self._custom_spinbox)

        self._custom_widget = QWidget()
        self._custom_widget.setLayout(self._custom_layout)
        self._custom_widget.hide()
        layout.addWidget(self._custom_widget)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #3a3a3a;")
        layout.addWidget(sep1)

        # Main display: Temporal offset
        offset_layout = QHBoxLayout()
        offset_label = QLabel("Δt_sim =")
        offset_label.setStyleSheet("color: #808080; font-size: 12pt;")
        offset_label.setToolTip(
            "<b>Simultaneity Offset (Δt_sim)</b><br><br>"
            "The temporal offset in what is considered 'now'<br>"
            "at the target location, relative to a stationary observer.<br><br>"
            "<b>Formula:</b> Δt = γ × β × D<br><br>"
            "A positive offset means your 'now' at the target is<br>"
            "in the <i>future</i> relative to a stationary observer's 'now'.<br><br>"
            "At typical walking speeds (~5 km/h) and Andromeda's distance,<br>"
            "this offset can be ~1 day. At 0.0323c, it's ~80,000 years!"
        )
        offset_layout.addWidget(offset_label)

        self._offset_value = QLabel("+0")
        self._offset_value.setStyleSheet(
            "color: #ff88ff; font-size: 16pt; font-weight: bold; font-family: monospace;"
        )
        self._offset_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        offset_layout.addWidget(self._offset_value)

        self._offset_unit = QLabel("years")
        self._offset_unit.setStyleSheet("color: #808080; font-size: 12pt;")
        offset_layout.addWidget(self._offset_unit)

        layout.addLayout(offset_layout)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #3a3a3a;")
        layout.addWidget(sep2)

        # Status indicator
        status_layout = QHBoxLayout()
        status_label = QLabel("Status:")
        status_label.setStyleSheet("color: #808080;")
        status_label.setToolTip(
            "<b>Simultaneity Status</b><br><br>"
            "<b>CONVERGED:</b> Low offset - observers mostly agree on 'now'<br>"
            "<b>DIVERGENT:</b> Significant offset - observers disagree on 'now'<br><br>"
            "When divergent, events you consider simultaneous may be<br>"
            "in a different order for other observers."
        )
        status_layout.addWidget(status_label)

        self._status_indicator = QLabel("CONVERGED")
        self._status_indicator.setStyleSheet("color: #00ff88; font-family: monospace;")
        self._status_indicator.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_layout.addWidget(self._status_indicator)

        layout.addLayout(status_layout)

        # Separator
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("color: #3a3a3a;")
        layout.addWidget(sep3)

        # Contributing factors section
        factors_label = QLabel("FACTORS")
        factors_label.setStyleSheet("color: #5a5a5a; font-size: 8pt;")
        layout.addWidget(factors_label)

        # Beta (velocity)
        beta_layout = QHBoxLayout()
        beta_label = QLabel("β =")
        beta_label.setStyleSheet("color: #808080;")
        beta_label.setToolTip(
            "<b>Velocity Parameter (β)</b><br><br>"
            "β = v/c - velocity as fraction of light speed.<br><br>"
            "Even small velocities produce noticeable simultaneity<br>"
            "offsets at large distances."
        )
        beta_layout.addWidget(beta_label)

        self._beta_value = QLabel("0.0000")
        self._beta_value.setStyleSheet("color: #00aaff; font-family: monospace;")
        self._beta_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        beta_layout.addWidget(self._beta_value)

        beta_unit = QLabel("c")
        beta_unit.setStyleSheet("color: #808080;")
        beta_layout.addWidget(beta_unit)

        layout.addLayout(beta_layout)

        # Gamma (Lorentz factor)
        gamma_layout = QHBoxLayout()
        gamma_label = QLabel("γ =")
        gamma_label.setStyleSheet("color: #808080;")
        gamma_label.setToolTip(
            "<b>Lorentz Factor (γ)</b><br><br>"
            "γ = 1/√(1 - β²)<br><br>"
            "Contributes to the simultaneity offset calculation.<br>"
            "At low velocities, γ ≈ 1."
        )
        gamma_layout.addWidget(gamma_label)

        self._gamma_value = QLabel("1.0000")
        self._gamma_value.setStyleSheet("color: #00aaff; font-family: monospace;")
        self._gamma_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        gamma_layout.addWidget(self._gamma_value)

        layout.addLayout(gamma_layout)

        # Distance
        dist_layout = QHBoxLayout()
        dist_label = QLabel("D =")
        dist_label.setStyleSheet("color: #808080;")
        dist_label.setToolTip(
            "<b>Target Distance (D)</b><br><br>"
            "Distance to the target in light-years.<br><br>"
            "The simultaneity offset scales linearly with distance."
        )
        dist_layout.addWidget(dist_label)

        self._distance_value = QLabel("2.5×10⁶")
        self._distance_value.setStyleSheet("color: #00aaff; font-family: monospace;")
        self._distance_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        dist_layout.addWidget(self._distance_value)

        dist_unit = QLabel("ly")
        dist_unit.setStyleSheet("color: #808080;")
        dist_layout.addWidget(dist_unit)

        layout.addLayout(dist_layout)

    def _connect_signals(self) -> None:
        """Connect model signals."""
        self._model.state_changed.connect(self._update_display)

    def _on_target_changed(self, index: int) -> None:
        """Handle target selection change."""
        name, distance, _ = TARGET_PRESETS[index]

        if distance is None:  # Custom
            self._custom_widget.show()
            self._model.set_target_distance(self._custom_distance_ly)
        else:
            self._custom_widget.hide()
            self._model.set_target_distance(distance)

        self._update_display()

    def _on_custom_distance_changed(self, value: float) -> None:
        """Handle custom distance input change."""
        self._custom_distance_ly = value
        self._model.set_target_distance(value)
        self._update_display()

    def _get_current_distance(self) -> float:
        """Get the currently selected target distance in light-years."""
        index = self._target_combo.currentIndex()
        _, distance, _ = TARGET_PRESETS[index]
        if distance is None:
            return self._custom_distance_ly
        return distance

    def _update_display(self) -> None:
        """Update display from model."""
        state = self._model.get_state()

        # Get values
        beta = state.get("velocity_beta", 0.0)
        gamma = state.get("lorentz_gamma", 1.0)
        distance_ly = state.get("target_distance_ly", 2.5e6)
        offset_years = state.get("simultaneity_offset_years", 0.0)

        # Update factor displays
        self._beta_value.setText(f"{beta:.4f}")
        self._gamma_value.setText(f"{gamma:.4f}")

        # Format distance display with scientific notation for large values
        self._distance_value.setText(self._format_distance(distance_ly))

        # Format and display offset with appropriate units
        offset_display, unit = self._format_offset(offset_years)
        self._offset_value.setText(offset_display)
        self._offset_unit.setText(unit)

        # Update status indicator
        # Use absolute offset in years to determine divergence
        abs_offset = abs(offset_years)
        if abs_offset < 1e-6:  # Less than ~31 seconds
            self._status_indicator.setText("● CONVERGED")
            self._status_indicator.setStyleSheet("color: #00ff88; font-family: monospace;")
        elif abs_offset < 1:  # Less than 1 year
            self._status_indicator.setText("● OFFSET")
            self._status_indicator.setStyleSheet("color: #ffaa00; font-family: monospace;")
        else:
            self._status_indicator.setText("● DIVERGENT")
            self._status_indicator.setStyleSheet("color: #ff88ff; font-family: monospace;")

    def _format_distance(self, distance_ly: float) -> str:
        """Format distance for display."""
        if distance_ly >= 1e6:
            return f"{distance_ly/1e6:.1f}×10⁶"
        elif distance_ly >= 1e3:
            return f"{distance_ly/1e3:.1f}×10³"
        elif distance_ly >= 1:
            return f"{distance_ly:.2f}"
        elif distance_ly >= 1e-3:
            # Light-days to light-hours
            light_days = distance_ly * 365.25
            if light_days >= 1:
                return f"{light_days:.1f} ld"
            return f"{light_days * 24:.1f} lh"
        else:
            # Light-minutes or light-seconds
            light_seconds = distance_ly * 31557600  # seconds per year
            if light_seconds >= 60:
                return f"{light_seconds/60:.1f} lm"
            return f"{light_seconds:.1f} ls"

    def _format_offset(self, offset_years: float) -> tuple[str, str]:
        """Format temporal offset for display, returning (value, unit)."""
        abs_offset = abs(offset_years)
        sign = "+" if offset_years >= 0 else "-"

        if abs_offset >= 1e6:
            return f"{sign}{abs_offset/1e6:,.0f}", "Myr"
        elif abs_offset >= 1000:
            return f"{sign}{abs_offset:,.0f}", "years"
        elif abs_offset >= 1:
            return f"{sign}{abs_offset:.1f}", "years"
        elif abs_offset >= 1/365.25:  # More than a day
            days = abs_offset * 365.25
            return f"{sign}{days:.1f}", "days"
        elif abs_offset >= 1/8766:  # More than an hour
            hours = abs_offset * 8766
            return f"{sign}{hours:.1f}", "hours"
        elif abs_offset >= 1/525960:  # More than a minute
            minutes = abs_offset * 525960
            return f"{sign}{minutes:.1f}", "min"
        elif abs_offset >= 1/31557600:  # More than a second
            seconds = abs_offset * 31557600
            return f"{sign}{seconds:.1f}", "s"
        else:
            # Milliseconds
            ms = abs_offset * 31557600 * 1000
            return f"{sign}{ms:.1f}", "ms"
