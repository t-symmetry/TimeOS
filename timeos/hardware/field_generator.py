"""Field Generator - Electromagnetic field manipulation for temporal operations.

This module handles the generation and control of electromagnetic fields
required for temporal displacement operations.

Theoretical basis:
- Feynman's interpretation: positrons as electrons traveling backward in time
- Time-reversal symmetry (T-symmetry) in electromagnetic interactions
- CPT symmetry and its implications for field configurations
- Wheeler-Feynman absorber theory

The field generator creates specific electromagnetic configurations
that (theoretically) enable temporal displacement by exploiting
T-symmetry properties of electromagnetic interactions.

Note: Actual field configurations for temporal displacement
are not yet determined. This interface supports experimentation.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import math

from timeos.hardware.base import HardwareModule, ModuleStatus, ModuleDiagnostics


class FieldType(Enum):
    """Type of electromagnetic field configuration."""

    STATIC_MAGNETIC = "static_magnetic"  # Constant B field
    ROTATING_MAGNETIC = "rotating_magnetic"  # Time-varying B field
    PULSED_MAGNETIC = "pulsed_magnetic"  # Pulsed B field
    STATIC_ELECTRIC = "static_electric"  # Constant E field
    OSCILLATING_EM = "oscillating_em"  # EM wave configuration
    STANDING_WAVE = "standing_wave"  # Standing EM wave
    SOLITON = "soliton"  # Self-reinforcing wave packet

    # Theoretical/experimental configurations
    T_SYMMETRIC = "t_symmetric"  # Time-symmetric field config
    CPT_CONJUGATE = "cpt_conjugate"  # CPT-transformed configuration
    WHEELER_FEYNMAN = "wheeler_feynman"  # Absorber theory config


class FieldGeometry(Enum):
    """Geometric configuration of the field."""

    UNIFORM = "uniform"  # Constant field throughout volume
    DIPOLE = "dipole"  # Dipole field pattern
    QUADRUPOLE = "quadrupole"  # Quadrupole configuration
    TOROIDAL = "toroidal"  # Toroidal/donut shape
    SOLENOID = "solenoid"  # Cylindrical coil pattern
    HELMHOLTZ = "helmholtz"  # Helmholtz coil pair
    CUSTOM = "custom"  # User-defined geometry


@dataclass
class Vector3:
    """3D vector for field components."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @property
    def magnitude(self) -> float:
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def normalized(self) -> Vector3:
        mag = self.magnitude
        if mag == 0:
            return Vector3(0, 0, 0)
        return Vector3(self.x / mag, self.y / mag, self.z / mag)

    def __mul__(self, scalar: float) -> Vector3:
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    def __add__(self, other: Vector3) -> Vector3:
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)


@dataclass
class FieldConfiguration:
    """Configuration for field generation.

    Attributes:
        field_type: Type of field to generate
        geometry: Geometric configuration
        b_field_tesla: Magnetic field strength (Tesla)
        e_field_vm: Electric field strength (V/m)
        frequency_hz: Oscillation frequency for time-varying fields
        phase_rad: Phase offset (radians)
        direction: Primary field direction
        volume_m3: Active field volume
        gradient_tm: Field gradient (Tesla/meter)
        custom_params: Additional configuration parameters
    """

    field_type: FieldType = FieldType.STATIC_MAGNETIC
    geometry: FieldGeometry = FieldGeometry.HELMHOLTZ
    b_field_tesla: float = 1.0
    e_field_vm: float = 0.0
    frequency_hz: float = 0.0
    phase_rad: float = 0.0
    direction: Vector3 = field(default_factory=lambda: Vector3(0, 0, 1))
    volume_m3: float = 1.0
    gradient_tm: float = 0.0
    custom_params: dict[str, Any] = field(default_factory=dict)

    @property
    def energy_density_jm3(self) -> float:
        """Calculate field energy density (J/m^3)."""
        mu_0 = 4 * math.pi * 1e-7  # Vacuum permeability
        epsilon_0 = 8.854e-12  # Vacuum permittivity

        b_energy = (self.b_field_tesla ** 2) / (2 * mu_0)
        e_energy = (epsilon_0 * self.e_field_vm ** 2) / 2

        return b_energy + e_energy

    @property
    def total_energy_joules(self) -> float:
        """Total field energy."""
        return self.energy_density_jm3 * self.volume_m3

    @property
    def is_time_varying(self) -> bool:
        """Check if field varies with time."""
        return self.field_type in (
            FieldType.ROTATING_MAGNETIC,
            FieldType.PULSED_MAGNETIC,
            FieldType.OSCILLATING_EM,
            FieldType.STANDING_WAVE,
        )


