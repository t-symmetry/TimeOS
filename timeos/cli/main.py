"""TimeOS CLI - Command-line interface for temporal event management."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from timeos import __version__
from timeos.msgs import ChronoStamp, TimelineEvent
from timeos.core.event_log import EventLog
from timeos.core.timeline import Timeline
from timeos.core.constraints import ConstraintChecker


DEFAULT_DB = "timeline.db"


def get_timeline(db_path: str) -> Timeline:
    """Get a Timeline instance for the given database path."""
    log = EventLog(db_path)
    return Timeline(log)


@click.group()
@click.version_option(version=__version__, prog_name="TimeOS")
@click.option(
    "--db",
    default=DEFAULT_DB,
    envvar="TIMEOS_DB",
    help="Path to timeline database.",
    type=click.Path(),
)
@click.pass_context
def cli(ctx: click.Context, db: str) -> None:
    """TimeOS - Time Operating System.

    A modular framework for temporal event systems with causality constraints.
    """
    ctx.ensure_object(dict)
    ctx.obj["db"] = db


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize a new timeline database."""
    db_path = ctx.obj["db"]

    if Path(db_path).exists():
        click.echo(f"Database already exists: {db_path}")
        return

    log = EventLog(db_path)
    log.close()
    click.echo(f"Initialized timeline database: {db_path}")


@cli.command()
@click.argument("event_file", type=click.Path(exists=True))
@click.option("--branch", "-b", default="main", help="Branch to add event to.")
@click.option("--author", "-a", default="", help="Event author.")
@click.pass_context
def log(ctx: click.Context, event_file: str, branch: str, author: str) -> None:
    """Append an event from a JSON file."""
    db_path = ctx.obj["db"]

    with open(event_file) as f:
        data = json.load(f)

    timeline = get_timeline(db_path)

    if author:
        timeline.set_author(author)

    if branch != "main":
        try:
            timeline.set_branch(branch)
        except ValueError:
            click.echo(f"Branch '{branch}' does not exist. Create it first with 'timeos branch create'.")
            sys.exit(1)

    # Create event from JSON
    stamp_data = data.get("stamp", {})
    stamp = ChronoStamp(
        frame_id=stamp_data.get("frame_id", "default"),
        t=stamp_data.get("t", 0.0),
        t_uncertainty=stamp_data.get("t_uncertainty", 0.0),
        clock_id=stamp_data.get("clock_id", ""),
        clock_class=stamp_data.get("clock_class", "sim"),
    )

    parents = data.get("parents", [])
    payload = data.get("payload", "").encode() if isinstance(data.get("payload"), str) else b""

    event = timeline.create_event(
        stamp=stamp,
        event_type=data.get("event_type", "observation"),
        payload=payload,
        payload_schema=data.get("payload_schema", ""),
        parents=parents,
        branch_id=branch,
    )

    click.echo(f"Event logged: {event.event_id}")
    timeline.log.close()


