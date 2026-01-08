"""Thermal Model - Temperature simulation for superconducting magnets.

Models thermal behavior of superconducting field coils including:
- Heat dissipation from current flow
- Cooling system capacity
- Thermal runaway (quench) conditions
- Temperature-dependent critical current
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import time


class ThermalState(Enum):
    """Thermal state of the superconducting system."""

    COLD = "cold"  # Below critical temp, superconducting
    WARMING = "warming"  # Temperature rising
    CRITICAL = "critical"  # Near quench threshold
    QUENCH = "quench"  # Superconductivity lost
    RECOVERY = "recovery"  # Cooling down after quench


@dataclass
class ThermalConfig:
    """Thermal model configuration.

    Attributes:
        critical_temp_kelvin: Temperature above which superconductivity is lost
        operating_temp_kelvin: Normal operating temperature
        ambient_temp_kelvin: Ambient/room temperature
        cooling_power_watts: Maximum cooling capacity
        thermal_mass_jk: Heat capacity (Joules per Kelvin)
        heat_leak_wk: Thermal conductivity to ambient (Watts per Kelvin)
        quench_threshold: Temperature fraction of T_c that triggers quench warning
        recovery_threshold: Temperature fraction for recovery to normal
    """

    critical_temp_kelvin: float = 9.2  # Niobium-titanium T_c
    operating_temp_kelvin: float = 4.2  # Liquid helium temp
    ambient_temp_kelvin: float = 293.0  # Room temperature
    cooling_power_watts: float = 50.0  # Cryocooler capacity
    thermal_mass_jk: float = 1000.0  # Heat capacity
    heat_leak_wk: float = 0.1  # Parasitic heat load coefficient
    quench_threshold: float = 0.9  # 90% of T_c triggers warning
    recovery_threshold: float = 0.5  # 50% of T_c for recovery


@dataclass
class ThermalStatus:
    """Current thermal status.

    Attributes:
        temperature_kelvin: Current temperature
        state: Current thermal state
        quench_risk: Risk of quench (0.0 to 1.0)
        cooling_load_watts: Current cooling requirement
        cooling_headroom_watts: Available cooling margin
        time_to_quench_seconds: Estimated time to quench at current rate
    """

    temperature_kelvin: float = 4.2
    state: ThermalState = ThermalState.COLD
    quench_risk: float = 0.0
    cooling_load_watts: float = 0.0
    cooling_headroom_watts: float = 50.0
    time_to_quench_seconds: float | None = None


class ThermalModel:
    """Thermal simulation for superconducting magnet systems.

    Models the thermal behavior of a superconducting magnet including:
    - Ohmic heating (zero in superconducting state)
    - AC losses from changing fields
    - Heat leak from environment
    - Cryogenic cooling
    - Quench propagation

    The model uses a simple first-order thermal equation:
    dT/dt = (Q_in - Q_cool) / C

    Where:
    - Q_in = heat input (AC losses + heat leak)
    - Q_cool = cooling power
    - C = thermal mass
    """

    def __init__(self, config: ThermalConfig | None = None):
        """Initialize thermal model.

        Args:
            config: Thermal configuration (uses defaults if None)
        """
        self._config = config or ThermalConfig()
        self._temperature = self._config.operating_temp_kelvin
        self._state = ThermalState.COLD
        self._last_update = time.monotonic()

        # Internal state
        self._current_amps = 0.0
        self._field_rate_ts = 0.0  # dB/dt for AC losses
        self._quenched = False
        self._cooling_active = True

        # History for trend analysis
        self._temp_history: list[tuple[float, float]] = []
        self._max_history = 100

    @property
    def temperature(self) -> float:
        """Current temperature in Kelvin."""
        return self._temperature

    @property
    def state(self) -> ThermalState:
        """Current thermal state."""
        return self._state

    @property
    def is_superconducting(self) -> bool:
        """Check if still superconducting."""
        return self._temperature < self._config.critical_temp_kelvin and not self._quenched

    def set_current(self, current_amps: float) -> None:
        """Set magnet current (affects heating if not superconducting)."""
        self._current_amps = current_amps

    def set_field_rate(self, rate_ts: float) -> None:
        """Set field change rate for AC loss calculation."""
        self._field_rate_ts = rate_ts

    def set_cooling(self, active: bool) -> None:
        """Enable/disable active cooling."""
        self._cooling_active = active

    def update(self, dt: float | None = None) -> ThermalStatus:
        """Update thermal state.

        Args:
            dt: Time step in seconds (None = use real elapsed time)

        Returns:
            Current thermal status
        """
        now = time.monotonic()
        if dt is None:
            dt = now - self._last_update
        self._last_update = now

        # Clamp dt to reasonable range
        dt = max(0.0, min(dt, 1.0))

        # Calculate heat inputs
        heat_in = self._calculate_heat_input()

        # Calculate cooling
        heat_out = self._calculate_cooling()

        # Net heat flow
        net_heat = heat_in - heat_out

        # Temperature change: dT = Q * dt / C
        dT = (net_heat * dt) / self._config.thermal_mass_jk
        self._temperature += dT

        # Clamp temperature
        self._temperature = max(
            self._config.operating_temp_kelvin * 0.5,  # Can't go too cold
            min(self._temperature, self._config.ambient_temp_kelvin)  # Can't exceed ambient
        )

        # Record history
        self._temp_history.append((now, self._temperature))
        if len(self._temp_history) > self._max_history:
            self._temp_history.pop(0)

        # Update state
        self._update_state()

        # Calculate status
        return self._calculate_status(heat_in, heat_out)

    def _calculate_heat_input(self) -> float:
        """Calculate total heat input in Watts."""
        heat = 0.0

        # Heat leak from environment
        temp_diff = self._config.ambient_temp_kelvin - self._temperature
        heat += self._config.heat_leak_wk * temp_diff

        # AC losses from changing field (proportional to dB/dt squared)
        # Q_ac = k * (dB/dt)^2 * V
        ac_loss_factor = 10.0  # W/(T/s)^2
        heat += ac_loss_factor * self._field_rate_ts ** 2

        # Ohmic heating if not superconducting
        if not self.is_superconducting:
            # Resistance appears when normal
            resistance = 0.01  # Ohms (rough estimate)
            heat += self._current_amps ** 2 * resistance

        return heat

    def _calculate_cooling(self) -> float:
        """Calculate cooling power in Watts."""
        if not self._cooling_active:
            return 0.0

        # Cooling is most effective at higher temperatures
        # Models real cryocooler behavior
        temp_ratio = self._temperature / self._config.operating_temp_kelvin
        efficiency = min(1.0, temp_ratio - 1.0) if temp_ratio > 1.0 else 0.0

        # Base cooling power plus efficiency factor
        base_cooling = self._config.cooling_power_watts * 0.3  # Minimum cooling
        variable_cooling = self._config.cooling_power_watts * 0.7 * efficiency

        return base_cooling + variable_cooling

    def _update_state(self) -> None:
        """Update thermal state based on temperature."""
        t_ratio = self._temperature / self._config.critical_temp_kelvin

        if self._quenched:
            if t_ratio < self._config.recovery_threshold:
                self._quenched = False
                self._state = ThermalState.COLD
            elif self._temperature < self._config.critical_temp_kelvin:
                self._state = ThermalState.RECOVERY
            else:
                self._state = ThermalState.QUENCH
        else:
            if t_ratio >= 1.0:
                self._quenched = True
                self._state = ThermalState.QUENCH
            elif t_ratio >= self._config.quench_threshold:
                self._state = ThermalState.CRITICAL
            elif self._is_warming():
                self._state = ThermalState.WARMING
            else:
                self._state = ThermalState.COLD

    def _is_warming(self) -> bool:
        """Check if temperature is trending upward."""
        if len(self._temp_history) < 5:
            return False
        recent = self._temp_history[-5:]
        temps = [t for _, t in recent]
        return temps[-1] > temps[0] + 0.1  # Rising by more than 0.1K

    def _calculate_status(self, heat_in: float, heat_out: float) -> ThermalStatus:
        """Calculate current thermal status."""
        t_ratio = self._temperature / self._config.critical_temp_kelvin

        # Quench risk increases exponentially near T_c
        if t_ratio < 0.5:
            quench_risk = 0.0
        elif t_ratio < self._config.quench_threshold:
            quench_risk = (t_ratio - 0.5) / (self._config.quench_threshold - 0.5) * 0.3
        else:
            quench_risk = 0.3 + 0.7 * (t_ratio - self._config.quench_threshold) / (1.0 - self._config.quench_threshold)

        quench_risk = min(1.0, max(0.0, quench_risk))

        # Cooling headroom
        headroom = heat_out - heat_in

        # Time to quench estimate
        time_to_quench = None
        if heat_in > heat_out and self._temperature < self._config.critical_temp_kelvin:
            temp_margin = self._config.critical_temp_kelvin - self._temperature
            heat_rate = heat_in - heat_out
            # Time = (T_c - T) * C / Q_net
            time_to_quench = (temp_margin * self._config.thermal_mass_jk) / heat_rate

        return ThermalStatus(
            temperature_kelvin=self._temperature,
            state=self._state,
            quench_risk=quench_risk,
            cooling_load_watts=heat_in,
            cooling_headroom_watts=headroom,
            time_to_quench_seconds=time_to_quench,
        )

    def force_quench(self) -> None:
        """Force a quench condition (for testing)."""
        self._temperature = self._config.critical_temp_kelvin * 1.1
        self._quenched = True
        self._state = ThermalState.QUENCH

    def reset(self) -> None:
        """Reset to cold operating state."""
        self._temperature = self._config.operating_temp_kelvin
        self._quenched = False
        self._state = ThermalState.COLD
        self._temp_history.clear()
