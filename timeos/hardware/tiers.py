"""Hardware Tier Definitions for TimeOS.

Defines the buildability and reality status of hardware modules.

Tier Definitions:
- REAL: Direct hardware implementation with real physics
- PROXY: Real hardware acting as stand-in for abstract concept
- INFRASTRUCTURE: Supporting systems (compute, network, power)
- ABSTRACT: Pure software, no hardware equivalent needed
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING


class HardwareTier(Enum):
    """Hardware tier classification."""

    REAL = "real"
    """Direct hardware implementation with real physics.

    Examples: Temperature sensors, safety relays, GPS clocks
    """

    PROXY = "proxy"
    """Real hardware acting as stand-in for abstract concept.

    Examples: Electromagnet for "temporal field", PLC for TDU sequencing
    """

    INFRASTRUCTURE = "infrastructure"
    """Supporting systems required but not domain-specific.

    Examples: Control computer, network switch, power distribution
    """

    ABSTRACT = "abstract"
    """Pure software, no hardware equivalent needed.

    Examples: Causality engine, timeline branching, constraint checking
    """


@dataclass(frozen=True)
class HardwareSpec:
    """Specification for a hardware module's real-world mapping."""

    tier: HardwareTier
    """The buildability tier of this module."""

    buildability_percent: int
    """Percentage of functionality buildable with current technology (0-100)."""

    description: str
    """Human-readable description of what this module represents."""

    real_world_equivalent: str
    """What off-the-shelf hardware could implement this."""

    example_products: tuple[str, ...]
    """Specific product examples that could be used."""

    cost_range: tuple[int, int]
    """Estimated cost range in USD (min, max)."""

    notes: str = ""
    """Additional notes about buildability or limitations."""


# Module hardware specifications
MODULE_SPECS: dict[str, HardwareSpec] = {
    "field_generator": HardwareSpec(
        tier=HardwareTier.PROXY,
        buildability_percent=85,
        description="Electromagnetic field generation and control",
        real_world_equivalent="Programmable power supply + electromagnet + gaussmeter",
        example_products=(
            "TDK Lambda Zup/Genesys",
            "Keysight E36xx",
            "Delta Elektronika SM",
            "Lake Shore 475 Gaussmeter",
        ),
        cost_range=(1000, 5000),
        notes="Physical B-field is real; 'temporal field' interpretation is proxy",
    ),
    "tdu": HardwareSpec(
        tier=HardwareTier.PROXY,
        buildability_percent=75,
        description="Temporal Displacement Unit - sequencing and coordination",
        real_world_equivalent="Industrial PLC or motion controller with state machine",
        example_products=(
            "Beckhoff CX-series",
            "Siemens S7-1200",
            "Allen-Bradley Micro800",
            "WAGO PFC200",
        ),
        cost_range=(500, 2000),
        notes="Executes sequenced operations; 'displacement' is semantic, not physical",
    ),
    "causality_monitor": HardwareSpec(
        tier=HardwareTier.ABSTRACT,
        buildability_percent=100,
        description="Causal ordering and constraint verification",
        real_world_equivalent="Pure software - graph analysis and constraint checking",
        example_products=(
            "Custom software",
            "Constraint solvers",
            "Model checkers",
        ),
        cost_range=(0, 0),
        notes="Already fully implemented in software; no hardware needed",
    ),
    "anchor": HardwareSpec(
        tier=HardwareTier.REAL,
        buildability_percent=95,
        description="Temporal reference and synchronization",
        real_world_equivalent="GPS-disciplined oscillator + precision clock",
        example_products=(
            "Trimble Thunderbolt E",
            "Jackson Labs Fury",
            "Leo Bodnar GPS Clock",
            "Stanford Research FS725 Rubidium",
        ),
        cost_range=(300, 2000),
        notes="Standard metrology equipment; fully buildable",
    ),
    "safety": HardwareSpec(
        tier=HardwareTier.REAL,
        buildability_percent=98,
        description="Safety interlocks and emergency stop systems",
        real_world_equivalent="Safety PLC + E-stop + safety relays",
        example_products=(
            "Pilz PNOZ",
            "Sick Flexi Soft",
            "Allen-Bradley Guardmaster",
            "Siemens 3SK1",
        ),
        cost_range=(200, 1000),
        notes="Most realistic part of system; standard industrial safety",
    ),
    "thermal": HardwareSpec(
        tier=HardwareTier.REAL,
        buildability_percent=100,
        description="Temperature monitoring and thermal management",
        real_world_equivalent="RTD/thermocouple sensors + PID controller + cooling",
        example_products=(
            "PT100 RTDs",
            "MAX31865 interface",
            "Industrial PID controllers",
            "Recirculating chillers",
        ),
        cost_range=(100, 2000),
        notes="Completely standard industrial/lab equipment",
    ),
    "power": HardwareSpec(
        tier=HardwareTier.REAL,
        buildability_percent=100,
        description="Power monitoring and energy budget tracking",
        real_world_equivalent="Power meters + smart PDU + UPS",
        example_products=(
            "IoTaWatt",
            "Schneider PowerLogic",
            "APC Smart-UPS",
            "Raritan PDU",
        ),
        cost_range=(200, 1500),
        notes="Standard power monitoring; fully buildable",
    ),
    "data_logger": HardwareSpec(
        tier=HardwareTier.REAL,
        buildability_percent=100,
        description="Multi-channel data acquisition and logging",
        real_world_equivalent="DAQ module + storage",
        example_products=(
            "NI USB-6001/6009",
            "Beckhoff EL terminals",
            "LabJack T7",
            "Digilent Analog Discovery",
        ),
        cost_range=(200, 1500),
        notes="Standard DAQ; HDF5/CSV export is pure software",
    ),
}


