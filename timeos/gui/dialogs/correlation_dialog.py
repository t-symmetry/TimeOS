"""Correlation Dialog - Interactive stream alignment visualization.

Allows users to:
- Load two data streams from files
- Visualize cross-correlation
- Find and apply optimal time offset
- Export aligned data
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional, List, Tuple

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QGroupBox,
    QSpinBox,
    QDoubleSpinBox,
    QProgressBar,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QWidget,
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont


# Configure pyqtgraph
pg.setConfigOptions(antialias=True, background='#1a1a1a', foreground='#808080')


class CorrelationWorker(QThread):
    """Worker thread for correlation computation."""

    progress = Signal(int)
    finished = Signal(dict)  # Result dict
    error = Signal(str)

    def __init__(
        self,
        times1: List[float],
        values1: List[float],
        times2: List[float],
        values2: List[float],
        max_offset: float = 1.0,
    ):
        super().__init__()
        self.times1 = times1
        self.values1 = values1
        self.times2 = times2
        self.values2 = values2
        self.max_offset = max_offset

    def run(self) -> None:
        """Run correlation computation."""
        try:
            from timeos.correlation import find_offset, align_streams
            from timeos.correlation.align import TimeSeries

            self.progress.emit(10)

            series1 = TimeSeries(times=self.times1, values=self.values1)
            series2 = TimeSeries(times=self.times2, values=self.values2)

            self.progress.emit(30)

            result = find_offset(series1, series2, max_offset=self.max_offset)

            self.progress.emit(70)

            # Get aligned series
            _, aligned = align_streams(series1, series2, result)

            self.progress.emit(100)

            self.finished.emit({
                "offset": result.offset,
                "uncertainty": result.offset_uncertainty,
                "correlation": result.correlation,
                "confidence": result.confidence,
                "aligned_times": aligned.times,
                "aligned_values": aligned.values,
                "series1": series1,
                "series2": series2,
            })

        except Exception as e:
            self.error.emit(str(e))


class StreamPlot(pg.PlotWidget):
    """Plot widget for displaying data streams."""

    def __init__(self, title: str = "", parent: QWidget | None = None):
        super().__init__(parent, title=title)

        self.setMinimumHeight(150)
        self.showGrid(x=True, y=True, alpha=0.3)
        self.setLabel('bottom', 'Time', units='s')
        self.setLabel('left', 'Value')

        # Plot items
        self._line1: Optional[pg.PlotDataItem] = None
        self._line2: Optional[pg.PlotDataItem] = None

    def set_data(
        self,
        times1: List[float],
        values1: List[float],
        times2: Optional[List[float]] = None,
        values2: Optional[List[float]] = None,
        label1: str = "Stream 1",
        label2: str = "Stream 2",
    ) -> None:
        """Set plot data."""
        # Clear existing
        self.clear()

        # Plot first series
        if times1 and values1:
            self._line1 = self.plot(
                times1, values1,
                pen=pg.mkPen('#00aaff', width=2),
                name=label1,
            )

        # Plot second series
        if times2 and values2:
            self._line2 = self.plot(
                times2, values2,
                pen=pg.mkPen('#ff8800', width=2),
                name=label2,
            )

        # Add legend
        if self._line1 or self._line2:
            self.addLegend()


class CorrelationPlot(pg.PlotWidget):
    """Plot widget for cross-correlation results."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, title="Cross-Correlation")

        self.setMinimumHeight(150)
        self.showGrid(x=True, y=True, alpha=0.3)
        self.setLabel('bottom', 'Offset', units='s')
        self.setLabel('left', 'Correlation')

        # Zero line
        self.addItem(pg.InfiniteLine(
            pos=0, angle=90,
            pen=pg.mkPen('#3a3a3a', style=Qt.PenStyle.DashLine)
        ))

        self._corr_line: Optional[pg.PlotDataItem] = None
        self._peak_marker: Optional[pg.ScatterPlotItem] = None

    def set_correlation(
        self,
        offsets: List[float],
        correlations: List[float],
        peak_offset: float,
        peak_correlation: float,
    ) -> None:
        """Set correlation data."""
        self.clear()

        # Re-add zero line
        self.addItem(pg.InfiniteLine(
            pos=0, angle=90,
            pen=pg.mkPen('#3a3a3a', style=Qt.PenStyle.DashLine)
        ))

        # Plot correlation curve
        self._corr_line = self.plot(
            offsets, correlations,
            pen=pg.mkPen('#00ff88', width=2),
        )

        # Mark peak
        self._peak_marker = pg.ScatterPlotItem(
            [peak_offset], [peak_correlation],
            size=15, symbol='o',
            pen=pg.mkPen('#ff0000', width=2),
            brush=pg.mkBrush('#ff0000'),
        )
        self.addItem(self._peak_marker)


