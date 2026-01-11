"""W3C PROV-O provenance format.

Exports TimeOS events to W3C PROV ontology format for
provenance tracking and data lineage.

See: https://www.w3.org/TR/prov-o/
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from timeos.core.event_log import EventLog
    from timeos.msgs import TimelineEvent


@dataclass
class ProvEntity:
    """A PROV Entity (thing with provenance).

    In TimeOS, events are entities that can be derived from other events.
    """
    identifier: str
    label: str = ""
    generated_at: Optional[datetime] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_ttl(self, prefix: str = "timeos") -> str:
        """Convert to Turtle format."""
        lines = [f"{prefix}:{self.identifier} a prov:Entity"]

        if self.label:
            lines.append(f'    rdfs:label "{self.label}"')

        if self.generated_at:
            ts = self.generated_at.isoformat()
            lines.append(f'    prov:generatedAtTime "{ts}"^^xsd:dateTime')

        for key, value in self.attributes.items():
            if isinstance(value, str):
                lines.append(f'    {prefix}:{key} "{value}"')
            elif isinstance(value, (int, float)):
                lines.append(f'    {prefix}:{key} {value}')

        return " ;\n".join(lines) + " ."

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-LD compatible dict."""
        result = {
            "@id": self.identifier,
            "@type": "prov:Entity",
        }

        if self.label:
            result["rdfs:label"] = self.label

        if self.generated_at:
            result["prov:generatedAtTime"] = {
                "@type": "xsd:dateTime",
                "@value": self.generated_at.isoformat(),
            }

        result.update(self.attributes)
        return result


@dataclass
class ProvActivity:
    """A PROV Activity (something that occurs over time).

    In TimeOS, operations like displacements or observations are activities.
    """
    identifier: str
    label: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    used: List[str] = field(default_factory=list)
    generated: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_ttl(self, prefix: str = "timeos") -> str:
        """Convert to Turtle format."""
        lines = [f"{prefix}:{self.identifier} a prov:Activity"]

        if self.label:
            lines.append(f'    rdfs:label "{self.label}"')

        if self.start_time:
            ts = self.start_time.isoformat()
            lines.append(f'    prov:startedAtTime "{ts}"^^xsd:dateTime')

        if self.end_time:
            ts = self.end_time.isoformat()
            lines.append(f'    prov:endedAtTime "{ts}"^^xsd:dateTime')

        for used_id in self.used:
            lines.append(f"    prov:used {prefix}:{used_id}")

        for gen_id in self.generated:
            lines.append(f"    prov:generated {prefix}:{gen_id}")

        return " ;\n".join(lines) + " ."

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-LD compatible dict."""
        result = {
            "@id": self.identifier,
            "@type": "prov:Activity",
        }

        if self.label:
            result["rdfs:label"] = self.label

        if self.start_time:
            result["prov:startedAtTime"] = {
                "@type": "xsd:dateTime",
                "@value": self.start_time.isoformat(),
            }

        if self.end_time:
            result["prov:endedAtTime"] = {
                "@type": "xsd:dateTime",
                "@value": self.end_time.isoformat(),
            }

        if self.used:
            result["prov:used"] = [{"@id": u} for u in self.used]

        if self.generated:
            result["prov:generated"] = [{"@id": g} for g in self.generated]

        return result


@dataclass
class ProvAgent:
    """A PROV Agent (something that bears responsibility).

    In TimeOS, authors of events are agents.
    """
    identifier: str
    label: str = ""
    agent_type: str = "prov:SoftwareAgent"
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_ttl(self, prefix: str = "timeos") -> str:
        """Convert to Turtle format."""
        lines = [f"{prefix}:{self.identifier} a {self.agent_type}"]

        if self.label:
            lines.append(f'    rdfs:label "{self.label}"')

        return " ;\n".join(lines) + " ."

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-LD compatible dict."""
        result = {
            "@id": self.identifier,
            "@type": self.agent_type,
        }

        if self.label:
            result["rdfs:label"] = self.label

        return result


