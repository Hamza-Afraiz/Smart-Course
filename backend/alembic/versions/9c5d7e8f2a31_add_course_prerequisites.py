"""add course_prerequisites table

Revision ID: 9c5d7e8f2a31
Revises: 8b2c4d6e1f90
Create Date: 2026-06-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9c5d7e8f2a31"
down_revision: str | None = "8b2c4d6e1f90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_prerequisites",
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prerequisite_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["prerequisite_id"], ["courses.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("course_id", "prerequisite_id"),
        sa.CheckConstraint(
            "course_id <> prerequisite_id", name="ck_course_prereq_no_self"
        ),
    )
    # reverse lookups: "what courses depend on this one"
    op.create_index(
        "idx_course_prereq_prerequisite",
        "course_prerequisites",
        ["prerequisite_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_course_prereq_prerequisite", table_name="course_prerequisites"
    )
    op.drop_table("course_prerequisites")
