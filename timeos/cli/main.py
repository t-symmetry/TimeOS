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
def gui(demo: bool) -> None:
    """Launch the TimeOS GUI control interface."""
    try:
        from timeos.gui import launch
    except ImportError:
        click.echo("Error: GUI dependencies not installed.")
        click.echo("Install with: pip install timeos[gui]")
        sys.exit(1)

    sys.exit(launch(demo=demo))


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


if __name__ == "__main__":
    cli()