class CorrelationDialog(QDialog):
    """Dialog for interactive stream correlation and alignment."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("Stream Correlation")
        self.setMinimumSize(900, 700)

        self._file1_path: Optional[Path] = None
        self._file2_path: Optional[Path] = None
        self._times1: List[float] = []
        self._values1: List[float] = []
        self._times2: List[float] = []
        self._values2: List[float] = []
        self._result: Optional[dict] = None
        self._worker: Optional[CorrelationWorker] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # File selection section
        file_group = QGroupBox("Data Files")
        file_layout = QGridLayout(file_group)

        # File 1
        file_layout.addWidget(QLabel("Stream 1:"), 0, 0)
        self._file1_edit = QLineEdit()
        self._file1_edit.setReadOnly(True)
        file_layout.addWidget(self._file1_edit, 0, 1)
        file1_btn = QPushButton("Browse...")
        file1_btn.clicked.connect(lambda: self._browse_file(1))
        file_layout.addWidget(file1_btn, 0, 2)

        # File 2
        file_layout.addWidget(QLabel("Stream 2:"), 1, 0)
        self._file2_edit = QLineEdit()
        self._file2_edit.setReadOnly(True)
        file_layout.addWidget(self._file2_edit, 1, 1)
        file2_btn = QPushButton("Browse...")
        file2_btn.clicked.connect(lambda: self._browse_file(2))
        file_layout.addWidget(file2_btn, 1, 2)

        # Column names
        file_layout.addWidget(QLabel("Time column:"), 2, 0)
        self._time_col_edit = QLineEdit("time")
        file_layout.addWidget(self._time_col_edit, 2, 1)

        file_layout.addWidget(QLabel("Value column:"), 3, 0)
        self._value_col_edit = QLineEdit("value")
        file_layout.addWidget(self._value_col_edit, 3, 1)

        layout.addWidget(file_group)

        # Parameters section
        param_group = QGroupBox("Parameters")
        param_layout = QHBoxLayout(param_group)

        param_layout.addWidget(QLabel("Max offset (s):"))
        self._max_offset_spin = QDoubleSpinBox()
        self._max_offset_spin.setRange(0.001, 1000.0)
        self._max_offset_spin.setValue(1.0)
        self._max_offset_spin.setDecimals(3)
        param_layout.addWidget(self._max_offset_spin)

        param_layout.addStretch()

        # Correlate button
        self._correlate_btn = QPushButton("Correlate")
        self._correlate_btn.clicked.connect(self._run_correlation)
        self._correlate_btn.setEnabled(False)
        param_layout.addWidget(self._correlate_btn)

        layout.addWidget(param_group)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Results section
        results_group = QGroupBox("Results")
        results_layout = QGridLayout(results_group)

        results_layout.addWidget(QLabel("Offset:"), 0, 0)
        self._offset_label = QLabel("--")
        self._offset_label.setFont(QFont("Monospace", 10))
        results_layout.addWidget(self._offset_label, 0, 1)

        results_layout.addWidget(QLabel("Uncertainty:"), 0, 2)
        self._uncertainty_label = QLabel("--")
        self._uncertainty_label.setFont(QFont("Monospace", 10))
        results_layout.addWidget(self._uncertainty_label, 0, 3)

        results_layout.addWidget(QLabel("Correlation:"), 1, 0)
        self._correlation_label = QLabel("--")
        self._correlation_label.setFont(QFont("Monospace", 10))
        results_layout.addWidget(self._correlation_label, 1, 1)

        results_layout.addWidget(QLabel("Confidence:"), 1, 2)
        self._confidence_label = QLabel("--")
        self._confidence_label.setFont(QFont("Monospace", 10))
        results_layout.addWidget(self._confidence_label, 1, 3)

        layout.addWidget(results_group)

        # Plots
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Input streams plot
        self._input_plot = StreamPlot("Input Streams")
        splitter.addWidget(self._input_plot)

        # Aligned streams plot
        self._aligned_plot = StreamPlot("Aligned Streams")
        splitter.addWidget(self._aligned_plot)

        layout.addWidget(splitter, 1)

        # Button bar
        button_layout = QHBoxLayout()

        self._export_btn = QPushButton("Export Aligned...")
        self._export_btn.clicked.connect(self._export_aligned)
        self._export_btn.setEnabled(False)
        button_layout.addWidget(self._export_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _browse_file(self, file_num: int) -> None:
        """Browse for a data file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select Stream {file_num} File",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )

        if path:
            if file_num == 1:
                self._file1_path = Path(path)
                self._file1_edit.setText(path)
                self._load_file(1)
            else:
                self._file2_path = Path(path)
                self._file2_edit.setText(path)
                self._load_file(2)

            self._update_correlate_button()

    def _load_file(self, file_num: int) -> None:
        """Load data from a file."""
        path = self._file1_path if file_num == 1 else self._file2_path
        if not path:
            return

        time_col = self._time_col_edit.text()
        value_col = self._value_col_edit.text()

        times = []
        values = []

        try:
            with open(path, newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        times.append(float(row[time_col]))
                        values.append(float(row[value_col]))
                    except (KeyError, ValueError):
                        continue

            if file_num == 1:
                self._times1 = times
                self._values1 = values
            else:
                self._times2 = times
                self._values2 = values

            # Update plot
            self._update_input_plot()

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load file: {e}")

    def _update_correlate_button(self) -> None:
        """Update correlate button state."""
        enabled = bool(self._times1 and self._values1 and self._times2 and self._values2)
        self._correlate_btn.setEnabled(enabled)

    def _update_input_plot(self) -> None:
        """Update the input streams plot."""
        self._input_plot.set_data(
            self._times1, self._values1,
            self._times2, self._values2,
            label1="Stream 1",
            label2="Stream 2",
        )

    def _run_correlation(self) -> None:
        """Run the correlation computation."""
        if self._worker is not None and self._worker.isRunning():
            return

        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._correlate_btn.setEnabled(False)

        self._worker = CorrelationWorker(
            self._times1, self._values1,
            self._times2, self._values2,
            max_offset=self._max_offset_spin.value(),
        )
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_correlation_finished)
        self._worker.error.connect(self._on_correlation_error)
        self._worker.start()

    def _on_correlation_finished(self, result: dict) -> None:
        """Handle correlation completion."""
        self._result = result
        self._progress.setVisible(False)
        self._correlate_btn.setEnabled(True)
        self._export_btn.setEnabled(True)

        # Update results labels
        offset = result["offset"]
        uncertainty = result["uncertainty"]
        correlation = result["correlation"]
        confidence = result["confidence"]

        # Format offset nicely
        if abs(offset) < 0.001:
            offset_str = f"{offset * 1e6:.1f} µs"
            unc_str = f"±{uncertainty * 1e6:.1f} µs"
        elif abs(offset) < 1.0:
            offset_str = f"{offset * 1e3:.3f} ms"
            unc_str = f"±{uncertainty * 1e3:.3f} ms"
        else:
            offset_str = f"{offset:.6f} s"
            unc_str = f"±{uncertainty:.6f} s"

        self._offset_label.setText(offset_str)
        self._uncertainty_label.setText(unc_str)
        self._correlation_label.setText(f"{correlation:.4f}")
        self._confidence_label.setText(f"{confidence * 100:.1f}%")

        # Color-code correlation quality
        if correlation > 0.8:
            color = "#00ff88"
        elif correlation > 0.5:
            color = "#ffaa00"
        else:
            color = "#ff4444"
        self._correlation_label.setStyleSheet(f"color: {color};")

        # Update aligned plot
        aligned_times = result["aligned_times"]
        aligned_values = result["aligned_values"]

        self._aligned_plot.set_data(
            self._times1, self._values1,
            aligned_times, aligned_values,
            label1="Stream 1",
            label2="Stream 2 (aligned)",
        )

    def _on_correlation_error(self, error: str) -> None:
        """Handle correlation error."""
        self._progress.setVisible(False)
        self._correlate_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Correlation failed: {error}")

    def _export_aligned(self) -> None:
        """Export aligned data."""
        if not self._result:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Aligned Data",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )

        if not path:
            return

        try:
            time_col = self._time_col_edit.text()
            value_col = self._value_col_edit.text()

            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([time_col, value_col, 'source'])

                # Write stream 1
                for t, v in zip(self._times1, self._values1):
                    writer.writerow([t, v, 'stream1'])

                # Write aligned stream 2
                aligned_times = self._result["aligned_times"]
                aligned_values = self._result["aligned_values"]
                for t, v in zip(aligned_times, aligned_values):
                    writer.writerow([t, v, 'stream2_aligned'])

            QMessageBox.information(self, "Success", f"Exported to: {path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed: {e}")
