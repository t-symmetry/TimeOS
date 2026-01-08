"""Paradox Test Suite - Educational demonstrations of classic time travel paradoxes.

This module provides runnable scenarios that demonstrate how TimeOS
handles various paradoxes through its constraint system.

Each paradox is designed to:
1. Set up a timeline configuration
2. Attempt an operation that would create a paradox
3. Show how the constraint system detects and responds
4. Explain what happened and why

Usage:
    from timeos.paradoxes import GrandfatherParadox, BootstrapParadox

    # Run a paradox demo
    demo = GrandfatherParadox()
    result = demo.run()
    print(result.explanation)

    # Load a pre-built scenario
    from timeos.paradoxes import load_scenario, list_scenarios
    timeline, events = load_scenario("branching")
"""

from timeos.paradoxes.scenarios import (
    ParadoxDemo,
    ParadoxResult,
    GrandfatherParadox,
    BootstrapParadox,
    PredestinationParadox,
    ObserverParadox,
    run_all_demos,
)

from timeos.paradoxes.demo_scenarios import (
    Scenario,
    ScenarioCategory,
    ScenarioEvent,
    get_scenario,
    list_scenarios,
    load_scenario,
    ALL_SCENARIOS,
    SCENARIOS_BY_NAME,
    SCENARIOS_BY_CATEGORY,
)

__all__ = [
    # Paradox demos
    "ParadoxDemo",
    "ParadoxResult",
    "GrandfatherParadox",
    "BootstrapParadox",
    "PredestinationParadox",
    "ObserverParadox",
    "run_all_demos",
    # Scenarios
    "Scenario",
    "ScenarioCategory",
    "ScenarioEvent",
    "get_scenario",
    "list_scenarios",
    "load_scenario",
    "ALL_SCENARIOS",
    "SCENARIOS_BY_NAME",
    "SCENARIOS_BY_CATEGORY",
]
