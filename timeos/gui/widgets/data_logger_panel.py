"""Data Logger Panel - Real-time data logging control and visualization."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QSpinBox,
    QCheckBox,
    QProgressBar,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

# Try to import data logger
try:
    from timeos.hardware.drivers.real.data_logger import (
        DataLogger,
        LogChannel,
        LogSession,
        LogFormat,
    )
    DATA_LOGGER_AVAILABLE = True
except ImportError:
    DATA_LOGGER_AVAILABLE = False


class DataLoggerPanel(QWidget):
    """Panel for controlling data logging sessions.

    Features:
    - Start/stop logging sessions
    - Configure channels and formats
    - View real-time statistics
    - Export data
    """

    # Signals
    session_started = Signal(str)  # session_id
    session_stopped = Signal(str)  # session_id
    data_exported = Signal(str)    # file_path

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._logger: DataLogger | None = None
        self._update_timer: QTimer | None = None

        self._setup_ui()
        self._connect_signals()

    def set_logger(self, logger: DataLogger) -> None:
        """Set the data logger instance.

        Args:
            logger: DataLogger instance to control
        """
        self._logger = logger
        self._update_channels_table()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Session control group
        session_group = QGroupBox("Logging Session")
        session_layout = QVBoxLayout(session_group)

        # Status row
        status_row = QHBoxLayout()

        self._status_indicator = QLabel("●")
        self._status_indicator.setStyleSheet("color: #666666; font-size: 16px;")
        status_row.addWidget(self._status_indicator)

        self._status_label = QLabel("Idle")
        self._status_label.setStyleSheet("font-weight: bold;")
        status_row.addWidget(self._status_label)

        status_row.addStretch()

        self._sample_count_label = QLabel("Samples: 0")
        status_row.addWidget(self._sample_count_label)

        session_layout.addLayout(status_row)

        # Session ID row
        id_row = QHBoxLayout()
        id_row.addWidget(QLabel("Session ID:"))

        self._session_id_edit = QLineEdit()
        self._session_id_edit.setPlaceholderText("Auto-generated if empty")
        id_row.addWidget(self._session_id_edit)

        session_layout.addLayout(id_row)

        # Format and path row
        format_row = QHBoxLayout()

        format_row.addWidget(QLabel("Format:"))
        self._format_combo = QComboBox()
        self._format_combo.addItems(["CSV", "HDF5"])
        format_row.addWidget(self._format_combo)

        format_row.addWidget(QLabel("Path:"))
        self._path_edit = QLineEdit()
        self._path_edit.setText(str(Path.home() / "timeos_data"))
        format_row.addWidget(self._path_edit)

        self._browse_btn = QPushButton("...")
        self._browse_btn.setMaximumWidth(30)
        format_row.addWidget(self._browse_btn)

        session_layout.addLayout(format_row)

        # Control buttons
        btn_row = QHBoxLayout()

        self._start_btn = QPushButton("Start Logging")
        self._start_btn.setStyleSheet(
            "QPushButton { background-color: #2d5a2d; }"
            "QPushButton:hover { background-color: #3d7a3d; }"
        )
        btn_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setStyleSheet(
            "QPushButton { background-color: #5a2d2d; }"
            "QPushButton:hover { background-color: #7a3d3d; }"
        )
        btn_row.addWidget(self._stop_btn)

        self._export_btn = QPushButton("Export Buffer")
        btn_row.addWidget(self._export_btn)

        session_layout.addLayout(btn_row)

        layout.addWidget(session_group)

        # Channels group
        channels_group = QGroupBox("Channels")
        channels_layout = QVBoxLayout(channels_group)

        self._channels_table = QTableWidget()
        self._channels_table.setColumnCount(5)
        self._channels_table.setHorizontalHeaderLabels([
            "Channel", "Value", "Units", "Rate", "Enabled"
        ])
        self._channels_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._channels_table.setMaximumHeight(150)
        channels_layout.addWidget(self._channels_table)

        # Add channel row
        add_row = QHBoxLayout()
        self._channel_name_edit = QLineEdit()
        self._channel_name_edit.setPlaceholderText("Channel name")
        add_row.addWidget(self._channel_name_edit)

        self._channel_units_edit = QLineEdit()
        self._channel_units_edit.setPlaceholderText("Units")
        self._channel_units_edit.setMaximumWidth(60)
        add_row.addWidget(self._channel_units_edit)

        self._add_channel_btn = QPushButton("Add")
        self._add_channel_btn.setMaximumWidth(50)
        add_row.addWidget(self._add_channel_btn)

        channels_layout.addLayout(add_row)

        layout.addWidget(channels_group)

        # Statistics group
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)

        # Stats grid
        stats_grid = QHBoxLayout()

        # Left column
        left_col = QVBoxLayout()
        self._duration_label = QLabel("Duration: --:--:--")
        left_col.addWidget(self._duration_label)
        self._bytes_label = QLabel("Size: 0 B")
        left_col.addWidget(self._bytes_label)
        stats_grid.addLayout(left_col)

        # Right column
        right_col = QVBoxLayout()
        self._rate_label = QLabel("Rate: 0 samples/s")
        right_col.addWidget(self._rate_label)
        self._errors_label = QLabel("Errors: 0")
        right_col.addWidget(self._errors_label)
        stats_grid.addLayout(right_col)

        stats_layout.addLayout(stats_grid)

        # Progress bar for buffer usage
        self._buffer_progress = QProgressBar()
        self._buffer_progress.setFormat("Buffer: %p%")
        self._buffer_progress.setValue(0)
        stats_layout.addWidget(self._buffer_progress)

        layout.addWidget(stats_group)

        layout.addStretch()

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn.clicked.connect(self._on_stop)
        self._export_btn.clicked.connect(self._on_export)
        self._browse_btn.clicked.connect(self._on_browse)
        self._add_channel_btn.clicked.connect(self._on_add_channel)

    def _on_start(self) -> None:
        """Start logging session."""
        if not self._logger:
            self._create_default_logger()

        # Get format
        format_map = {
            "CSV": LogFormat.CSV,
            "HDF5": LogFormat.HDF5,
        }
        log_format = format_map.get(
            self._format_combo.currentText(),
            LogFormat.CSV
        )

        # Start session
        session_id = self._session_id_edit.text() or ""
        session = self._logger.start_session(
            session_id=session_id,
            format=log_format,
            metadata={
                "started_from": "gui",
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Update UI
        self._status_indicator.setStyleSheet("color: #00ff88; font-size: 16px;")
        self._status_label.setText(f"Recording: {session.session_id}")
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

        # Start update timer
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_stats)
        self._update_timer.start(500)

        self.session_started.emit(session.session_id)

    def _on_stop(self) -> None:
        """Stop logging session."""
        if not self._logger:
            return

        session = self._logger.stop_session()

        # Stop update timer
        if self._update_timer:
            self._update_timer.stop()
            self._update_timer = None

        # Update UI
        self._status_indicator.setStyleSheet("color: #666666; font-size: 16px;")
        self._status_label.setText("Idle")
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

        if session:
            self.session_stopped.emit(session.session_id)

    def _on_export(self) -> None:
        """Export buffer to file."""
        if not self._logger:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data",
            str(Path.home() / "timeos_export.csv"),
            "CSV Files (*.csv);;All Files (*)",
        )

        if path:
            count = self._logger.export_csv(path)
            self.data_exported.emit(path)

    def _on_browse(self) -> None:
        """Browse for log directory."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Log Directory",
            self._path_edit.text(),
        )
        if path:
            self._path_edit.setText(path)

    def _on_add_channel(self) -> None:
        """Add a new channel."""
        name = self._channel_name_edit.text().strip()
        if not name:
            return

        units = self._channel_units_edit.text().strip() or "V"

        if not self._logger:
            self._create_default_logger()

        self._logger.add_channel(LogChannel(
            name=name,
            units=units,
        ))

        self._channel_name_edit.clear()
        self._channel_units_edit.clear()
        self._update_channels_table()

    def _create_default_logger(self) -> None:
        """Create default data logger."""
        if not DATA_LOGGER_AVAILABLE:
            return

        path = self._path_edit.text()
        self._logger = DataLogger(base_path=path)

        # Add default channels
        default_channels = [
            LogChannel(name="field_tesla", units="T"),
            LogChannel(name="temperature_kelvin", units="K"),
            LogChannel(name="power_watts", units="W"),
            LogChannel(name="causality_risk", units="%"),
        ]
        for ch in default_channels:
            self._logger.add_channel(ch)

        self._update_channels_table()

    def _update_channels_table(self) -> None:
        """Update the channels table."""
        if not self._logger:
            return

        channels = self._logger.channels
        self._channels_table.setRowCount(len(channels))

        for row, ch in enumerate(channels):
            self._channels_table.setItem(row, 0, QTableWidgetItem(ch.name))

            # Get latest value
            latest = self._logger.get_latest(ch.name)
            value_str = f"{latest[1]:.4f}" if latest else "--"
            self._channels_table.setItem(row, 1, QTableWidgetItem(value_str))

            self._channels_table.setItem(row, 2, QTableWidgetItem(ch.units))
            self._channels_table.setItem(
                row, 3, QTableWidgetItem(f"1:{ch.decimation}")
            )

            # Enabled checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            self._channels_table.setCellWidget(row, 4, checkbox)

    def _update_stats(self) -> None:
        """Update statistics display."""
        if not self._logger or not self._logger.session:
            return

        session = self._logger.session

        # Duration
        duration = time.time() - session.start_time
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        self._duration_label.setText(f"Duration: {hours:02d}:{minutes:02d}:{seconds:02d}")

        # Size
        bytes_written = session.bytes_written
        if bytes_written < 1024:
            size_str = f"{bytes_written} B"
        elif bytes_written < 1024 * 1024:
            size_str = f"{bytes_written / 1024:.1f} KB"
        else:
            size_str = f"{bytes_written / (1024 * 1024):.1f} MB"
        self._bytes_label.setText(f"Size: {size_str}")

        # Sample count
        self._sample_count_label.setText(f"Samples: {session.total_samples:,}")

        # Rate
        if duration > 0:
            rate = session.total_samples / duration
            self._rate_label.setText(f"Rate: {rate:.1f} samples/s")

        # Errors
        self._errors_label.setText(f"Errors: {session.errors}")

        # Update channel values
        self._update_channels_table()

    def log_data(self, data: dict[str, float]) -> None:
        """Log data from external source.

        Args:
            data: Channel name -> value mapping
        """
        if self._logger:
            self._logger.log_dict(data)
