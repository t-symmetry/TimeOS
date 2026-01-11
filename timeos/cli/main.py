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


# =============================================================================
# Clock Commands
# =============================================================================

@cli.group()
def clock() -> None:
    """Manage clock sources and time synchronization."""
    pass


@clock.command("status")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
def clock_status(json_output: bool) -> None:
    """Show status of all clock sources.

    Displays current time sources with quality metrics including
    offset, uncertainty, stratum, and synchronization status.
    """
    try:
        from timeos.clocks import (
            ClockRegistry,
            RealtimeClock,
            MonotonicClock,
            NTPClock,
        )
    except ImportError as e:
        click.echo(f"Error loading clocks module: {e}")
        sys.exit(1)

    # Create registry with available clocks
    registry = ClockRegistry()

    # Add system clocks
    registry.register(RealtimeClock())
    registry.register(MonotonicClock())

    # Try NTP
    try:
        ntp = NTPClock()
        if ntp.ntp_daemon:
            registry.register(ntp)
    except Exception:
        pass

    if json_output:
        import json as json_lib
        data = []
        for clock in registry:
            quality = clock.get_quality()
            data.append({
                "source_id": clock.source_id,
                "type": clock.clock_type.value,
                "status": clock.status.name,
                "stratum": quality.stratum,
                "offset": quality.offset,
                "uncertainty": quality.estimated_error,
                "jitter": quality.jitter,
                "quality_score": quality.quality_score,
            })
        click.echo(json_lib.dumps(data, indent=2))
        return

    click.echo("Clock Sources")
    click.echo("=" * 60)

    for clock in registry:
        quality = clock.get_quality()
        stamp = clock.now()

        status_color = {
            "SYNCED": "green",
            "DEGRADED": "yellow",
            "FREERUN": "red",
            "FAULT": "red",
        }.get(clock.status.name, "white")

        click.echo("")
        click.echo(click.style(f"  {clock.source_id}", bold=True) +
                   f" ({clock.clock_type.value})")
        click.echo(f"    Status:      {click.style(clock.status.name, fg=status_color)}")
        click.echo(f"    Stratum:     {quality.stratum}")
        click.echo(f"    Offset:      {_format_time(quality.offset)}")
        click.echo(f"    Uncertainty: ±{_format_time(quality.estimated_error)}")
        click.echo(f"    Jitter:      {_format_time(quality.jitter)}")
        click.echo(f"    Quality:     {quality.quality_score*100:.1f}%")

    # Show best clock
    best = registry.get_best()
    if best:
        click.echo("")
        click.echo(f"Best source: {click.style(best.source_id, fg='green', bold=True)}")

    click.echo("")


@clock.command("now")
@click.option("--source", "-s", help="Specific clock source to use.")
@click.option("--format", "-f", "fmt", default="iso",
              type=click.Choice(["iso", "unix", "tai"]),
              help="Output format.")
def clock_now(source: str | None, fmt: str) -> None:
    """Get current time from clock sources.

    Returns current time with uncertainty from the best available
    clock source, or a specific source if specified.
    """
    try:
        from timeos.clocks import (
            ClockRegistry,
            RealtimeClock,
            MonotonicClock,
            NTPClock,
        )
    except ImportError as e:
        click.echo(f"Error loading clocks module: {e}")
        sys.exit(1)

    from datetime import datetime, timezone

    # Create registry
    registry = ClockRegistry()
    registry.register(RealtimeClock())
    registry.register(MonotonicClock())

    try:
        ntp = NTPClock()
        if ntp.ntp_daemon:
            registry.register(ntp)
    except Exception:
        pass

    # Get clock
    if source:
        clock = registry.get(source)
        if not clock:
            click.echo(f"Unknown clock source: {source}")
            click.echo(f"Available: {', '.join(c.source_id for c in registry)}")
            sys.exit(1)
    else:
        clock = registry.get_best()

    if not clock:
        click.echo("No clock sources available")
        sys.exit(1)

    stamp = clock.now()

    if fmt == "unix":
        click.echo(f"{stamp.t:.9f} ±{stamp.t_uncertainty:.9f}")
    elif fmt == "tai":
        # TAI is UTC + leap seconds (currently 37)
        tai = stamp.t + 37
        click.echo(f"{tai:.9f} ±{stamp.t_uncertainty:.9f} TAI")
    else:  # iso
        dt = datetime.fromtimestamp(stamp.t, tz=timezone.utc)
        click.echo(f"{dt.isoformat()} ±{_format_time(stamp.t_uncertainty)}")
        click.echo(f"Source: {clock.source_id} ({clock.clock_type.value})")