@dataclass
class FieldState:
    """Current state of the field generator.

    Attributes:
        active: Whether field is being generated
        configuration: Current field configuration
        actual_b_tesla: Measured magnetic field strength
        actual_e_vm: Measured electric field strength
        stability: Field stability metric (0.0 to 1.0)
        uniformity: Field uniformity metric (0.0 to 1.0)
        power_watts: Current power consumption
        temperature_kelvin: Coil/magnet temperature
        quench_risk: Risk of superconducting quench (0.0 to 1.0)
    """

    active: bool = False
    configuration: FieldConfiguration | None = None
    actual_b_tesla: float = 0.0
    actual_e_vm: float = 0.0
    stability: float = 1.0
    uniformity: float = 1.0
    power_watts: float = 0.0
    temperature_kelvin: float = 293.0  # Room temp
    quench_risk: float = 0.0


class FieldGenerator(HardwareModule):
    """Abstract interface for electromagnetic field generation.

    The field generator creates the electromagnetic environment
    required for temporal displacement operations. Different
    field configurations may enable different displacement modes.

    Theory notes:
    - T-symmetric fields may create conditions for time reversal
    - Strong magnetic fields affect particle worldlines
    - Rotating fields may induce frame-dragging effects
    - Pulsed fields can create transient conditions

    Safety considerations:
    - Strong magnetic fields affect pacemakers, metal implants
    - Rapidly changing fields induce eddy currents
    - Superconducting magnets risk quench events
    - High voltages present shock hazard
    """

    def __init__(self, module_id: str = "field_gen_primary"):
        super().__init__(module_id)
        self._current_config: FieldConfiguration | None = None
        self._field_active = False
        self._ramp_rate_ts = 0.1  # Tesla per second for ramping

    @property
    def field_active(self) -> bool:
        """Check if field is currently being generated."""
        return self._field_active

    @abstractmethod
    def configure(self, config: FieldConfiguration) -> bool:
        """Set field configuration.

        Args:
            config: Desired field configuration.

        Returns:
            True if configuration is valid and accepted.
        """
        pass

    @abstractmethod
    def energize(self) -> bool:
        """Activate field generation.

        Must call configure() first.

        Returns:
            True if field was activated successfully.
        """
        pass

    @abstractmethod
    def de_energize(self) -> bool:
        """Deactivate field generation safely.

        Returns:
            True if field was deactivated successfully.
        """
        pass

    @abstractmethod
    def ramp_to(self, target_b_tesla: float, rate_ts: float | None = None) -> bool:
        """Ramp field to target strength.

        Args:
            target_b_tesla: Target magnetic field strength.
            rate_ts: Ramp rate in Tesla/second (None = use default).

        Returns:
            True if ramp completed successfully.
        """
        pass

    @abstractmethod
    def get_field_state(self) -> FieldState:
        """Get current field state.

        Returns:
            Current state of the field generator.
        """
        pass

    @abstractmethod
    def measure_field(self, position: Vector3) -> tuple[Vector3, Vector3]:
        """Measure field at a specific position.

        Args:
            position: Position in meters from center.

        Returns:
            Tuple of (B_field, E_field) vectors.
        """
        pass

    @abstractmethod
    def get_field_map(
        self, resolution: float = 0.01
    ) -> dict[tuple[float, float, float], tuple[Vector3, Vector3]]:
        """Get full field map.

        Args:
            resolution: Spatial resolution in meters.

        Returns:
            Dictionary mapping positions to (B, E) field vectors.
        """
        pass

    def calculate_lorentz_force(
        self, charge: float, velocity: Vector3, position: Vector3
    ) -> Vector3:
        """Calculate Lorentz force on a charged particle.

        F = q(E + v × B)

        Args:
            charge: Particle charge in Coulombs.
            velocity: Particle velocity in m/s.
            position: Particle position in meters.

        Returns:
            Force vector in Newtons.
        """
        b_field, e_field = self.measure_field(position)

        # v × B (cross product)
        v_cross_b = Vector3(
            velocity.y * b_field.z - velocity.z * b_field.y,
            velocity.z * b_field.x - velocity.x * b_field.z,
            velocity.x * b_field.y - velocity.y * b_field.x,
        )

        # F = q(E + v × B)
        return Vector3(
            charge * (e_field.x + v_cross_b.x),
            charge * (e_field.y + v_cross_b.y),
            charge * (e_field.z + v_cross_b.z),
        )
