"""Timeline View Widget - Visual timeline with events and branches."""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

from timeos.gui.models.machine_model import MachineModel


# Configure pyqtgraph for dark theme
pg.setConfigOptions(antialias=True, background='#0d0d0d', foreground='#808080')

# Branch colors for visualization
BRANCH_COLORS = [
    '#00ff88',  # main - green
    '#ff8800',  # branch 1 - orange
    '#00aaff',  # branch 2 - blue
    '#ff00aa',  # branch 3 - magenta
    '#aaff00',  # branch 4 - yellow-green
    '#aa00ff',  # branch 5 - purple
]


class TimelinePlot(pg.PlotWidget):
    """PyQtGraph-based timeline visualization with branch support."""

    event_clicked = Signal(dict)  # Emitted when an event is clicked

    def __init__(self, model: MachineModel, parent: QWidget | None = None):
        super().__init__(parent)

        self._model = model
        self._events: list[dict] = []
        self._branches: list[dict] = []
        self._current_time = 0.0
        self._anchor_time: float | None = 0.0
        self._branch_y_positions: dict[str, float] = {"main": 0.0}

        self._setup_plot()
        self._create_items()

    def _setup_plot(self) -> None:
        """Configure the plot appearance."""
        self.setMinimumHeight(150)
        self.setMouseEnabled(x=True, y=False)
        self.setMenuEnabled(False)

        # Configure axes
        self.setLabel('bottom', 't', units='s')
        self.showGrid(x=True, y=False, alpha=0.3)

        # Hide y-axis (timeline uses y for branches)
        self.getAxis('left').hide()
        self.setYRange(-1.5, 1.5)

        # Style the plot
        self.getAxis('bottom').setPen(pg.mkPen('#3a3a3a', width=1))
        self.getAxis('bottom').setTextPen('#808080')

    def _create_items(self) -> None:
        """Create plot items for timeline elements."""
        # Main timeline axis line
        self._axis_line = pg.InfiniteLine(
            pos=0, angle=0, pen=pg.mkPen('#3a3a3a', width=2)
        )
        self.addItem(self._axis_line)

        # Branch lines (will be populated dynamically)
        self._branch_lines: list[pg.PlotDataItem] = []
        self._branch_labels: list[pg.TextItem] = []
        self._fork_connectors: list[pg.PlotDataItem] = []

        # Anchor marker (vertical line + diamond)
        self._anchor_line = pg.InfiniteLine(
            pos=0, angle=90, pen=pg.mkPen('#00aaff', width=1, style=Qt.PenStyle.DashLine)
        )
        self._anchor_line.setVisible(False)
        self.addItem(self._anchor_line)

        self._anchor_marker = pg.ScatterPlotItem(
            size=16, symbol='d', pen=pg.mkPen('#00aaff', width=2),
            brush=pg.mkBrush('#00aaff')
        )
        self.addItem(self._anchor_marker)

        # Current position marker (glowing circle)
        self._current_glow = pg.ScatterPlotItem(
            size=30, symbol='o', pen=None,
            brush=pg.mkBrush(0, 255, 136, 50)
        )
        self.addItem(self._current_glow)

        self._current_marker = pg.ScatterPlotItem(
            size=16, symbol='o', pen=pg.mkPen('#00ff88', width=2),
            brush=pg.mkBrush('#00ff88')
        )
        self.addItem(self._current_marker)

        # Event markers (will be set per branch)
        self._event_markers = pg.ScatterPlotItem(
            size=10, symbol='o', pen=pg.mkPen('#808080', width=1),
            brush=pg.mkBrush('#404040'), hoverable=True
        )
        self._event_markers.sigClicked.connect(self._on_event_clicked)
        self.addItem(self._event_markers)

        # Labels
        self._anchor_label = pg.TextItem("ANCHOR", color='#00aaff', anchor=(0.5, 1.5))
        self._anchor_label.setFont(QFont("Monospace", 8))
        self.addItem(self._anchor_label)

        self._current_label = pg.TextItem("NOW", color='#00ff88', anchor=(0.5, 1.5))
        self._current_label.setFont(QFont("Monospace", 8))
        self.addItem(self._current_label)

    def _get_branch_color(self, branch_id: str) -> str:
        """Get color for a branch."""
        if branch_id == "main":
            return BRANCH_COLORS[0]
        # Hash branch name to get consistent color
        idx = hash(branch_id) % (len(BRANCH_COLORS) - 1) + 1
        return BRANCH_COLORS[idx]

    def set_branches(self, branches: list[dict]) -> None:
        """Update branch visualization."""
        self._branches = branches

        # Clear existing branch items
        for line in self._branch_lines:
            self.removeItem(line)
        for label in self._branch_labels:
            self.removeItem(label)
        for connector in self._fork_connectors:
            self.removeItem(connector)
        self._branch_lines.clear()
        self._branch_labels.clear()
        self._fork_connectors.clear()

        # Calculate y positions for branches
        self._branch_y_positions = {"main": 0.0}
        y_offset = 0.5
        for i, branch in enumerate(branches):
            if branch["branch_id"] != "main":
                # Alternate above and below main line
                sign = 1 if i % 2 == 0 else -1
                self._branch_y_positions[branch["branch_id"]] = sign * y_offset
                y_offset += 0.3

        # Create branch lines and labels
        view_range = self.viewRange()
        x_min, x_max = view_range[0] if view_range else (-10, 10)

        for branch in branches:
            branch_id = branch["branch_id"]
            y = self._branch_y_positions.get(branch_id, 0.0)
            color = self._get_branch_color(branch_id)

            # Branch line
            if branch_id != "main":  # Main line is already drawn
                line = self.plot(
                    [x_min, x_max], [y, y],
                    pen=pg.mkPen(color, width=1, style=Qt.PenStyle.DashLine)
                )
                self._branch_lines.append(line)

                # Branch label
                label = pg.TextItem(branch_id, color=color, anchor=(0, 0.5))
                label.setFont(QFont("Monospace", 7))
                label.setPos(x_min + 0.5, y)
                self.addItem(label)
                self._branch_labels.append(label)

                # Fork connector from parent
                parent_branch = branch.get("parent_branch")
                fork_event_id = branch.get("fork_event_id")
                if parent_branch and fork_event_id:
                    parent_y = self._branch_y_positions.get(parent_branch, 0.0)
                    # Find fork time from events
                    fork_time = self._get_event_time(fork_event_id)
                    if fork_time is not None:
                        connector = self.plot(
                            [fork_time, fork_time], [parent_y, y],
                            pen=pg.mkPen(color, width=2)
                        )
                        self._fork_connectors.append(connector)

                        # Fork point marker
                        fork_marker = pg.ScatterPlotItem(
                            [fork_time], [parent_y],
                            size=8, symbol='s',
                            pen=pg.mkPen(color, width=1),
                            brush=pg.mkBrush(color)
                        )
                        self.addItem(fork_marker)
                        self._fork_connectors.append(fork_marker)

    def _get_event_time(self, event_id: str) -> float | None:
        """Get time for an event by ID."""
        for event in self._events:
            if event.get("event_id") == event_id:
                return event.get("time")
        return None

    def set_current_time(self, t: float) -> None:
        """Update current time marker."""
        self._current_time = t
        self._current_marker.setData([t], [0])
        self._current_glow.setData([t], [0])
        self._current_label.setPos(t, 0.5)

    def set_anchor_time(self, t: float | None) -> None:
        """Update anchor marker."""
        self._anchor_time = t
        if t is not None:
            self._anchor_line.setPos(t)
            self._anchor_line.setVisible(True)
            self._anchor_marker.setData([t], [0])
            self._anchor_label.setPos(t, 0.5)
            self._anchor_label.setVisible(True)
        else:
            self._anchor_line.setVisible(False)
            self._anchor_marker.setData([], [])
            self._anchor_label.setVisible(False)

    def set_events(self, events: list[dict]) -> None:
        """Update event markers with branch positioning."""
        self._events = events
        if events:
            times = []
            ys = []
            colors = []

            for e in events:
                times.append(e.get("time", 0.0))
                branch_id = e.get("branch_id", "main")
                y = self._branch_y_positions.get(branch_id, 0.0)
                ys.append(y)
                colors.append(self._get_branch_color(branch_id))

            # Create colored brushes for each event
            brushes = [pg.mkBrush(c) for c in colors]
            pens = [pg.mkPen(c, width=1) for c in colors]

            self._event_markers.setData(
                times, ys,
                brush=brushes,
                pen=pens
            )
        else:
            self._event_markers.setData([], [])

    def set_view_range(self, start: float, end: float) -> None:
        """Set visible time range."""
        self.setXRange(start, end, padding=0.05)

        # Update branch line lengths
        for line in self._branch_lines:
            x_data, y_data = line.getData()
            if x_data is not None and len(x_data) >= 2:
                y = y_data[0]
                line.setData([start - 5, end + 5], [y, y])

        # Update branch label positions
        for label in self._branch_labels:
            pos = label.pos()
            label.setPos(start + 0.5, pos.y())

    def _on_event_clicked(self, plot, points) -> None:
        """Handle click on event marker."""
        if points and self._events:
            # Find the clicked event
            idx = points[0].index()
            if 0 <= idx < len(self._events):
                self.event_clicked.emit(self._events[idx])