@clock.command("drift")
@click.option("--duration", "-d", default=10.0, help="Measurement duration in seconds.")
@click.option("--interval", "-i", default=1.0, help="Sample interval in seconds.")
def clock_drift(duration: float, interval: float) -> None:
    """Measure clock drift over time.

    Compares monotonic and realtime clocks to estimate drift.
    """
    import time

    click.echo(f"Measuring drift for {duration:.1f}s (interval: {interval:.1f}s)...")
    click.echo("")

    samples = []
    start_mono = time.monotonic()
    start_real = time.time()

    while True:
        elapsed = time.monotonic() - start_mono
        if elapsed >= duration:
            break

        mono = time.monotonic()
        real = time.time()

        # Difference from start
        mono_elapsed = mono - start_mono
        real_elapsed = real - start_real

        # Drift is difference between clocks
        drift = real_elapsed - mono_elapsed
        samples.append((mono_elapsed, drift))

        time.sleep(interval)

    if len(samples) < 2:
        click.echo("Not enough samples collected")
        return

    # Calculate drift rate (linear regression)
    n = len(samples)
    sum_x = sum(s[0] for s in samples)
    sum_y = sum(s[1] for s in samples)
    sum_xy = sum(s[0] * s[1] for s in samples)
    sum_xx = sum(s[0] ** 2 for s in samples)

    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x ** 2)
    intercept = (sum_y - slope * sum_x) / n

    drift_ppm = slope * 1e6

    click.echo(f"Samples:      {n}")
    click.echo(f"Duration:     {samples[-1][0]:.1f}s")
    click.echo(f"Total drift:  {_format_time(samples[-1][1])}")
    click.echo(f"Drift rate:   {drift_ppm:.3f} ppm")

    if abs(drift_ppm) < 0.1:
        click.echo(click.style("Drift: Excellent (<0.1 ppm)", fg="green"))
    elif abs(drift_ppm) < 1.0:
        click.echo(click.style("Drift: Good (<1 ppm)", fg="green"))
    elif abs(drift_ppm) < 10.0:
        click.echo(click.style("Drift: Acceptable (<10 ppm)", fg="yellow"))
    else:
        click.echo(click.style(f"Drift: High ({drift_ppm:.1f} ppm)", fg="red"))


def _format_time(seconds: float) -> str:
    """Format time value with appropriate units."""
    if seconds == float('inf') or seconds != seconds:  # NaN check
        return "--"

    abs_s = abs(seconds)
    if abs_s == 0:
        return "0"
    elif abs_s < 1e-9:
        return f"{seconds*1e12:.1f} ps"
    elif abs_s < 1e-6:
        return f"{seconds*1e9:.1f} ns"
    elif abs_s < 1e-3:
        return f"{seconds*1e6:.1f} µs"
    elif abs_s < 1:
        return f"{seconds*1e3:.1f} ms"
    else:
        return f"{seconds:.3f} s"


# =============================================================================
# Correlation Commands
# =============================================================================

