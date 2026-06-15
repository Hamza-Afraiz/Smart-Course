"""In-process schema registry for domain events.

Enforces the discipline a Kafka Schema Registry gives you — events are versioned
contracts and the producer is rejected if a payload doesn't conform — without
standing up the Confluent service. For a single-team system this is the
high-value slice: producer-side contract validation + a BACKWARD-compatibility
check to run when evolving a schema. Moving to Confluent SR + Avro later is a
serialization change at the relay/producer, not a redesign.

See docs/QA.md (2026-06-09) for why the full Confluent stack is deferred here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SchemaValidationError(Exception):
    """Raised when an event payload violates its registered contract."""


@dataclass(frozen=True)
class EventSchema:
    event_type: str
    version: int
    fields: dict[str, type]  # field name → expected python type
    required: frozenset[str]


_REGISTRY: dict[str, EventSchema] = {
    "user.enrolled": EventSchema(
        event_type="user.enrolled",
        version=1,
        fields={
            "enrollment_id": str,
            "student_id": str,
            "course_id": str,
            "enrolled_at": str,
        },
        required=frozenset({"enrollment_id", "student_id", "course_id"}),
    ),
    "lesson.completed": EventSchema(
        event_type="lesson.completed",
        version=1,
        fields={
            "progress_id": str,
            "enrollment_id": str,
            "student_id": str,
            "course_id": str,
            "lesson_id": str,
            "completed_at": str,
        },
        required=frozenset(
            {"progress_id", "enrollment_id", "student_id", "course_id", "lesson_id"}
        ),
    ),
    "course.published": EventSchema(
        event_type="course.published",
        version=1,
        fields={
            "course_id": str,
            "workflow_run_id": str,
            "published_at": str,
        },
        required=frozenset({"course_id", "workflow_run_id", "published_at"}),
    ),
}


def get_schema(event_type: str) -> EventSchema:
    schema = _REGISTRY.get(event_type)
    if schema is None:
        raise SchemaValidationError(f"no schema registered for event '{event_type}'")
    return schema


def validate(event_type: str, payload: dict[str, Any]) -> None:
    """Producer-side gate: reject a payload that violates its contract.

    Mirrors a Schema Registry rejecting an incompatible produce — a failure here
    means the producer built a wrong payload (a bug), surfaced at emit time
    instead of as a downstream consumer crash on a fraction of messages.
    """
    schema = get_schema(event_type)

    missing = schema.required - payload.keys()
    if missing:
        raise SchemaValidationError(
            f"{event_type}: missing required field(s) {sorted(missing)}"
        )

    for field, value in payload.items():
        expected = schema.fields.get(field)
        if expected is None:
            raise SchemaValidationError(
                f"{event_type}: unknown field '{field}' (not in schema v{schema.version})"
            )
        # optional fields may be null; required ones are guaranteed present above
        if value is not None and not isinstance(value, expected):
            raise SchemaValidationError(
                f"{event_type}.{field}: expected {expected.__name__}, "
                f"got {type(value).__name__}"
            )


def is_backward_compatible(old: EventSchema, new: EventSchema) -> bool:
    """True if a consumer on `new` can read data produced with `old` (BACKWARD).

    Allowed: drop a field, add an *optional* field, keep types.
    Forbidden: add a *required* field (old data lacks it), change a field's type.
    """
    for field in new.required:
        if field not in old.fields:
            return False
    for field, ftype in new.fields.items():
        if field in old.fields and old.fields[field] != ftype:
            return False
    return True
