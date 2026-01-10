"""Topic Monitor Widget - Live ROS2 topic data visualization."""

from __future__ import annotations

from typing import Optional, List
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
    QSplitter,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Qt, QTimer

from .ros2_bridge import ROS2Bridge, PRIORITY_TOPICS, TopicInfo


class TopicMonitorWidget(QWidget):
    """Widget for monitoring ROS2 topic data in real-time."""

    def __init__(
        self,
        bridge: ROS2Bridge,
        parent: QWidget | None = None
    ):
        super().__init__(parent)

        self._bridge = bridge
        self._current_topic: Optional[str] = None
        self._is_streaming = False
        self._message_count = 0
        self._last_message_time: Optional[datetime] = None

        self._setup_ui()
        self._connect_signals()

        # Auto-refresh topic list
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_refresh_topics)
        self._refresh_timer.start(5000)  # Refresh every 5 seconds

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)

        # Topic selection
        select_layout = QHBoxLayout()

        select_layout.addWidget(QLabel("Topic:"))

        self._topic_combo = QComboBox()
        self._topic_combo.setMinimumWidth(250)
        self._topic_combo.currentTextChanged.connect(self._on_topic_changed)
        select_layout.addWidget(self._topic_combo, 1)

        self._refresh_btn = QPushButton("Refresh List")
        self._refresh_btn.clicked.connect(self._on_refresh_topics)
        select_layout.addWidget(self._refresh_btn)

        layout.addLayout(select_layout)

        # Topic info
        info_layout = QHBoxLayout()

        self._type_label = QLabel("Type: -")
        self._type_label.setStyleSheet("color: #808080;")
        info_layout.addWidget(self._type_label)

        info_layout.addStretch()

        self._rate_label = QLabel("Rate: -")
        self._rate_label.setStyleSheet("color: #808080;")
        info_layout.addWidget(self._rate_label)

        self._count_label = QLabel("Messages: 0")
        self._count_label.setStyleSheet("color: #808080;")
        info_layout.addWidget(self._count_label)

        layout.addLayout(info_layout)

        # Control buttons
        control_layout = QHBoxLayout()

        self._echo_btn = QPushButton("Echo Once")
        self._echo_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d4a5a;
                color: white;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3d6a7a;
            }
            QPushButton:disabled {
                background-color: #404040;
                color: #808080;
            }
        """)
        self._echo_btn.clicked.connect(self._on_echo_once)
        control_layout.addWidget(self._echo_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._on_clear)
        control_layout.addWidget(self._clear_btn)

        control_layout.addStretch()

        layout.addLayout(control_layout)

        # Data display
        data_group = QGroupBox("Topic Data")
        data_layout = QVBoxLayout(data_group)

        self._data_text = QTextEdit()
        self._data_text.setReadOnly(True)
        self._data_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                border: 1px solid #404040;
            }
        """)
        self._data_text.setPlaceholderText(
            "Select a topic and click 'Echo Once' to see data..."
        )
        data_layout.addWidget(self._data_text)

        layout.addWidget(data_group, 1)

        # Priority topics quick access
        priority_group = QGroupBox("Quick Access")
        priority_layout = QHBoxLayout(priority_group)

        for topic in PRIORITY_TOPICS[:5]:  # Show first 5
            btn = QPushButton(topic.split('/')[-1])
            btn.setToolTip(topic)
            btn.setMaximumWidth(100)
            btn.clicked.connect(lambda checked, t=topic: self._select_topic(t))
            priority_layout.addWidget(btn)

        priority_layout.addStretch()
        layout.addWidget(priority_group)

    def _connect_signals(self) -> None:
        """Connect bridge signals."""
        self._bridge.topics_updated.connect(self._on_topics_updated)
        self._bridge.topic_data_received.connect(self._on_topic_data)
        self._bridge.ros2_available_changed.connect(self._on_ros2_changed)

    def _on_ros2_changed(self, available: bool) -> None:
        """Handle ROS2 availability change."""
        self._echo_btn.setEnabled(available)
        if available:
            self._bridge.get_topic_list()

    def _on_refresh_topics(self) -> None:
        """Refresh the topic list."""
        if self._bridge.ros2_available:
            self._bridge.get_topic_list()

    def _on_topics_updated(self, topics: List[TopicInfo]) -> None:
        """Handle topic list update."""
        current = self._topic_combo.currentText()

        self._topic_combo.blockSignals(True)
        self._topic_combo.clear()

        # Add priority topics first
        for topic in PRIORITY_TOPICS:
            matching = [t for t in topics if t.name == topic]
            if matching:
                self._topic_combo.addItem(
                    f"{topic} [{matching[0].msg_type}]",
                    topic
                )

        # Add separator if we added priority topics
        if self._topic_combo.count() > 0:
            self._topic_combo.insertSeparator(self._topic_combo.count())

        # Add remaining topics
        for topic in topics:
            if topic.name not in PRIORITY_TOPICS:
                display = f"{topic.name} [{topic.msg_type}]" if topic.msg_type else topic.name
                self._topic_combo.addItem(display, topic.name)

        # Restore selection if possible
        if current:
            for i in range(self._topic_combo.count()):
                if self._topic_combo.itemData(i) == current:
                    self._topic_combo.setCurrentIndex(i)
                    break

        self._topic_combo.blockSignals(False)

    def _on_topic_changed(self, text: str) -> None:
        """Handle topic selection change."""
        # Get actual topic name from item data
        index = self._topic_combo.currentIndex()
        if index >= 0:
            topic = self._topic_combo.itemData(index)
            if topic:
                self._current_topic = topic
                self._update_topic_info()

    def _update_topic_info(self) -> None:
        """Update topic info display."""
        if not self._current_topic:
            return

        # Find topic info
        for topic_info in self._bridge.topics:
            if topic_info.name == self._current_topic:
                self._type_label.setText(f"Type: {topic_info.msg_type}")
                break

    def _select_topic(self, topic: str) -> None:
        """Select a topic programmatically."""
        for i in range(self._topic_combo.count()):
            if self._topic_combo.itemData(i) == topic:
                self._topic_combo.setCurrentIndex(i)
                break

    def _on_echo_once(self) -> None:
        """Echo the current topic once."""
        if not self._current_topic:
            return

        if not self._bridge.ros2_available:
            self._data_text.append("Error: ROS2 not available")
            return

        self._data_text.append(f"\n--- {datetime.now().strftime('%H:%M:%S')} ---")
        self._data_text.append(f"Echoing {self._current_topic}...")

        self._bridge.echo_topic(self._current_topic)

    def _on_topic_data(self, topic: str, data: str) -> None:
        """Handle incoming topic data."""
        if topic != self._current_topic:
            return

        self._message_count += 1
        self._last_message_time = datetime.now()

        self._count_label.setText(f"Messages: {self._message_count}")

        # Format and display data
        self._data_text.append(data.strip())

        # Auto-scroll to bottom
        scrollbar = self._data_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_clear(self) -> None:
        """Clear the data display."""
        self._data_text.clear()
        self._message_count = 0
        self._count_label.setText("Messages: 0")

    def showEvent(self, event) -> None:
        """Handle show event."""
        super().showEvent(event)
        if self._bridge.ros2_available:
            self._bridge.get_topic_list()

    def hideEvent(self, event) -> None:
        """Handle hide event."""
        super().hideEvent(event)
        # Stop any active streaming when hidden
        if self._current_topic:
            self._bridge.stop_echo_topic(self._current_topic)
