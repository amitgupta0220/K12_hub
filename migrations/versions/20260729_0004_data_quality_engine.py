"""Add configuration-driven data-quality audit persistence.

Revision ID: 20260729_0004
Revises: 20260729_0003
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0004"
down_revision: str | None = "20260729_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_primary_key(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def upgrade() -> None:
    """Create rule-run, aggregate-result, and row-failure audit structures."""

    op.alter_column(
        "sis_student",
        "student_id",
        schema="staging",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.add_column(
        "data_quality_rule",
        sa.Column("dataset", sa.String(255), nullable=False, server_default="legacy"),
        schema="metadata",
    )
    op.add_column(
        "data_quality_rule",
        sa.Column("blocking", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema="metadata",
    )
    op.add_column(
        "data_quality_rule",
        sa.Column(
            "remediation_guidance",
            sa.Text(),
            nullable=False,
            server_default="Review and correct the source record.",
        ),
        schema="metadata",
    )

    op.add_column(
        "rejected_record",
        sa.Column("rule_code", sa.String(20), nullable=False, server_default="LEGACY"),
        schema="quarantine",
    )
    op.add_column(
        "rejected_record",
        sa.Column(
            "remediation_guidance",
            sa.Text(),
            nullable=False,
            server_default="Review and correct the source record.",
        ),
        schema="quarantine",
    )
    op.drop_constraint(
        "ck_rejected_record_positive_row_number",
        "rejected_record",
        schema="quarantine",
        type_="check",
    )
    op.alter_column(
        "rejected_record",
        "source_file_id",
        schema="quarantine",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_rejected_record_nonnegative_row_number",
        "rejected_record",
        "source_row_number >= 0",
        schema="quarantine",
    )

    op.create_table(
        "data_quality_rule_run",
        _uuid_primary_key("data_quality_rule_run_id"),
        sa.Column(
            "pipeline_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit.pipeline_run.pipeline_run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("enabled_rule_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evaluated_row_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("blocking_failure_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        schema="audit",
    )
    op.create_index(
        "ix_data_quality_rule_run_pipeline",
        "data_quality_rule_run",
        ["pipeline_run_id", "started_at"],
        schema="audit",
    )

    op.create_table(
        "data_quality_rule_result",
        _uuid_primary_key("data_quality_rule_result_id"),
        sa.Column(
            "data_quality_rule_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "audit.data_quality_rule_run.data_quality_rule_run_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "pipeline_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit.pipeline_run.pipeline_run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("metadata.data_quality_rule.rule_id"),
            nullable=False,
        ),
        sa.Column("rule_code", sa.String(20), nullable=False),
        sa.Column("dataset", sa.String(255), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("evaluated_row_count", sa.BigInteger(), nullable=False),
        sa.Column("failure_count", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "data_quality_rule_run_id",
            "rule_id",
            name="uq_data_quality_rule_result_run_rule",
        ),
        schema="audit",
    )
    op.create_index(
        "ix_data_quality_rule_result_pipeline_rule",
        "data_quality_rule_result",
        ["pipeline_run_id", "rule_code"],
        schema="audit",
    )

    op.create_table(
        "data_quality_failure",
        _uuid_primary_key("data_quality_failure_id"),
        sa.Column(
            "data_quality_rule_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "audit.data_quality_rule_run.data_quality_rule_run_id",
                ondelete="CASCADE",
            ),
            nullable=False,
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
        ),
        sa.Column("source_row_number", sa.BigInteger(), nullable=False),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("metadata.data_quality_rule.rule_id"),
            nullable=False,
        ),
        sa.Column("rule_code", sa.String(20), nullable=False),
        sa.Column("dataset", sa.String(255), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("remediation_guidance", sa.Text(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "source_row_number >= 0",
            name="ck_data_quality_failure_nonnegative_row_number",
        ),
        schema="audit",
    )
    op.create_index(
        "ix_data_quality_failure_pipeline_rule",
        "data_quality_failure",
        ["pipeline_run_id", "rule_code"],
        schema="audit",
    )
    op.create_index(
        "ix_data_quality_failure_source_row",
        "data_quality_failure",
        ["source_file_id", "source_row_number"],
        schema="audit",
    )


def downgrade() -> None:
    """Remove Prompt 8 data-quality persistence."""

    op.drop_table("data_quality_failure", schema="audit")
    op.drop_table("data_quality_rule_result", schema="audit")
    op.drop_table("data_quality_rule_run", schema="audit")

    op.drop_constraint(
        "ck_rejected_record_nonnegative_row_number",
        "rejected_record",
        schema="quarantine",
        type_="check",
    )
    op.alter_column(
        "rejected_record",
        "source_file_id",
        schema="quarantine",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.create_check_constraint(
        "ck_rejected_record_positive_row_number",
        "rejected_record",
        "source_row_number > 0",
        schema="quarantine",
    )
    op.drop_column("rejected_record", "remediation_guidance", schema="quarantine")
    op.drop_column("rejected_record", "rule_code", schema="quarantine")
    op.drop_column("data_quality_rule", "remediation_guidance", schema="metadata")
    op.drop_column("data_quality_rule", "blocking", schema="metadata")
    op.drop_column("data_quality_rule", "dataset", schema="metadata")
    op.alter_column(
        "sis_student",
        "student_id",
        schema="staging",
        existing_type=sa.Text(),
        nullable=False,
    )