@cli.command("correlate")
@click.argument("file1", type=click.Path(exists=True))
@click.argument("file2", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output file for aligned data.")
@click.option("--time-col", default="time", help="Column name for timestamps.")
@click.option("--value-col", default="value", help="Column name for values.")
@click.option("--max-offset", type=float, default=1.0, help="Maximum offset to search (seconds).")
def correlate_cmd(
    file1: str,
    file2: str,
    output: str | None,
    time_col: str,
    value_col: str,
    max_offset: float,
) -> None:
    """Align two CSV data files by cross-correlation.

    Finds the time offset between two data streams and optionally
    outputs the aligned data.

    Example:
        timeos correlate sensor1.csv sensor2.csv -o aligned.csv
    """
    import csv

    def load_csv(path: str) -> tuple[list[float], list[float]]:
        """Load time/value pairs from CSV."""
        times = []
        values = []
        with open(path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    times.append(float(row[time_col]))
                    values.append(float(row[value_col]))
                except (KeyError, ValueError):
                    continue
        return times, values

    try:
        from timeos.correlation import find_offset, align_streams
        from timeos.correlation.align import TimeSeries
    except ImportError as e:
        click.echo(f"Error loading correlation module: {e}")
        sys.exit(1)

    # Load data
    click.echo(f"Loading {file1}...")
    times1, values1 = load_csv(file1)
    click.echo(f"  {len(times1)} samples")

    click.echo(f"Loading {file2}...")
    times2, values2 = load_csv(file2)
    click.echo(f"  {len(times2)} samples")

    if not times1 or not times2:
        click.echo("Error: No valid data found in files.")
        sys.exit(1)

    # Create time series
    series1 = TimeSeries(times=times1, values=values1)
    series2 = TimeSeries(times=times2, values=values2)

    # Find offset
    click.echo("Computing cross-correlation...")
    result = find_offset(series1, series2, max_offset=max_offset)

    click.echo()
    click.echo("Alignment Results")
    click.echo("=" * 40)
    click.echo(f"Offset:      {_format_time(result.offset)}")
    click.echo(f"Uncertainty: {_format_time(result.offset_uncertainty)}")
    click.echo(f"Correlation: {result.correlation:.4f}")
    click.echo(f"Confidence:  {result.confidence * 100:.1f}%")

    if result.correlation > 0.8:
        click.echo(click.style("Alignment: Excellent", fg="green"))
    elif result.correlation > 0.5:
        click.echo(click.style("Alignment: Good", fg="green"))
    elif result.correlation > 0.2:
        click.echo(click.style("Alignment: Fair", fg="yellow"))
    else:
        click.echo(click.style("Alignment: Poor", fg="red"))

    # Output aligned data if requested
    if output:
        _, aligned = align_streams(series1, series2, result)

        with open(output, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([time_col, value_col, 'source'])

            # Write series1
            for t, v in zip(series1.times, series1.values):
                writer.writerow([t, v, 'file1'])

            # Write aligned series2
            for t, v in zip(aligned.times, aligned.values):
                writer.writerow([t, v, 'file2'])

        click.echo(f"\nAligned data written to: {output}")


# =============================================================================
# Export Commands
# =============================================================================

@cli.group()
def export() -> None:
    """Export timeline data to various formats."""
    pass


@export.command("prov")
@click.option("--format", "fmt", type=click.Choice(["ttl", "json"]), default="ttl",
              help="Output format (ttl=Turtle, json=JSON-LD).")
@click.option("--base-uri", default="http://example.org/timeos/",
              help="Base URI for identifiers.")
@click.option("--output", "-o", type=click.Path(), help="Output file (default: stdout).")
@click.pass_context
def export_prov(ctx: click.Context, fmt: str, base_uri: str, output: str | None) -> None:
    """Export timeline to W3C PROV provenance format.

    Exports events as PROV entities with derivation relationships
    for provenance tracking and data lineage.

    Example:
        timeos export prov --format ttl > timeline.ttl
        timeos export prov --format json -o timeline.jsonld
    """
    db_path = ctx.obj["db"]

    try:
        from timeos.formats.prov import export_timeline_prov
    except ImportError as e:
        click.echo(f"Error loading formats module: {e}")
        sys.exit(1)

    log = EventLog(db_path)

    try:
        result = export_timeline_prov(log, output_format=fmt, base_uri=base_uri)

        if output:
            with open(output, 'w') as f:
                f.write(result)
            click.echo(f"Exported to: {output}")
        else:
            click.echo(result)

    finally:
        log.close()


@export.command("influx")
@click.option("--measurement", default="timeos_event", help="InfluxDB measurement name.")
@click.option("--output", "-o", type=click.Path(), help="Output file (default: stdout).")
@click.pass_context
def export_influx(ctx: click.Context, measurement: str, output: str | None) -> None:
    """Export timeline to InfluxDB line protocol.

    Generates line protocol that can be piped to `influx write` or
    imported via the InfluxDB API.

    Example:
        timeos export influx > events.lp
        timeos export influx | influx write -b mybucket
    """
    db_path = ctx.obj["db"]

    try:
        from timeos.formats.influx import format_events_influx
    except ImportError as e:
        click.echo(f"Error loading formats module: {e}")
        sys.exit(1)

    log = EventLog(db_path)

    try:
        events = list(log.query())

        if not events:
            click.echo("No events to export.", err=True)
            return

        result = format_events_influx(events, measurement=measurement)

        if output:
            with open(output, 'w') as f:
                f.write(result)
            click.echo(f"Exported {len(events)} events to: {output}", err=True)
        else:
            click.echo(result)

    finally:
        log.close()


@export.command("json")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
@click.option("--output", "-o", type=click.Path(), help="Output file (default: stdout).")
@click.pass_context
def export_json(ctx: click.Context, pretty: bool, output: str | None) -> None:
    """Export timeline to JSON format.

    Example:
        timeos export json --pretty > timeline.json
    """
    import json as json_lib

    db_path = ctx.obj["db"]
    log = EventLog(db_path)

    try:
        events = [event.to_dict() for event in log.query()]

        if pretty:
            result = json_lib.dumps({"events": events}, indent=2)
        else:
            result = json_lib.dumps({"events": events})

        if output:
            with open(output, 'w') as f:
                f.write(result)
            click.echo(f"Exported {len(events)} events to: {output}", err=True)
        else:
            click.echo(result)

    finally:
        log.close()


@export.command("csv")
@click.option("--output", "-o", type=click.Path(), help="Output file (default: stdout).")
@click.pass_context
def export_csv(ctx: click.Context, output: str | None) -> None:
    """Export timeline to CSV format.

    Example:
        timeos export csv -o timeline.csv
    """
    import csv
    import io

    db_path = ctx.obj["db"]
    log = EventLog(db_path)

    try:
        events = list(log.query())

        if not events:
            click.echo("No events to export.", err=True)
            return

        # Prepare CSV
        if output:
            f = open(output, 'w', newline='')
        else:
            f = io.StringIO()

        writer = csv.writer(f)
        writer.writerow([
            'event_id', 'frame_id', 't', 't_uncertainty',
            'branch_id', 'event_type', 'author'
        ])

        for event in events:
            writer.writerow([
                event.event_id,
                event.stamp.frame_id,
                event.stamp.t,
                event.stamp.t_uncertainty,
                event.branch_id,
                event.event_type,
                event.author or '',
            ])

        if output:
            f.close()
            click.echo(f"Exported {len(events)} events to: {output}", err=True)
        else:
            click.echo(f.getvalue())

    finally:
        log.close()


if __name__ == "__main__":
    cli()
