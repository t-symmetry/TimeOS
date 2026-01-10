"""HIL Configuration Dialog - Configure Hardware-in-the-Loop settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTabWidget,
    QWidget,
    QFormLayout,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal


@dataclass
class ModuleConfig:
    """Configuration for a single module."""
    name: str
    mode: str  # "emulated", "real", "disabled"
    connection_type: str  # "ni_daq", "labview", "serial", "tcp"
    address: str
    port: int
    enabled: bool


class HILConfigDialog(QDialog):
    """Dialog for configuring Hardware-in-the-Loop settings.

    Allows users to:
    - Set modules to real, emulated, or disabled
    - Configure connection parameters
    - Set up NI DAQ channels
    - Configure LabVIEW bridge
    """

    # Signals
    config_changed = Signal(dict)  # emits full config dict

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("HIL Configuration")
        self.setMinimumSize(600, 500)

        self._module_configs: dict[str, ModuleConfig] = {}
        self._init_default_configs()
        self._setup_ui()

    def _init_default_configs(self) -> None:
        """Initialize default module configurations."""
        modules = [
            ("field_generator", "Field Generator"),
            ("tdu", "Temporal Displacement Unit"),
            ("causality_monitor", "Causality Monitor"),
            ("anchor", "Anchor System"),
            ("safety", "Safety Interlocks"),
        ]

        for key, name in modules:
            self._module_configs[key] = ModuleConfig(
                name=name,
                mode="emulated",
                connection_type="ni_daq",
                address="Dev1",
                port=0,
                enabled=True,
            )

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Tab widget for different configuration sections
        tabs = QTabWidget()

        # Modules tab
        modules_tab = self._create_modules_tab()
        tabs.addTab(modules_tab, "Modules")

        # NI DAQ tab
        nidaq_tab = self._create_nidaq_tab()
        tabs.addTab(nidaq_tab, "NI DAQ")

        # LabVIEW tab
        labview_tab = self._create_labview_tab()
        tabs.addTab(labview_tab, "LabVIEW")

        # Safety tab
        safety_tab = self._create_safety_tab()
        tabs.addTab(safety_tab, "Safety")

        layout.addWidget(tabs)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._test_btn = QPushButton("Test Connections")
        self._test_btn.clicked.connect(self._on_test_connections)
        btn_layout.addWidget(self._test_btn)

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(self._apply_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        self._ok_btn = QPushButton("OK")
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self._ok_btn)

        layout.addLayout(btn_layout)

    def _create_modules_tab(self) -> QWidget:
        """Create the modules configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Module table
        self._modules_table = QTableWidget()
        self._modules_table.setColumnCount(5)
        self._modules_table.setHorizontalHeaderLabels([
            "Module", "Mode", "Connection", "Address", "Enabled"
        ])
        self._modules_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )

        self._populate_modules_table()
        layout.addWidget(self._modules_table)

        # Quick actions
        action_layout = QHBoxLayout()

        all_emulated_btn = QPushButton("All Emulated")
        all_emulated_btn.clicked.connect(lambda: self._set_all_mode("emulated"))
        action_layout.addWidget(all_emulated_btn)

        all_real_btn = QPushButton("All Real")
        all_real_btn.clicked.connect(lambda: self._set_all_mode("real"))
        action_layout.addWidget(all_real_btn)

        action_layout.addStretch()

        layout.addLayout(action_layout)

        return widget

    def _populate_modules_table(self) -> None:
        """Populate the modules table."""
        self._modules_table.setRowCount(len(self._module_configs))

        for row, (key, config) in enumerate(self._module_configs.items()):
            # Module name
            name_item = QTableWidgetItem(config.name)
            name_item.setData(Qt.ItemDataRole.UserRole, key)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._modules_table.setItem(row, 0, name_item)

            # Mode combo
            mode_combo = QComboBox()
            mode_combo.addItems(["emulated", "real", "disabled"])
            mode_combo.setCurrentText(config.mode)
            mode_combo.currentTextChanged.connect(
                lambda text, k=key: self._on_mode_changed(k, text)
            )
            self._modules_table.setCellWidget(row, 1, mode_combo)

            # Connection type combo
            conn_combo = QComboBox()
            conn_combo.addItems(["ni_daq", "labview", "serial", "tcp"])
            conn_combo.setCurrentText(config.connection_type)
            self._modules_table.setCellWidget(row, 2, conn_combo)

            # Address
            addr_edit = QLineEdit(config.address)
            self._modules_table.setCellWidget(row, 3, addr_edit)

            # Enabled checkbox
            enabled_cb = QCheckBox()
            enabled_cb.setChecked(config.enabled)
            self._modules_table.setCellWidget(row, 4, enabled_cb)

    def _set_all_mode(self, mode: str) -> None:
        """Set all modules to the same mode."""
        for row in range(self._modules_table.rowCount()):
            combo = self._modules_table.cellWidget(row, 1)
            if isinstance(combo, QComboBox):
                combo.setCurrentText(mode)

    def _on_mode_changed(self, key: str, mode: str) -> None:
        """Handle mode change for a module."""
        if key in self._module_configs:
            self._module_configs[key].mode = mode

    def _create_nidaq_tab(self) -> QWidget:
        """Create the NI DAQ configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Device settings
        device_group = QGroupBox("Device Settings")
        device_layout = QFormLayout(device_group)

        self._nidaq_device_edit = QLineEdit("Dev1")
        device_layout.addRow("Device Name:", self._nidaq_device_edit)

        self._nidaq_sample_rate = QSpinBox()
        self._nidaq_sample_rate.setRange(1, 1000000)
        self._nidaq_sample_rate.setValue(10000)
        self._nidaq_sample_rate.setSuffix(" Hz")
        device_layout.addRow("Sample Rate:", self._nidaq_sample_rate)

        layout.addWidget(device_group)

        # Channel mappings
        channels_group = QGroupBox("Channel Mappings")
        channels_layout = QVBoxLayout(channels_group)

        self._channels_table = QTableWidget()
        self._channels_table.setColumnCount(4)
        self._channels_table.setHorizontalHeaderLabels([
            "Signal", "Channel", "Range", "Type"
        ])
        self._channels_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )

        # Default channel mappings
        default_channels = [
            ("field_setpoint", "ao0", "±10V", "Analog Out"),
            ("field_readback", "ai0", "±10V", "Analog In"),
            ("temperature", "ai1", "0-10V", "Analog In"),
            ("interlock_in", "di0", "TTL", "Digital In"),
            ("interlock_out", "do0", "TTL", "Digital Out"),
            ("e_stop", "di1", "TTL", "Digital In"),
        ]

        self._channels_table.setRowCount(len(default_channels))
        for row, (signal, channel, range_, type_) in enumerate(default_channels):
            self._channels_table.setItem(row, 0, QTableWidgetItem(signal))
            self._channels_table.setItem(row, 1, QTableWidgetItem(channel))
            self._channels_table.setItem(row, 2, QTableWidgetItem(range_))
            self._channels_table.setItem(row, 3, QTableWidgetItem(type_))

        channels_layout.addWidget(self._channels_table)

        layout.addWidget(channels_group)

        # Simulation mode
        self._nidaq_simulate_cb = QCheckBox("Simulation Mode (no hardware)")
        self._nidaq_simulate_cb.setChecked(True)
        layout.addWidget(self._nidaq_simulate_cb)

        layout.addStretch()

        return widget

    def _create_labview_tab(self) -> QWidget:
        """Create the LabVIEW bridge configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Connection settings
        conn_group = QGroupBox("Connection Settings")
        conn_layout = QFormLayout(conn_group)

        self._lv_mode_combo = QComboBox()
        self._lv_mode_combo.addItems(["client", "server"])
        conn_layout.addRow("Mode:", self._lv_mode_combo)

        self._lv_host_edit = QLineEdit("localhost")
        conn_layout.addRow("Host:", self._lv_host_edit)

        self._lv_port_spin = QSpinBox()
        self._lv_port_spin.setRange(1024, 65535)
        self._lv_port_spin.setValue(5000)
        conn_layout.addRow("Port:", self._lv_port_spin)

        self._lv_timeout_spin = QSpinBox()
        self._lv_timeout_spin.setRange(1, 60)
        self._lv_timeout_spin.setValue(5)
        self._lv_timeout_spin.setSuffix(" s")
        conn_layout.addRow("Timeout:", self._lv_timeout_spin)

        layout.addWidget(conn_group)

        # Protocol settings
        proto_group = QGroupBox("Protocol")
        proto_layout = QFormLayout(proto_group)

        self._lv_heartbeat_spin = QSpinBox()
        self._lv_heartbeat_spin.setRange(100, 10000)
        self._lv_heartbeat_spin.setValue(1000)
        self._lv_heartbeat_spin.setSuffix(" ms")
        proto_layout.addRow("Heartbeat:", self._lv_heartbeat_spin)

        self._lv_buffer_spin = QSpinBox()
        self._lv_buffer_spin.setRange(1024, 1048576)
        self._lv_buffer_spin.setValue(65536)
        self._lv_buffer_spin.setSuffix(" bytes")
        proto_layout.addRow("Buffer Size:", self._lv_buffer_spin)

        layout.addWidget(proto_group)

        # Status
        status_group = QGroupBox("Status")
        status_layout = QHBoxLayout(status_group)

        self._lv_status_label = QLabel("Disconnected")
        self._lv_status_label.setStyleSheet("color: #666666;")
        status_layout.addWidget(self._lv_status_label)

        status_layout.addStretch()

        self._lv_connect_btn = QPushButton("Connect")
        self._lv_connect_btn.clicked.connect(self._on_labview_connect)
        status_layout.addWidget(self._lv_connect_btn)

        layout.addWidget(status_group)

        layout.addStretch()

        return widget

    def _create_safety_tab(self) -> QWidget:
        """Create the safety configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Interlock settings
        interlock_group = QGroupBox("Interlock Settings")
        interlock_layout = QFormLayout(interlock_group)

        self._watchdog_spin = QSpinBox()
        self._watchdog_spin.setRange(100, 10000)
        self._watchdog_spin.setValue(1000)
        self._watchdog_spin.setSuffix(" ms")
        interlock_layout.addRow("Watchdog Timeout:", self._watchdog_spin)

        self._heartbeat_required_cb = QCheckBox("Require heartbeat")
        self._heartbeat_required_cb.setChecked(True)
        interlock_layout.addRow("", self._heartbeat_required_cb)

        layout.addWidget(interlock_group)

        # Limits
        limits_group = QGroupBox("Safety Limits")
        limits_layout = QFormLayout(limits_group)

        self._max_field_spin = QSpinBox()
        self._max_field_spin.setRange(1, 100)
        self._max_field_spin.setValue(15)
        self._max_field_spin.setSuffix(" T")
        limits_layout.addRow("Max Field:", self._max_field_spin)

        self._max_temp_spin = QSpinBox()
        self._max_temp_spin.setRange(1, 300)
        self._max_temp_spin.setValue(10)
        self._max_temp_spin.setSuffix(" K")
        limits_layout.addRow("Max Temperature:", self._max_temp_spin)

        self._max_power_spin = QSpinBox()
        self._max_power_spin.setRange(100, 100000)
        self._max_power_spin.setValue(50000)
        self._max_power_spin.setSuffix(" W")
        limits_layout.addRow("Max Power:", self._max_power_spin)

        layout.addWidget(limits_group)

        # E-Stop
        estop_group = QGroupBox("Emergency Stop")
        estop_layout = QVBoxLayout(estop_group)

        self._estop_hw_cb = QCheckBox("Hardware E-Stop enabled")
        self._estop_hw_cb.setChecked(True)
        estop_layout.addWidget(self._estop_hw_cb)

        self._estop_sw_cb = QCheckBox("Software E-Stop enabled")
        self._estop_sw_cb.setChecked(True)
        estop_layout.addWidget(self._estop_sw_cb)

        layout.addWidget(estop_group)

        layout.addStretch()

        return widget

    def _on_test_connections(self) -> None:
        """Test all configured connections."""
        results = []

        for key, config in self._module_configs.items():
            if config.mode == "real" and config.enabled:
                # Would actually test connection here
                results.append(f"{config.name}: Simulated OK")
            elif config.mode == "emulated" and config.enabled:
                results.append(f"{config.name}: Emulated (no test needed)")
            else:
                results.append(f"{config.name}: Disabled")

        QMessageBox.information(
            self,
            "Connection Test Results",
            "\n".join(results),
        )

    def _on_labview_connect(self) -> None:
        """Test LabVIEW connection."""
        host = self._lv_host_edit.text()
        port = self._lv_port_spin.value()

        # Simulate connection attempt
        self._lv_status_label.setText(f"Connecting to {host}:{port}...")
        self._lv_status_label.setStyleSheet("color: #ffaa00;")

        # In real implementation, would attempt actual connection
        # For now, just show simulated result
        self._lv_status_label.setText("Connected (simulated)")
        self._lv_status_label.setStyleSheet("color: #00ff88;")

    def _on_apply(self) -> None:
        """Apply configuration changes."""
        config = self.get_config()
        self.config_changed.emit(config)

    def _on_ok(self) -> None:
        """Apply and close."""
        self._on_apply()
        self.accept()

    def get_config(self) -> dict:
        """Get the current configuration as a dictionary."""
        # Update module configs from table
        for row in range(self._modules_table.rowCount()):
            name_item = self._modules_table.item(row, 0)
            key = name_item.data(Qt.ItemDataRole.UserRole)

            mode_combo = self._modules_table.cellWidget(row, 1)
            conn_combo = self._modules_table.cellWidget(row, 2)
            addr_edit = self._modules_table.cellWidget(row, 3)
            enabled_cb = self._modules_table.cellWidget(row, 4)

            if key in self._module_configs:
                self._module_configs[key].mode = mode_combo.currentText()
                self._module_configs[key].connection_type = conn_combo.currentText()
                self._module_configs[key].address = addr_edit.text()
                self._module_configs[key].enabled = enabled_cb.isChecked()

        return {
            "modules": {
                key: {
                    "name": cfg.name,
                    "mode": cfg.mode,
                    "connection_type": cfg.connection_type,
                    "address": cfg.address,
                    "port": cfg.port,
                    "enabled": cfg.enabled,
                }
                for key, cfg in self._module_configs.items()
            },
            "nidaq": {
                "device": self._nidaq_device_edit.text(),
                "sample_rate": self._nidaq_sample_rate.value(),
                "simulate": self._nidaq_simulate_cb.isChecked(),
            },
            "labview": {
                "mode": self._lv_mode_combo.currentText(),
                "host": self._lv_host_edit.text(),
                "port": self._lv_port_spin.value(),
                "timeout": self._lv_timeout_spin.value(),
                "heartbeat": self._lv_heartbeat_spin.value(),
                "buffer_size": self._lv_buffer_spin.value(),
            },
            "safety": {
                "watchdog_timeout": self._watchdog_spin.value(),
                "heartbeat_required": self._heartbeat_required_cb.isChecked(),
                "max_field": self._max_field_spin.value(),
                "max_temperature": self._max_temp_spin.value(),
                "max_power": self._max_power_spin.value(),
                "hardware_estop": self._estop_hw_cb.isChecked(),
                "software_estop": self._estop_sw_cb.isChecked(),
            },
        }

    def set_config(self, config: dict) -> None:
        """Set configuration from a dictionary."""
        # Modules
        if "modules" in config:
            for key, mod_cfg in config["modules"].items():
                if key in self._module_configs:
                    self._module_configs[key].mode = mod_cfg.get("mode", "emulated")
                    self._module_configs[key].connection_type = mod_cfg.get(
                        "connection_type", "ni_daq"
                    )
                    self._module_configs[key].address = mod_cfg.get("address", "Dev1")
                    self._module_configs[key].enabled = mod_cfg.get("enabled", True)
            self._populate_modules_table()

        # NI DAQ
        if "nidaq" in config:
            nidaq = config["nidaq"]
            self._nidaq_device_edit.setText(nidaq.get("device", "Dev1"))
            self._nidaq_sample_rate.setValue(nidaq.get("sample_rate", 10000))
            self._nidaq_simulate_cb.setChecked(nidaq.get("simulate", True))

        # LabVIEW
        if "labview" in config:
            lv = config["labview"]
            self._lv_mode_combo.setCurrentText(lv.get("mode", "client"))
            self._lv_host_edit.setText(lv.get("host", "localhost"))
            self._lv_port_spin.setValue(lv.get("port", 5000))
            self._lv_timeout_spin.setValue(lv.get("timeout", 5))
            self._lv_heartbeat_spin.setValue(lv.get("heartbeat", 1000))
            self._lv_buffer_spin.setValue(lv.get("buffer_size", 65536))

        # Safety
        if "safety" in config:
            safety = config["safety"]
            self._watchdog_spin.setValue(safety.get("watchdog_timeout", 1000))
            self._heartbeat_required_cb.setChecked(
                safety.get("heartbeat_required", True)
            )
            self._max_field_spin.setValue(safety.get("max_field", 15))
            self._max_temp_spin.setValue(safety.get("max_temperature", 10))
            self._max_power_spin.setValue(safety.get("max_power", 50000))
            self._estop_hw_cb.setChecked(safety.get("hardware_estop", True))
            self._estop_sw_cb.setChecked(safety.get("software_estop", True))
