"""Hardware-in-the-Loop (HIL) Manager for TimeOS.

Manages the mixing of real and emulated hardware components,
providing a unified interface regardless of the underlying
implementation.

Supports:
- Dynamic module configuration
- Runtime switching between real/emulated
- Safety interlock enforcement
- Data routing between modules
- Failure injection for testing
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)


class ModuleType(Enum):
    """Hardware module types."""
    FIELD_GENERATOR = "field_generator"
    TDU = "tdu"
    CAUSALITY_MONITOR = "causality"
    SAFETY = "safety"
    THERMAL = "thermal"
    SENSORS = "sensors"
    DAQ = "daq"
    LABVIEW = "labview"


class ModuleMode(Enum):
    """Module operation mode."""
    DISABLED = auto()
    SIMULATED = auto()  # Pure software
    EMULATED = auto()   # Realistic behavior
    REAL = auto()       # Actual hardware


class ModuleState(Enum):
    """Module runtime state."""
    OFFLINE = auto()
    INITIALIZING = auto()
    READY = auto()
    ACTIVE = auto()
    ERROR = auto()
    FAULT = auto()


class HardwareModule(Protocol):
    """Protocol for hardware modules."""

    def initialize(self) -> bool:
        """Initialize the module."""
        ...

    def shutdown(self) -> None:
        """Shutdown the module."""
        ...

    def get_status(self) -> dict[str, Any]:
        """Get module status."""
        ...


@dataclass
class ModuleConfig:
    """Configuration for a single module.

    Attributes:
        module_type: Type of module
        mode: Operation mode
        driver_class: Class to instantiate for this module
        driver_params: Parameters for driver constructor
        enabled: Whether module is enabled
        priority: Initialization priority (lower = first)
    """
    module_type: ModuleType
    mode: ModuleMode = ModuleMode.EMULATED
    driver_class: type | None = None
    driver_params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 100

    # Runtime
    instance: Any = None
    state: ModuleState = ModuleState.OFFLINE
    last_error: str = ""


@dataclass
class HILConfig:
    """Configuration for HIL system.

    Attributes:
        modules: Module configurations
        safety_critical: Whether to enforce safety interlocks
        allow_mixed_mode: Allow mixing real and emulated modules
        watchdog_timeout: Watchdog timeout in seconds
        log_path: Path for data logging
    """
    modules: dict[ModuleType, ModuleConfig] = field(default_factory=dict)
    safety_critical: bool = True
    allow_mixed_mode: bool = True
    watchdog_timeout: float = 5.0
    log_path: str = "/tmp/timeos_hil"

    def add_module(
        self,
        module_type: ModuleType,
        mode: ModuleMode = ModuleMode.EMULATED,
        driver_class: type | None = None,
        **params,
    ) -> "HILConfig":
        """Add a module configuration.

        Args:
            module_type: Type of module
            mode: Operation mode
            driver_class: Driver class
            **params: Driver parameters

        Returns:
            Self for chaining
        """
        self.modules[module_type] = ModuleConfig(
            module_type=module_type,
            mode=mode,
            driver_class=driver_class,
            driver_params=params,
        )
        return self


@dataclass
class SafetyInterlock:
    """Safety interlock definition.

    Attributes:
        name: Interlock name
        condition: Function that returns True if interlock is tripped
        action: Function to execute when tripped
        severity: 1=warning, 2=stop, 3=emergency
        modules: Affected modules
    """
    name: str
    condition: Callable[[], bool]
    action: Callable[[], None]
    severity: int = 2
    modules: list[ModuleType] = field(default_factory=list)

    # Runtime
    tripped: bool = False
    trip_time: float = 0.0
    trip_count: int = 0


class HILManager:
    """Hardware-in-the-Loop system manager.

    Coordinates real and emulated hardware modules, enforces
    safety interlocks, and provides a unified interface.

    Example usage:
        # Configure system
        config = HILConfig(safety_critical=True)
        config.add_module(
            ModuleType.FIELD_GENERATOR,
            mode=ModuleMode.EMULATED,
        )
        config.add_module(
            ModuleType.DAQ,
            mode=ModuleMode.REAL,
            driver_class=NIDAQDriver,
            device_id="Dev1",
        )

        # Create manager
        manager = HILManager(config)

        # Initialize
        manager.initialize()

        # Access modules
        field_gen = manager.get_module(ModuleType.FIELD_GENERATOR)
        field_gen.set_field(5.0)

        # Shutdown
        manager.shutdown()
    """

    def __init__(self, config: HILConfig):
        """Initialize HIL manager.

        Args:
            config: System configuration
        """
        self._config = config
        self._lock = threading.RLock()
        self._initialized = False
        self._running = False

        # Safety
        self._interlocks: list[SafetyInterlock] = []
        self._estop_active = False
        self._safe_to_operate = True

        # Watchdog
        self._watchdog_thread: threading.Thread | None = None
        self._last_activity: dict[ModuleType, float] = {}

        # State callbacks
        self._state_callbacks: list[Callable[[ModuleType, ModuleState], None]] = []
        self._safety_callbacks: list[Callable[[str, int], None]] = []

        # Statistics
        self._stats = {
            "init_time": 0.0,
            "uptime": 0.0,
            "interlock_trips": 0,
            "errors": 0,
        }

        # Register default interlocks
        self._register_default_interlocks()

    @property
    def config(self) -> HILConfig:
        """Get configuration."""
        return self._config

    @property
    def is_initialized(self) -> bool:
        """Check if system is initialized."""
        return self._initialized

    @property
    def is_safe(self) -> bool:
        """Check if system is safe to operate."""
        return self._safe_to_operate and not self._estop_active

    @property
    def estop_active(self) -> bool:
        """Check if E-stop is active."""
        return self._estop_active

    def on_state_change(
        self,
        callback: Callable[[ModuleType, ModuleState], None],
    ) -> None:
        """Register state change callback."""
        self._state_callbacks.append(callback)

    def on_safety_event(
        self,
        callback: Callable[[str, int], None],
    ) -> None:
        """Register safety event callback."""
        self._safety_callbacks.append(callback)

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def initialize(self) -> bool:
        """Initialize all configured modules.

        Returns:
            True if all modules initialized successfully
        """
        with self._lock:
            if self._initialized:
                return True

            start_time = time.time()
            logger.info("Initializing HIL system...")

            # Sort modules by priority
            modules = sorted(
                self._config.modules.values(),
                key=lambda m: m.priority,
            )

            # Initialize each module
            success = True
            for module_config in modules:
                if not module_config.enabled:
                    continue

                if not self._init_module(module_config):
                    success = False
                    if self._config.safety_critical:
                        logger.error("Safety-critical init failure, aborting")
                        break

            if success:
                self._initialized = True
                self._running = True
                self._stats["init_time"] = time.time() - start_time

                # Start watchdog
                self._start_watchdog()

                logger.info(
                    f"HIL system initialized in {self._stats['init_time']:.2f}s"
                )
            else:
                # Shutdown any initialized modules
                self.shutdown()

            return success

    def shutdown(self) -> None:
        """Shutdown all modules."""
        with self._lock:
            logger.info("Shutting down HIL system...")

            self._running = False

            # Stop watchdog
            if self._watchdog_thread and self._watchdog_thread.is_alive():
                self._watchdog_thread.join(timeout=2.0)

            # Shutdown in reverse priority order
            modules = sorted(
                self._config.modules.values(),
                key=lambda m: -m.priority,
            )

            for module_config in modules:
                if module_config.instance:
                    self._shutdown_module(module_config)

            self._initialized = False
            logger.info("HIL system shutdown complete")

    def _init_module(self, config: ModuleConfig) -> bool:
        """Initialize a single module.

        Args:
            config: Module configuration

        Returns:
            True if successful
        """
        config.state = ModuleState.INITIALIZING
        self._notify_state_change(config.module_type, config.state)

        try:
            # Get driver class based on mode
            driver_class = config.driver_class
            if driver_class is None:
                driver_class = self._get_default_driver(config)

            if driver_class is None:
                logger.warning(f"No driver for {config.module_type.value}, skipping")
                config.state = ModuleState.OFFLINE
                return True

            # Create instance
            logger.debug(f"Creating {config.module_type.value} ({config.mode.name})")
            instance = driver_class(**config.driver_params)

            # Initialize
            if hasattr(instance, "initialize"):
                if not instance.initialize():
                    raise RuntimeError("Initialize returned False")

            config.instance = instance
            config.state = ModuleState.READY
            self._last_activity[config.module_type] = time.time()

            self._notify_state_change(config.module_type, config.state)
            logger.info(f"Initialized: {config.module_type.value}")
            return True

        except Exception as e:
            config.state = ModuleState.ERROR
            config.last_error = str(e)
            self._stats["errors"] += 1

            self._notify_state_change(config.module_type, config.state)
            logger.error(f"Failed to init {config.module_type.value}: {e}")
            return False

    def _shutdown_module(self, config: ModuleConfig) -> None:
        """Shutdown a single module.

        Args:
            config: Module configuration
        """
        try:
            if hasattr(config.instance, "shutdown"):
                config.instance.shutdown()
            elif hasattr(config.instance, "disconnect"):
                config.instance.disconnect()

            logger.debug(f"Shutdown: {config.module_type.value}")

        except Exception as e:
            logger.error(f"Shutdown error for {config.module_type.value}: {e}")

        finally:
            config.instance = None
            config.state = ModuleState.OFFLINE
            self._notify_state_change(config.module_type, config.state)

    def _get_default_driver(self, config: ModuleConfig) -> type | None:
        """Get default driver class for module.

        Args:
            config: Module configuration

        Returns:
            Driver class or None
        """
        # Import drivers lazily
        if config.mode == ModuleMode.EMULATED:
            if config.module_type == ModuleType.FIELD_GENERATOR:
                from timeos.hardware.drivers.emulated import EmulatedFieldGenerator
                return EmulatedFieldGenerator

            elif config.module_type == ModuleType.TDU:
                from timeos.hardware.drivers.emulated import EmulatedTDU
                return EmulatedTDU

        elif config.mode == ModuleMode.REAL:
            if config.module_type == ModuleType.DAQ:
                from timeos.hardware.drivers.real import NIDAQDriver
                return NIDAQDriver

            elif config.module_type == ModuleType.LABVIEW:
                from timeos.hardware.drivers.real import LabVIEWBridge
                return LabVIEWBridge

        return None

    # =========================================================================
    # Module Access
    # =========================================================================

    def get_module(self, module_type: ModuleType) -> Any | None:
        """Get a module instance.

        Args:
            module_type: Type of module

        Returns:
            Module instance or None
        """
        config = self._config.modules.get(module_type)
        if config:
            return config.instance
        return None

    def get_module_state(self, module_type: ModuleType) -> ModuleState:
        """Get module state.

        Args:
            module_type: Type of module

        Returns:
            Module state
        """
        config = self._config.modules.get(module_type)
        if config:
            return config.state
        return ModuleState.OFFLINE

    def get_module_mode(self, module_type: ModuleType) -> ModuleMode:
        """Get module mode.

        Args:
            module_type: Type of module

        Returns:
            Module mode
        """
        config = self._config.modules.get(module_type)
        if config:
            return config.mode
        return ModuleMode.DISABLED

    def set_module_enabled(
        self,
        module_type: ModuleType,
        enabled: bool,
    ) -> bool:
        """Enable or disable a module.

        Args:
            module_type: Type of module
            enabled: Whether to enable

        Returns:
            True if successful
        """
        config = self._config.modules.get(module_type)
        if not config:
            return False

        with self._lock:
            if enabled and not config.enabled:
                config.enabled = True
                if self._initialized:
                    return self._init_module(config)

            elif not enabled and config.enabled:
                if config.instance:
                    self._shutdown_module(config)
                config.enabled = False

            return True

    def get_status(self) -> dict[str, Any]:
        """Get overall system status.

        Returns:
            Status dictionary
        """
        modules_status = {}
        for mod_type, config in self._config.modules.items():
            modules_status[mod_type.value] = {
                "mode": config.mode.name,
                "state": config.state.name,
                "enabled": config.enabled,
                "error": config.last_error,
            }

        interlocks_status = [
            {
                "name": il.name,
                "tripped": il.tripped,
                "severity": il.severity,
                "trip_count": il.trip_count,
            }
            for il in self._interlocks
        ]

        return {
            "initialized": self._initialized,
            "running": self._running,
            "safe_to_operate": self._safe_to_operate,
            "estop_active": self._estop_active,
            "modules": modules_status,
            "interlocks": interlocks_status,
            "stats": dict(self._stats),
        }

    # =========================================================================
    # Safety
    # =========================================================================

    def add_interlock(self, interlock: SafetyInterlock) -> None:
        """Add a safety interlock.

        Args:
            interlock: Interlock definition
        """
        self._interlocks.append(interlock)
        logger.debug(f"Added interlock: {interlock.name}")

    def check_interlocks(self) -> list[str]:
        """Check all interlocks.

        Returns:
            List of tripped interlock names
        """
        tripped = []

        for interlock in self._interlocks:
            try:
                if interlock.condition():
                    if not interlock.tripped:
                        interlock.tripped = True
                        interlock.trip_time = time.time()
                        interlock.trip_count += 1
                        self._stats["interlock_trips"] += 1

                        logger.warning(
                            f"Interlock tripped: {interlock.name} "
                            f"(severity {interlock.severity})"
                        )

                        # Execute action
                        try:
                            interlock.action()
                        except Exception as e:
                            logger.error(f"Interlock action error: {e}")

                        # Notify callbacks
                        for cb in self._safety_callbacks:
                            try:
                                cb(interlock.name, interlock.severity)
                            except Exception as e:
                                logger.error(f"Safety callback error: {e}")

                    tripped.append(interlock.name)

                else:
                    interlock.tripped = False

            except Exception as e:
                logger.error(f"Interlock check error ({interlock.name}): {e}")

        self._safe_to_operate = len(tripped) == 0
        return tripped

    def emergency_stop(self, reason: str = "Manual E-stop") -> None:
        """Trigger emergency stop.

        Args:
            reason: Reason for E-stop
        """
        logger.critical(f"EMERGENCY STOP: {reason}")

        self._estop_active = True
        self._safe_to_operate = False

        # Stop all modules
        for config in self._config.modules.values():
            if config.instance:
                try:
                    if hasattr(config.instance, "emergency_stop"):
                        config.instance.emergency_stop()
                    elif hasattr(config.instance, "shutdown"):
                        config.instance.shutdown()
                except Exception as e:
                    logger.error(f"E-stop error for {config.module_type.value}: {e}")

                config.state = ModuleState.FAULT

        # Notify callbacks
        for cb in self._safety_callbacks:
            try:
                cb("EMERGENCY_STOP", 3)
            except Exception as e:
                logger.error(f"Safety callback error: {e}")

    def reset_estop(self) -> bool:
        """Reset emergency stop.

        Returns:
            True if reset successful
        """
        # Check all interlocks are clear
        tripped = self.check_interlocks()
        if tripped:
            logger.warning(f"Cannot reset E-stop, interlocks active: {tripped}")
            return False

        self._estop_active = False
        self._safe_to_operate = True

        logger.info("E-stop reset")
        return True

    def _register_default_interlocks(self) -> None:
        """Register default safety interlocks."""
        # Watchdog interlock
        self.add_interlock(SafetyInterlock(
            name="watchdog_timeout",
            condition=self._check_watchdog,
            action=lambda: self.emergency_stop("Watchdog timeout"),
            severity=3,
        ))

    def _check_watchdog(self) -> bool:
        """Check if any module has timed out."""
        now = time.time()
        for mod_type, last in self._last_activity.items():
            if now - last > self._config.watchdog_timeout:
                config = self._config.modules.get(mod_type)
                if config and config.state == ModuleState.ACTIVE:
                    logger.warning(f"Watchdog timeout: {mod_type.value}")
                    return True
        return False

    # =========================================================================
    # Background Tasks
    # =========================================================================

    def _start_watchdog(self) -> None:
        """Start watchdog thread."""
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name="HIL_Watchdog",
            daemon=True,
        )
        self._watchdog_thread.start()

    def _watchdog_loop(self) -> None:
        """Watchdog loop."""
        while self._running:
            time.sleep(1.0)

            if not self._estop_active:
                self.check_interlocks()

            # Update uptime
            self._stats["uptime"] = time.time() - (
                self._stats.get("init_time", 0) or time.time()
            )

    def _notify_state_change(
        self,
        module_type: ModuleType,
        state: ModuleState,
    ) -> None:
        """Notify state change callbacks.

        Args:
            module_type: Module that changed
            state: New state
        """
        for cb in self._state_callbacks:
            try:
                cb(module_type, state)
            except Exception as e:
                logger.error(f"State callback error: {e}")

    # =========================================================================
    # Activity Tracking
    # =========================================================================

    def touch(self, module_type: ModuleType) -> None:
        """Update activity timestamp for module.

        Call this from module operations to prevent watchdog timeout.

        Args:
            module_type: Module that is active
        """
        self._last_activity[module_type] = time.time()
