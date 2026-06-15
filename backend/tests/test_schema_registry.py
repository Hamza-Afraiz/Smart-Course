import pytest

from app.events import schema_registry as sr
from app.events.schema_registry import EventSchema, SchemaValidationError


def _valid_enrolled() -> dict:
    return {
        "enrollment_id": "e1",
        "student_id": "s1",
        "course_id": "c1",
        "enrolled_at": "2026-01-01T00:00:00Z",
    }


# ── Producer-side validation ──────────────────────────────────────────────────


def test_valid_user_enrolled_passes():
    sr.validate("user.enrolled", _valid_enrolled())


def test_optional_field_may_be_null():
    payload = _valid_enrolled()
    payload["enrolled_at"] = None
    sr.validate("user.enrolled", payload)


def test_missing_required_field_rejected():
    payload = _valid_enrolled()
    del payload["student_id"]
    with pytest.raises(SchemaValidationError):
        sr.validate("user.enrolled", payload)


def test_wrong_type_rejected():
    payload = _valid_enrolled()
    payload["course_id"] = 123
    with pytest.raises(SchemaValidationError):
        sr.validate("user.enrolled", payload)


def test_unknown_field_rejected():
    payload = _valid_enrolled()
    payload["studnet_id"] = "typo"  # producer typo — exactly what the gate catches
    with pytest.raises(SchemaValidationError):
        sr.validate("user.enrolled", payload)


def test_unknown_event_type_rejected():
    with pytest.raises(SchemaValidationError):
        sr.validate("user.deleted", {})


def test_every_emitted_event_has_a_schema():
    for event_type in ("user.enrolled", "lesson.completed", "course.published"):
        assert sr.get_schema(event_type).version >= 1


# ── BACKWARD compatibility (schema evolution) ─────────────────────────────────


def _schema(fields: dict, required: set, version: int = 1) -> EventSchema:
    return EventSchema("evt", version, fields, frozenset(required))


def test_adding_optional_field_is_backward_compatible():
    old = _schema({"a": str}, {"a"})
    new = _schema({"a": str, "b": str}, {"a"}, version=2)
    assert sr.is_backward_compatible(old, new)


def test_dropping_field_is_backward_compatible():
    old = _schema({"a": str, "b": str}, {"a"})
    new = _schema({"a": str}, {"a"}, version=2)
    assert sr.is_backward_compatible(old, new)


def test_adding_required_field_is_not_backward_compatible():
    old = _schema({"a": str}, {"a"})
    new = _schema({"a": str, "b": str}, {"a", "b"}, version=2)
    assert not sr.is_backward_compatible(old, new)


def test_changing_field_type_is_not_backward_compatible():
    old = _schema({"a": str}, {"a"})
    new = _schema({"a": int}, {"a"}, version=2)
    assert not sr.is_backward_compatible(old, new)