@cli.command()
@click.option("--start", "-s", type=float, help="Start time (inclusive).")
@click.option("--end", "-e", type=float, help="End time (inclusive).")
@click.option("--frame", "-f", help="Filter by frame ID.")
@click.option("--branch", "-b", help="Filter by branch.")
@click.option("--type", "-t", "event_type", help="Filter by event type.")
@click.option("--limit", "-n", type=int, help="Maximum number of results.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.pass_context
def query(
    ctx: click.Context,
    start: float | None,
    end: float | None,
    frame: str | None,
    branch: str | None,
    event_type: str | None,
    limit: int | None,
    as_json: bool,
) -> None:
    """Query events from the timeline."""
    db_path = ctx.obj["db"]
    timeline = get_timeline(db_path)

    events = list(
        timeline.log.query(
            start=start,
            end=end,
            frame_id=frame,
            branch_id=branch,
            event_type=event_type,
            limit=limit,
        )
    )

    if as_json:
        output = {"events": [e.to_dict() for e in events]}
        click.echo(json.dumps(output, indent=2))
    else:
        if not events:
            click.echo("No events found.")
        else:
            for event in events:
                click.echo(
                    f"[{event.stamp.t:.6f}] {event.event_id[:8]}... "
                    f"({event.event_type}) branch:{event.branch_id}"
                )

    timeline.log.close()


@cli.group()
def branch() -> None:
    """Manage timeline branches."""
    pass


@branch.command("list")
@click.pass_context
def branch_list(ctx: click.Context) -> None:
    """List all branches."""
    db_path = ctx.obj["db"]
    timeline = get_timeline(db_path)

    branches = timeline.list_branches()

    if not branches:
        click.echo("No branches found.")
    else:
        for b in branches:
            parent = f" (from {b.parent_branch})" if b.parent_branch else ""
            click.echo(f"  {b.branch_id}: {b.event_count} events{parent}")

    timeline.log.close()


@branch.command("create")
@click.argument("name")
@click.option("--from", "from_event", help="Event ID to fork from.")
@click.pass_context
def branch_create(ctx: click.Context, name: str, from_event: str | None) -> None:
    """Create a new branch."""
    db_path = ctx.obj["db"]
    timeline = get_timeline(db_path)

    try:
        timeline.branch(name, from_event=from_event)
        click.echo(f"Created branch: {name}")
    except ValueError as e:
        click.echo(f"Error: {e}")
        sys.exit(1)

    timeline.log.close()


@branch.command("delete")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Delete even if branch has events.")
@click.pass_context
def branch_delete(ctx: click.Context, name: str, force: bool) -> None:
    """Delete a branch."""
    db_path = ctx.obj["db"]
    timeline = get_timeline(db_path)

    try:
        timeline.delete_branch(name, force=force)
        click.echo(f"Deleted branch: {name}")
    except ValueError as e:
        click.echo(f"Error: {e}")
        sys.exit(1)

    timeline.log.close()


@cli.command()
@click.option("--branch", "-b", help="Branch to validate.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed violations.")
@click.pass_context
def validate(ctx: click.Context, branch: str | None, verbose: bool) -> None:
    """Validate timeline consistency."""
    db_path = ctx.obj["db"]
    timeline = get_timeline(db_path)
    checker = ConstraintChecker()

    violations = checker.check_all(timeline, branch_id=branch)

    if not violations:
        event_count = timeline.log.count(branch)
        click.echo(f"Timeline is consistent ({event_count} events checked).")
    else:
        click.echo(f"Found {len(violations)} events with violations:")
        for event, result in violations:
            click.echo(f"  {event.event_id[:8]}... [{result.suggested_action.value}]")
            if verbose:
                for v in result.violations:
                    click.echo(f"    - {v}")

        sys.exit(1)

    timeline.log.close()


@cli.command("export")
@click.argument("output_file", type=click.Path())
@click.pass_context
def export_cmd(ctx: click.Context, output_file: str) -> None:
    """Export timeline to JSON file."""
    db_path = ctx.obj["db"]
    timeline = get_timeline(db_path)

    timeline.log.export_json(output_file)
    event_count = timeline.log.count()
    click.echo(f"Exported {event_count} events to {output_file}")

    timeline.log.close()


@cli.command("import")
@click.argument("input_file", type=click.Path(exists=True))
@click.pass_context
def import_cmd(ctx: click.Context, input_file: str) -> None:
    """Import events from JSON file."""
    db_path = ctx.obj["db"]
    timeline = get_timeline(db_path)

    count = timeline.log.import_json(input_file)
    click.echo(f"Imported {count} events from {input_file}")

    timeline.log.close()


@cli.command()
@click.option("--demo", is_flag=True, help="Launch with demo data.")
@click.option("--emulated", is_flag=True, help="Use emulated hardware modules.")
@click.option("--ros2", is_flag=True, help="Use ROS2 for all hardware communication (agnostic mode).")
def gui(demo: bool, emulated: bool, ros2: bool) -> None:
    """Launch the TimeOS GUI control interface.

    Modes:
      --demo       Simulated timeline with demo events
      --emulated   Realistic hardware emulation
      --ros2       Pure ROS2 interface (hardware-agnostic)

    Combine flags: --demo --ros2 runs demo with ROS2 backend.
    """
    try:
        from timeos.gui import launch
    except ImportError:
        click.echo("Error: GUI dependencies not installed.")
        click.echo("Install with: pip install timeos[gui]")
        sys.exit(1)

    sys.exit(launch(demo=demo, emulated=emulated, ros2=ros2))


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show timeline status."""
    db_path = ctx.obj["db"]

    if not Path(db_path).exists():
        click.echo(f"No timeline database at: {db_path}")
        click.echo("Run 'timeos init' to create one.")
        return

    timeline = get_timeline(db_path)

    total_events = timeline.log.count()
    branches = timeline.list_branches()

    click.echo(f"Database: {db_path}")
    click.echo(f"Total events: {total_events}")
    click.echo(f"Branches: {len(branches)}")

    for b in branches:
        click.echo(f"  - {b.branch_id}: {b.event_count} events")

    timeline.log.close()


@cli.group()
def paradox() -> None:
    """Run paradox demonstrations (educational)."""
    pass


@paradox.command("list")
def paradox_list() -> None:
    """List available paradox demonstrations."""
    click.echo("Available paradox demonstrations:")
    click.echo("")
    click.echo("  grandfather    - The Grandfather Paradox")
    click.echo("                   Attempting to prevent your own existence")
    click.echo("")
    click.echo("  bootstrap      - The Bootstrap Paradox")
    click.echo("                   Information that exists without origin")
    click.echo("")
    click.echo("  predestination - The Predestination Paradox")
    click.echo("                   Actions that cause what they tried to prevent")
    click.echo("")
    click.echo("  observer       - The Observer Paradox")
    click.echo("                   Observation changes the observed")
    click.echo("")
    click.echo("Run 'timeos paradox run <name>' to execute a demonstration.")
    click.echo("Run 'timeos paradox run all' to run all demonstrations.")


@paradox.command("run")
@click.argument("name")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output.")
def paradox_run(name: str, quiet: bool) -> None:
    """Run a paradox demonstration.

    NAME can be: grandfather, bootstrap, predestination, observer, or 'all'.
    """
    try:
        from timeos.paradoxes import (
            GrandfatherParadox,
            BootstrapParadox,
            PredestinationParadox,
            ObserverParadox,
            run_all_demos,
        )
    except ImportError as e:
        click.echo(f"Error loading paradox module: {e}")
        sys.exit(1)

    demos = {
        "grandfather": GrandfatherParadox,
        "bootstrap": BootstrapParadox,
        "predestination": PredestinationParadox,
        "observer": ObserverParadox,
    }

    if name == "all":
        click.echo("Running all paradox demonstrations...")
        click.echo("")
        results = run_all_demos(verbose=not quiet)

        # Summary
        prevented = sum(1 for r in results if r.prevented)
        detected = sum(1 for r in results if r.detected)
        click.echo(f"\nTotal: {len(results)} demos, {detected} detected, {prevented} prevented")

    elif name in demos:
        click.echo(f"Running: {name.title()} Paradox")
        click.echo("")

        demo = demos[name]()
        result = demo.run()

        if quiet:
            status = "PREVENTED" if result.prevented else ("DETECTED" if result.detected else "ALLOWED")
            click.echo(f"Result: {status} (Risk: {result.risk_level*100:.1f}%)")
        else:
            click.echo(result.format_report())

    else:
        click.echo(f"Unknown paradox: {name}")
        click.echo("Available: grandfather, bootstrap, predestination, observer, all")
        sys.exit(1)


@cli.group()
def scenario() -> None:
    """Load pre-built demo scenarios."""
    pass


@scenario.command("list")
@click.option("--category", "-c", help="Filter by category.")
def scenario_list(category: str | None) -> None:
    """List available demo scenarios."""
    try:
        from timeos.paradoxes import (
            list_scenarios,
            ScenarioCategory,
            SCENARIOS_BY_CATEGORY,
        )
    except ImportError as e:
        click.echo(f"Error loading scenarios: {e}")
        sys.exit(1)

    if category:
        try:
            cat = ScenarioCategory(category.lower())
            scenarios = list_scenarios(cat)
        except ValueError:
            click.echo(f"Unknown category: {category}")
            click.echo(f"Available: {', '.join(c.value for c in ScenarioCategory)}")
            sys.exit(1)
    else:
        scenarios = list_scenarios()

    click.echo("Available demo scenarios:")
    click.echo("")

    current_cat = None
    for s in scenarios:
        if s.category != current_cat:
            current_cat = s.category
            click.echo(f"  [{current_cat.value.upper()}]")

        risk_str = f" (expected risk: {s.expected_risk*100:.0f}%)" if s.expected_risk else ""
        click.echo(f"    {s.name:<20} - {s.title}{risk_str}")

    click.echo("")
    click.echo("Run 'timeos scenario load <name>' to load a scenario.")
    click.echo("Run 'timeos scenario info <name>' for details.")


@scenario.command("info")
@click.argument("name")
def scenario_info(name: str) -> None:
    """Show detailed information about a scenario."""
    try:
        from timeos.paradoxes import get_scenario
    except ImportError as e:
        click.echo(f"Error loading scenarios: {e}")
        sys.exit(1)

    s = get_scenario(name)
    if not s:
        click.echo(f"Unknown scenario: {name}")
        sys.exit(1)

    click.echo(f"Scenario: {s.title}")
    click.echo(f"Category: {s.category.value}")
    click.echo("")
    click.echo(f"Description:")
    click.echo(f"  {s.description}")
    click.echo("")

    if s.learning_objectives:
        click.echo("Learning Objectives:")
        for obj in s.learning_objectives:
            click.echo(f"  • {obj}")
        click.echo("")

    click.echo(f"Events: {len(s.events)}")
    for event in s.events:
        parent_str = f" (parents: {', '.join(event.parent_names)})" if event.parent_names else ""
        branch_str = f" [{event.branch_id}]" if event.branch_id != "main" else ""
        click.echo(f"  t={event.t:>5.1f}: {event.name}{branch_str}{parent_str}")

    if s.branches:
        click.echo(f"\nBranches: {', '.join(s.branches)}")

    if s.expected_risk:
        click.echo(f"\nExpected Paradox Risk: {s.expected_risk*100:.0f}%")


@scenario.command("load")
@click.argument("name")
@click.pass_context
def scenario_load(ctx: click.Context, name: str) -> None:
    """Load a scenario into the timeline database."""
    try:
        from timeos.paradoxes import get_scenario
    except ImportError as e:
        click.echo(f"Error loading scenarios: {e}")
        sys.exit(1)

    s = get_scenario(name)
    if not s:
        click.echo(f"Unknown scenario: {name}")
        sys.exit(1)

    db_path = ctx.obj["db"]

    # Initialize if needed
    if not Path(db_path).exists():
        log = EventLog(db_path)
        log.close()
        click.echo(f"Initialized timeline database: {db_path}")

    timeline = get_timeline(db_path)

    click.echo(f"Loading scenario: {s.title}")
    event_map = s.load(timeline)

    click.echo(f"Created {len(event_map)} events:")
    for event_name, event in event_map.items():
        click.echo(f"  {event_name}: {event.event_id[:8]}... (t={event.stamp.t:.1f})")

    if s.branches:
        click.echo(f"Created branches: {', '.join(s.branches)}")

    timeline.log.close()
    click.echo(f"\nScenario loaded to: {db_path}")


@cli.group()
def learn() -> None:
    """Educational walkthroughs and tutorials."""
    pass


@learn.command("list")
def learn_list() -> None:
    """List available walkthroughs."""
    try:
        from timeos.paradoxes import list_walkthroughs
    except ImportError as e:
        click.echo(f"Error loading walkthroughs: {e}")
        sys.exit(1)

    walkthroughs = list_walkthroughs()

    click.echo("Available walkthroughs:")
    click.echo("")

    difficulty_icons = {"beginner": "🟢", "intermediate": "🟡", "advanced": "🔴"}

    for w in walkthroughs:
        icon = difficulty_icons.get(w.difficulty, "⚪")
        prereq_str = f" (requires: {', '.join(w.prerequisites)})" if w.prerequisites else ""
        click.echo(f"  {icon} {w.scenario_name:<20} - {w.title}")
        click.echo(f"     {w.difficulty.capitalize()}, ~{w.estimated_time}{prereq_str}")
        click.echo("")

    click.echo("Run 'timeos learn show <name>' to view a walkthrough.")


@learn.command("show")
@click.argument("name")
@click.option("--step", "-s", type=int, help="Start at specific step (1-based).")
def learn_show(name: str, step: int | None) -> None:
    """Show a walkthrough in the terminal."""
    try:
        from timeos.paradoxes import get_walkthrough
    except ImportError as e:
        click.echo(f"Error loading walkthroughs: {e}")
        sys.exit(1)

    w = get_walkthrough(name)
    if not w:
        click.echo(f"Unknown walkthrough: {name}")
        click.echo("Run 'timeos learn list' to see available walkthroughs.")
        sys.exit(1)

    # Header
    click.echo("")
    click.echo("=" * 60)
    click.echo(f"WALKTHROUGH: {w.title.upper()}")
    click.echo("=" * 60)
    click.echo("")
    click.echo(f"Difficulty: {w.difficulty.capitalize()}")
    click.echo(f"Estimated time: {w.estimated_time}")
    click.echo(f"Steps: {len(w.steps)}")
    if w.prerequisites:
        click.echo(f"Prerequisites: {', '.join(w.prerequisites)}")
    click.echo("")

    # Show steps
    start_step = (step - 1) if step else 0
    start_step = max(0, min(start_step, len(w.steps) - 1))

    for i, s in enumerate(w.steps[start_step:], start=start_step + 1):
        click.echo("-" * 60)
        click.echo(f"Step {i}/{len(w.steps)}: {s.title}")
        click.echo(f"Type: {s.step_type.value.upper()}")
        click.echo("-" * 60)
        click.echo("")

        # Simple markdown rendering for terminal
        content = s.content.strip()
        # Remove markdown headers (show as plain text)
        import re
        content = re.sub(r'^#{1,3}\s+', '', content, flags=re.MULTILINE)
        # Convert **bold** to CAPS for terminal
        content = re.sub(r'\*\*(.+?)\*\*', lambda m: m.group(1).upper(), content)
        # Remove single asterisks (italic)
        content = re.sub(r'\*(.+?)\*', r'\1', content)

        click.echo(content)
        click.echo("")

        # Prompt to continue (unless it's the last step)
        if i < len(w.steps):
            try:
                click.echo("Press Enter for next step (q to quit)...")
                response = input()
                if response.lower() == 'q':
                    break
            except (KeyboardInterrupt, EOFError):
                break
            click.echo("")

    click.echo("=" * 60)
    click.echo("Walkthrough complete!")
    click.echo("")
    click.echo(f"To load this scenario: timeos scenario load {w.scenario_name}")
    click.echo("=" * 60)


if __name__ == "__main__":
    cli()