def get_module_spec(module_id: str) -> HardwareSpec | None:
    """Get the hardware specification for a module.

    Args:
        module_id: The module identifier

    Returns:
        HardwareSpec if found, None otherwise
    """
    return MODULE_SPECS.get(module_id)


def get_tier_symbol(tier: HardwareTier) -> str:
    """Get the display symbol for a hardware tier.

    Args:
        tier: The hardware tier

    Returns:
        Symbol string like "[R]", "[P]", etc.
    """
    symbols = {
        HardwareTier.REAL: "[R]",
        HardwareTier.PROXY: "[P]",
        HardwareTier.INFRASTRUCTURE: "[I]",
        HardwareTier.ABSTRACT: "[A]",
    }
    return symbols.get(tier, "[?]")


def get_tier_color(tier: HardwareTier) -> str:
    """Get the display color for a hardware tier.

    Args:
        tier: The hardware tier

    Returns:
        Hex color string
    """
    colors = {
        HardwareTier.REAL: "#00ff88",       # Green - fully real
        HardwareTier.PROXY: "#44aaff",      # Blue - proxy hardware
        HardwareTier.INFRASTRUCTURE: "#888888",  # Gray - supporting
        HardwareTier.ABSTRACT: "#aa88ff",   # Purple - software only
    }
    return colors.get(tier, "#ffffff")


def get_overall_buildability() -> float:
    """Calculate overall system buildability percentage.

    Returns:
        Weighted average buildability (0-100)
    """
    total = 0
    count = 0
    for spec in MODULE_SPECS.values():
        if spec.tier != HardwareTier.ABSTRACT:  # Don't count pure software
            total += spec.buildability_percent
            count += 1
    return total / count if count > 0 else 0.0


def format_cost_range(cost_range: tuple[int, int]) -> str:
    """Format a cost range for display.

    Args:
        cost_range: (min, max) tuple in USD

    Returns:
        Formatted string like "$500 - $2,000"
    """
    min_cost, max_cost = cost_range
    if min_cost == 0 and max_cost == 0:
        return "N/A (software)"
    return f"${min_cost:,} - ${max_cost:,}"
