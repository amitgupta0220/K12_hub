"""Create contract-driven staging tables and row reconciliation counts.

Revision ID: 20260729_0003
Revises: 20260729_0002
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0003"
down_revision: str | None = "20260729_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _staging_metadata(table_name: str) -> tuple[sa.Column, ...]:
    return (
        sa.Column(
            "staging_row_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "pipeline_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit.pipeline_run.pipeline_run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit.source_file.source_file_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_row_number", sa.BigInteger(), nullable=False),
        sa.Column("source_schema_version", sa.String(50), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "source_row_number > 0",
            name=f"ck_{table_name}_positive_source_row_number",
        ),
        sa.UniqueConstraint(
            "source_file_id",
            "source_row_number",
            name=f"uq_{table_name}_source_file_row_number",
        ),
    )


def _create_staging_table(name: str, *business_columns: sa.Column) -> None:
    op.create_table(
        name,
        *_staging_metadata(name),
        *business_columns,
        schema="staging",
    )
    op.create_index(
        f"ix_{name}_pipeline_run",
        name,
        ["pipeline_run_id"],
        schema="staging",
    )


def upgrade() -> None:
    """Create typed staging destinations and retry-safe audit constraints."""

    _create_staging_table(
        "sis_student",
        sa.Column("student_id", sa.Text(), nullable=False),
        sa.Column("local_student_number", sa.Text(), nullable=False),
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("last_name", sa.Text(), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("gender", sa.Text()),
        sa.Column("grade_level", sa.Text(), nullable=False),
        sa.Column("district_id", sa.Text(), nullable=False),
        sa.Column("school_id", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    _create_staging_table(
        "sis_enrollment",
        sa.Column("enrollment_id", sa.Text(), nullable=False),
        sa.Column("student_id", sa.Text(), nullable=False),
        sa.Column("district_id", sa.Text(), nullable=False),
        sa.Column("school_id", sa.Text(), nullable=False),
        sa.Column("academic_year", sa.Text(), nullable=False),
        sa.Column("grade_level", sa.Text(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("exit_date", sa.Date()),
        sa.Column("enrollment_status", sa.Text(), nullable=False),
    )
    _create_staging_table(
        "attendance_event",
        sa.Column("student_id", sa.Text(), nullable=False),
        sa.Column("district_id", sa.Text(), nullable=False),
        sa.Column("school_id", sa.Text(), nullable=False),
        sa.Column("instructional_date", sa.Date(), nullable=False),
        sa.Column("attendance_status", sa.Text(), nullable=False),
        sa.Column("minutes_attended", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.Text()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_staging_table(
        "assessment_event",
        sa.Column("assessment_event_id", sa.Text(), nullable=False),
        sa.Column("student_id", sa.Text(), nullable=False),
        sa.Column("district_id", sa.Text(), nullable=False),
        sa.Column("school_id", sa.Text(), nullable=False),
        sa.Column("academic_year", sa.Text(), nullable=False),
        sa.Column("assessment_name", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("assessment_date", sa.Date(), nullable=False),
        sa.Column("scale_score", sa.Numeric(), nullable=False),
        sa.Column("performance_level", sa.Text(), nullable=False),
    )

    for column_name in (
        "discovered_row_count",
        "parsed_row_count",
        "loaded_row_count",
        "rejected_row_count",
    ):
        op.add_column(
            "row_count_reconciliation",
            sa.Column(column_name, sa.BigInteger(), nullable=False, server_default="0"),
            schema="audit",
        )
    op.create_unique_constraint(
        "uq_row_count_reconciliation_source_stage",
        "row_count_reconciliation",
        ["source_file_id", "stage_name"],
        schema="audit",
    )
    op.create_unique_constraint(
        "uq_rejected_record_source_row_rule",
        "rejected_record",
        ["source_file_id", "source_row_number", "rule_id"],
        schema="quarantine",
    )


def downgrade() -> None:
    """Remove staging destinations and Prompt 7 reconciliation fields."""

    op.drop_constraint(
        "uq_rejected_record_source_row_rule",
        "rejected_record",
        schema="quarantine",
        type_="unique",
    )
    op.drop_constraint(
        "uq_row_count_reconciliation_source_stage",
        "row_count_reconciliation",
        schema="audit",
        type_="unique",
    )
    for column_name in (
        "rejected_row_count",
        "loaded_row_count",
        "parsed_row_count",
        "discovered_row_count",
    ):
        op.drop_column("row_count_reconciliation", column_name, schema="audit")
    for table_name in (
        "assessment_event",
        "attendance_event",
        "sis_enrollment",
        "sis_student",
    ):
        op.drop_table(table_name, schema="staging")