class TimelineView(QGroupBox):
    """Timeline visualization widget with controls."""

    event_selected = Signal(dict)  # Emitted when user selects an event

    def __init__(self, model: MachineModel, parent: QWidget | None = None):
        super().__init__("TIMELINE", parent)

        self._model = model
        self._auto_follow = True
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the timeline UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Plot widget
        self._plot = TimelinePlot(self._model)
        layout.addWidget(self._plot)

        # Control bar
        control_layout = QHBoxLayout()
        control_layout.setSpacing(8)

        # Zoom controls
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(24, 24)
        zoom_in_btn.setToolTip("Zoom in")
        zoom_in_btn.clicked.connect(self._zoom_in)
        control_layout.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setFixedSize(24, 24)
        zoom_out_btn.setToolTip("Zoom out")
        zoom_out_btn.clicked.connect(self._zoom_out)
        control_layout.addWidget(zoom_out_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.setFixedSize(48, 24)
        reset_btn.setToolTip("Reset view")
        reset_btn.clicked.connect(self._reset_view)
        control_layout.addWidget(reset_btn)

        # Auto-follow toggle
        self._follow_btn = QPushButton("Follow")
        self._follow_btn.setFixedSize(48, 24)
        self._follow_btn.setCheckable(True)
        self._follow_btn.setChecked(True)
        self._follow_btn.setToolTip("Auto-follow current time")
        self._follow_btn.toggled.connect(self._toggle_follow)
        control_layout.addWidget(self._follow_btn)

        control_layout.addStretch()

        # Info labels
        self._range_label = QLabel("View: -10.0s to +10.0s")
        self._range_label.setStyleSheet("color: #808080; font-size: 9pt;")
        control_layout.addWidget(self._range_label)

        self._event_count = QLabel("Events: 0")
        self._event_count.setStyleSheet("color: #808080; font-size: 9pt;")
        control_layout.addWidget(self._event_count)

        layout.addLayout(control_layout)

    def _connect_signals(self) -> None:
        """Connect signals."""
        self._model.state_changed.connect(self._update_display)
        self._model.event_logged.connect(self._on_new_event)
        self._plot.event_clicked.connect(self._on_event_clicked)

    def _update_display(self) -> None:
        """Update timeline from model state."""
        state = self._model.get_state()

        current_time = state.get("current_time", 0.0)
        anchor_time = state.get("anchor_time")

        self._plot.set_current_time(current_time)
        self._plot.set_anchor_time(anchor_time)

        # Auto-follow current time
        if self._auto_follow:
            view_start = current_time - 10.0
            view_end = current_time + 10.0
            self._plot.set_view_range(view_start, view_end)
            self._range_label.setText(f"View: {view_start:.1f}s to {view_end:.1f}s")

        # Update branches
        branches = self._model.get_branches()
        self._plot.set_branches(branches)

        # Try to get actual timeline events first
        timeline_events = self._model.get_timeline_events()

        # Fall back to GUI log events if no timeline events
        if not timeline_events:
            events = self._model.get_events()
            # Convert to timeline format with time field
            for e in events:
                evt = dict(e)
                evt["branch_id"] = "main"  # GUI events are on main branch
                # Use timestamp if available, otherwise 0
                if "timestamp" in e:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(e["timestamp"])
                        evt["time"] = dt.timestamp() % 1000  # Use fractional part for demo
                    except:
                        evt["time"] = 0.0
                timeline_events.append(evt)

        self._plot.set_events(timeline_events)

        # Update branch count in status
        branch_count = len(branches)
        event_count = len(timeline_events)
        if branch_count > 1:
            self._event_count.setText(f"Events: {event_count} | Branches: {branch_count}")
        else:
            self._event_count.setText(f"Events: {event_count}")

    def _on_new_event(self, event: dict) -> None:
        """Handle new event logged."""
        self._update_display()

    def _on_event_clicked(self, event: dict) -> None:
        """Handle event marker click."""
        self.event_selected.emit(event)

    def _zoom_in(self) -> None:
        """Zoom in on timeline."""
        self._plot.getViewBox().scaleBy((0.5, 1))
        self._auto_follow = False
        self._follow_btn.setChecked(False)

    def _zoom_out(self) -> None:
        """Zoom out on timeline."""
        self._plot.getViewBox().scaleBy((2, 1))
        self._auto_follow = False
        self._follow_btn.setChecked(False)

    def _reset_view(self) -> None:
        """Reset to default view."""
        state = self._model.get_state()
        current_time = state.get("current_time", 0.0)
        self._plot.set_view_range(current_time - 10.0, current_time + 10.0)
        self._auto_follow = True
        self._follow_btn.setChecked(True)

    def _toggle_follow(self, checked: bool) -> None:
        """Toggle auto-follow mode."""
        self._auto_follow = checked
        if checked:
            self._update_display()