def event_to_prov_entity(event: "TimelineEvent") -> ProvEntity:
    """Convert a TimelineEvent to a PROV Entity.

    Args:
        event: TimelineEvent to convert

    Returns:
        ProvEntity representation
    """
    # Create timestamp from event's t value
    # (in TimeOS, t is relative to a reference, not absolute)
    generated_at = None
    if event.stamp.t >= 0:
        # Use a reference epoch (Unix epoch for simplicity)
        try:
            generated_at = datetime.fromtimestamp(event.stamp.t, tz=timezone.utc)
        except (OSError, ValueError):
            # t is out of range for a timestamp
            pass

    return ProvEntity(
        identifier=event.event_id,
        label=f"{event.event_type} at t={event.stamp.t:.6f}",
        generated_at=generated_at,
        attributes={
            "event_type": event.event_type,
            "frame_id": event.stamp.frame_id,
            "t": event.stamp.t,
            "t_uncertainty": event.stamp.t_uncertainty,
            "branch_id": event.branch_id,
        },
    )


def export_prov_ttl(
    log: "EventLog",
    base_uri: str = "http://example.org/timeos/",
    prefix: str = "timeos",
) -> str:
    """Export EventLog to PROV-O Turtle format.

    Args:
        log: EventLog to export
        base_uri: Base URI for identifiers
        prefix: Namespace prefix

    Returns:
        Turtle format string
    """
    lines = [
        f"@prefix {prefix}: <{base_uri}> .",
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
    ]

    # Collect unique agents
    agents: Dict[str, ProvAgent] = {}

    # Convert events to entities and collect relationships
    for event in log.query():
        entity = event_to_prov_entity(event)
        lines.append(entity.to_ttl(prefix))
        lines.append("")

        # Add derivation relationships (wasGeneratedBy parents)
        parents = log.get_parents(event.event_id)
        for parent_id in parents:
            lines.append(
                f"{prefix}:{event.event_id} prov:wasDerivedFrom {prefix}:{parent_id} ."
            )

        # Add agent if author is present
        if event.author and event.author not in agents:
            agent = ProvAgent(
                identifier=f"agent_{event.author}",
                label=event.author,
                agent_type="prov:Person",
            )
            agents[event.author] = agent

        # Attribution
        if event.author:
            lines.append(
                f"{prefix}:{event.event_id} prov:wasAttributedTo "
                f"{prefix}:agent_{event.author} ."
            )

    # Add agents
    lines.append("")
    lines.append("# Agents")
    for agent in agents.values():
        lines.append(agent.to_ttl(prefix))
        lines.append("")

    return "\n".join(lines)


def export_prov_json(
    log: "EventLog",
    base_uri: str = "http://example.org/timeos/",
) -> str:
    """Export EventLog to PROV-O JSON-LD format.

    Args:
        log: EventLog to export
        base_uri: Base URI for identifiers

    Returns:
        JSON-LD string
    """
    context = {
        "prov": "http://www.w3.org/ns/prov#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "timeos": base_uri,
    }

    entities = []
    derivations = []
    agents: Dict[str, Dict] = {}
    attributions = []

    for event in log.query():
        entity = event_to_prov_entity(event)
        entity_dict = entity.to_dict()
        entity_dict["@id"] = f"timeos:{event.event_id}"
        entities.append(entity_dict)

        # Derivations
        parents = log.get_parents(event.event_id)
        for parent_id in parents:
            derivations.append({
                "@type": "prov:Derivation",
                "prov:entity": {"@id": f"timeos:{event.event_id}"},
                "prov:hadPrimarySource": {"@id": f"timeos:{parent_id}"},
            })

        # Agents and attributions
        if event.author:
            agent_id = f"timeos:agent_{event.author}"
            if event.author not in agents:
                agents[event.author] = {
                    "@id": agent_id,
                    "@type": "prov:Person",
                    "rdfs:label": event.author,
                }

            attributions.append({
                "@type": "prov:Attribution",
                "prov:entity": {"@id": f"timeos:{event.event_id}"},
                "prov:agent": {"@id": agent_id},
            })

    document = {
        "@context": context,
        "@graph": entities + list(agents.values()) + derivations + attributions,
    }

    return json.dumps(document, indent=2)


def export_timeline_prov(
    log: "EventLog",
    output_format: str = "ttl",
    base_uri: str = "http://example.org/timeos/",
) -> str:
    """Export EventLog to PROV format.

    Args:
        log: EventLog to export
        output_format: "ttl" for Turtle or "json" for JSON-LD
        base_uri: Base URI for identifiers

    Returns:
        Formatted provenance string
    """
    if output_format == "json":
        return export_prov_json(log, base_uri)
    else:
        return export_prov_ttl(log, base_uri)
