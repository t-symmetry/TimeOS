"""Service Call Widget - Interactive ROS2 service calling."""

from __future__ import annotations

import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QPushButton,
    QComboBox,
    QTextEdit,
    QLineEdit,
    QFormLayout,
    QSplitter,
    QFrame,
)
from PySide6.QtCore import Qt

from .ros2_bridge import ROS2Bridge, PRIORITY_SERVICES, ServiceInfo


# Request templates for common services
SERVICE_TEMPLATES = {
    '/timeos/set_field': {
        'field_strength_tesla': 0.5,
        'ramp_rate_tesla_per_sec': 0.01,
    },
    '/timeos/arm_system': {
        'arm': True,
        'operator_id': 'gui_user',
        'force': False,
    },
    '/timeos/trigger_estop': {
        'operator_id': 'gui_user',
        'reason': 'Manual trigger from GUI',
    },
    '/timeos/start_experiment': {},
    '/timeos/stop_experiment': {},
    '/timeos/create_event': {
        'event_type': 'user_event',
        'description': 'Event created from GUI',
        'x': 0.0,
        'y': 0.0,
        'z': 0.0,
        't': 0.0,
        'timeline_id': 'main',
        'parent_event_id': '',
        'data_json': '{}',
    },
}


class ServiceCallWidget(QWidget):
    """Widget for calling ROS2 services interactively."""

    def __init__(
        self,
        bridge: ROS2Bridge,
        parent: QWidget | None = None
    ):
        super().__init__(parent)

        self._bridge = bridge
        self._current_service: Optional[str] = None
        self._current_type: Optional[str] = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)

        # Service selection
        select_layout = QHBoxLayout()

        select_layout.addWidget(QLabel("Service:"))

        self._service_combo = QComboBox()
        self._service_combo.setMinimumWidth(300)
        self._service_combo.currentTextChanged.connect(self._on_service_changed)
        select_layout.addWidget(self._service_combo, 1)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._on_refresh)
        select_layout.addWidget(self._refresh_btn)

        layout.addLayout(select_layout)

        # Service info
        self._type_label = QLabel("Type: -")
        self._type_label.setStyleSheet("color: #808080; margin-left: 60px;")
        layout.addWidget(self._type_label)

        # Splitter for request/response
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Request panel
        request_group = QGroupBox("Request")
        request_layout = QVBoxLayout(request_group)

        self._request_text = QTextEdit()
        self._request_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                border: 1px solid #404040;
            }
        """)
        self._request_text.setPlaceholderText(
            "Enter request as JSON...\n\n"
            "Example:\n"
            '{\n'
            '    "field_strength_tesla": 0.5,\n'
            '    "ramp_rate_tesla_per_sec": 0.01\n'
            '}'
        )
        request_layout.addWidget(self._request_text)

        # Request buttons
        req_btn_layout = QHBoxLayout()

        self._template_btn = QPushButton("Load Template")
        self._template_btn.clicked.connect(self._on_load_template)
        req_btn_layout.addWidget(self._template_btn)

        self._format_btn = QPushButton("Format JSON")
        self._format_btn.clicked.connect(self._on_format_json)
        req_btn_layout.addWidget(self._format_btn)

        req_btn_layout.addStretch()
        request_layout.addLayout(req_btn_layout)

        splitter.addWidget(request_group)

        # Response panel
        response_group = QGroupBox("Response")
        response_layout = QVBoxLayout(response_group)

        self._response_text = QTextEdit()
        self._response_text.setReadOnly(True)
        self._response_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                border: 1px solid #404040;
            }
        """)
        self._response_text.setPlaceholderText("Response will appear here...")
        response_layout.addWidget(self._response_text)

        splitter.addWidget(response_group)
        splitter.setSizes([400, 400])

        layout.addWidget(splitter, 1)

        # Call button
        call_layout = QHBoxLayout()

        self._call_btn = QPushButton("Call Service")
        self._call_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d5a2d;
                color: white;
                padding: 10px 24px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3d7a3d;
            }
            QPushButton:disabled {
                background-color: #404040;
                color: #808080;
            }
        """)
        self._call_btn.clicked.connect(self._on_call_service)
        call_layout.addWidget(self._call_btn)

        self._status_label = QLabel("")
        call_layout.addWidget(self._status_label)

        call_layout.addStretch()

        self._clear_btn = QPushButton("Clear Response")
        self._clear_btn.clicked.connect(self._on_clear_response)
        call_layout.addWidget(self._clear_btn)

        layout.addLayout(call_layout)

        # Quick access buttons for priority services
        quick_group = QGroupBox("Quick Actions")
        quick_layout = QHBoxLayout(quick_group)

        quick_actions = [
            ("E-STOP", "/timeos/trigger_estop", "#5a2d2d"),
            ("Arm", "/timeos/arm_system", "#2d4a2d"),
            ("Set Field", "/timeos/set_field", "#2d4a5a"),
            ("Start Exp", "/timeos/start_experiment", "#4a4a2d"),
        ]

        for label, service, color in quick_actions:
            btn = QPushButton(label)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    padding: 6px 12px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {color.replace('2d', '4d')};
                }}
            """)
            btn.clicked.connect(lambda checked, s=service: self._select_service(s))
            quick_layout.addWidget(btn)

        quick_layout.addStretch()
        layout.addWidget(quick_group)

    def _connect_signals(self) -> None:
        """Connect bridge signals."""
        self._bridge.services_updated.connect(self._on_services_updated)
        self._bridge.service_response.connect(self._on_service_response)
        self._bridge.ros2_available_changed.connect(self._on_ros2_changed)

    def _on_ros2_changed(self, available: bool) -> None:
        """Handle ROS2 availability change."""
        self._call_btn.setEnabled(available)
        if available:
            self._bridge.get_service_list()

    def _on_refresh(self) -> None:
        """Refresh the service list."""
        if self._bridge.ros2_available:
            self._bridge.get_service_list()

    def _on_services_updated(self, services: List[ServiceInfo]) -> None:
        """Handle service list update."""
        current = self._service_combo.currentText()

        self._service_combo.blockSignals(True)
        self._service_combo.clear()

        # Add priority services first
        for service, srv_type in PRIORITY_SERVICES:
            matching = [s for s in services if s.name == service]
            if matching:
                display = f"{service} [{srv_type}]"
                self._service_combo.addItem(display, (service, srv_type))

        # Add separator
        if self._service_combo.count() > 0:
            self._service_combo.insertSeparator(self._service_combo.count())

        # Add remaining services
        priority_names = [s[0] for s in PRIORITY_SERVICES]
        for service in services:
            if service.name not in priority_names:
                display = f"{service.name} [{service.srv_type}]" if service.srv_type else service.name
                self._service_combo.addItem(display, (service.name, service.srv_type))

        self._service_combo.blockSignals(False)

        # Try to restore selection
        if current:
            for i in range(self._service_combo.count()):
                data = self._service_combo.itemData(i)
                if data and data[0] in current:
                    self._service_combo.setCurrentIndex(i)
                    break

    def _on_service_changed(self, text: str) -> None:
        """Handle service selection change."""
        index = self._service_combo.currentIndex()
        if index >= 0:
            data = self._service_combo.itemData(index)
            if data:
                self._current_service, self._current_type = data
                self._type_label.setText(f"Type: {self._current_type}")

                # Load template if available
                if self._current_service in SERVICE_TEMPLATES:
                    self._on_load_template()

    def _select_service(self, service: str) -> None:
        """Select a service programmatically."""
        for i in range(self._service_combo.count()):
            data = self._service_combo.itemData(i)
            if data and data[0] == service:
                self._service_combo.setCurrentIndex(i)
                break

    def _on_load_template(self) -> None:
        """Load template for current service."""
        if self._current_service in SERVICE_TEMPLATES:
            template = SERVICE_TEMPLATES[self._current_service]
            self._request_text.setPlainText(
                json.dumps(template, indent=2)
            )

    def _on_format_json(self) -> None:
        """Format the request JSON."""
        try:
            text = self._request_text.toPlainText()
            if text.strip():
                data = json.loads(text)
                self._request_text.setPlainText(
                    json.dumps(data, indent=2)
                )
        except json.JSONDecodeError as e:
            self._status_label.setText(f"JSON Error: {e}")
            self._status_label.setStyleSheet("color: #ff4444;")

    def _on_call_service(self) -> None:
        """Call the current service."""
        if not self._current_service:
            self._status_label.setText("No service selected")
            self._status_label.setStyleSheet("color: #ffaa00;")
            return

        if not self._current_type:
            self._status_label.setText("Service type unknown")
            self._status_label.setStyleSheet("color: #ffaa00;")
            return

        if not self._bridge.ros2_available:
            self._status_label.setText("ROS2 not available")
            self._status_label.setStyleSheet("color: #ff4444;")
            return

        # Parse request
        try:
            request_text = self._request_text.toPlainText().strip()
            if request_text:
                request = json.loads(request_text)
            else:
                request = {}
        except json.JSONDecodeError as e:
            self._status_label.setText(f"JSON Error: {e}")
            self._status_label.setStyleSheet("color: #ff4444;")
            return

        # Show calling status
        self._status_label.setText("Calling...")
        self._status_label.setStyleSheet("color: #00aaff;")
        self._call_btn.setEnabled(False)

        # Add timestamp to response
        timestamp = datetime.now().strftime('%H:%M:%S')
        self._response_text.append(f"\n--- {timestamp} ---")
        self._response_text.append(f"Calling {self._current_service}...")

        # Call service
        self._bridge.call_service(
            self._current_service,
            self._current_type,
            request
        )

    def _on_service_response(
        self,
        service: str,
        success: bool,
        response: str
    ) -> None:
        """Handle service response."""
        if service != self._current_service:
            return

        self._call_btn.setEnabled(True)

        if success:
            self._status_label.setText("Success")
            self._status_label.setStyleSheet("color: #00ff88;")
            self._response_text.append("SUCCESS:")
        else:
            self._status_label.setText("Failed")
            self._status_label.setStyleSheet("color: #ff4444;")
            self._response_text.append("FAILED:")

        self._response_text.append(response)

        # Auto-scroll
        scrollbar = self._response_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_clear_response(self) -> None:
        """Clear the response text."""
        self._response_text.clear()
        self._status_label.setText("")

    def showEvent(self, event) -> None:
        """Handle show event."""
        super().showEvent(event)
        if self._bridge.ros2_available:
            self._bridge.get_service_list()
