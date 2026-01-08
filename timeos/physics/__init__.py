"""TimeOS Physics Layer - Relativistic spacetime calculations.

This package provides proper relativistic physics for temporal operations:
- 4-vectors and Minkowski spacetime
- Lorentz transformations
- Reference frame management
- Causal structure (light cones)

All calculations use natural units where c=1 unless otherwise specified.
SI unit conversions are provided where needed.
"""

from timeos.physics.spacetime import (
    FourVector,
    Event,
    SpacetimeInterval,
    IntervalType,
    SPEED_OF_LIGHT,
)
from timeos.physics.lorentz import (
    LorentzBoost,
    lorentz_factor,
    time_dilation,
    length_contraction,
    velocity_addition,
)
from timeos.physics.frames import (
    InertialFrame,
    FrameRegistry,
)
from timeos.physics.causality import (
    LightCone,
    CausalRelation,
    is_causally_connected,
)

__all__ = [
    # Spacetime
    "FourVector",
    "Event",
    "SpacetimeInterval",
    "IntervalType",
    "SPEED_OF_LIGHT",
    # Lorentz
    "LorentzBoost",
    "lorentz_factor",
    "time_dilation",
    "length_contraction",
    "velocity_addition",
    # Frames
    "InertialFrame",
    "FrameRegistry",
    # Causality
    "LightCone",
    "CausalRelation",
    "is_causally_connected",
]
