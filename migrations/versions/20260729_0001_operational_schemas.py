"""Create operational metadata, audit, and quarantine schemas.

Revision ID: 20260729_0001
Revises:
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMAS = ("metadata", "raw", "staging", "core", "mart", "audit", "quarantine")


def _uuid_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
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
    )


def upgrade() -> None:
    """Create operational schemas, tables, constraints, and indexes."""

    for schema in SCHEMAS:
        op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    op.create_table(
        "source_system",
        _uuid_column("source_system_id"),
        sa.Column("source_system_code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("data_category", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.CheckConstraint(
            "data_category IN ('synthetic', 'public')",
            name="ck_source_system_data_category",
        ),
        sa.UniqueConstraint("source_system_code", name="uq_source_system_code"),
        schema="metadata",
    )

    op.create_table(
        "data_contract",
        _uuid_column("data_contract_id"),
        sa.Column(
            "source_system_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("metadata.source_system.source_system_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("contract_name", sa.String(255), nullable=False),
        sa.Column("contract_version", sa.String(50), nullable=False),
        sa.Column("contract_schema", postgresql.JSONB(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.UniqueConstraint(
            "source_system_id",
            "contract_name",
            "contract_version",
            name="uq_data_contract_source_name_version",
        ),
        schema="metadata",
    )

    op.create_table(
        "data_quality_rule",
        _uuid_column("rule_id"),
        sa.Column(
            "source_system_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("metadata.source_system.source_system_id", ondelete="CASCADE"),
        ),
        sa.Column("rule_code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("rule_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("configuration", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'error', 'critical')",
            name="ck_data_quality_rule_severity",
        ),
        sa.UniqueConstraint("rule_code", name="uq_data_quality_rule_code"),
        schema="metadata",
    )

    op.create_table(
        "pipeline_run",
        _uuid_column("pipeline_run_id"),
        sa.Column("pipeline_name", sa.String(255), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("records_discovered", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("records_loaded", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("records_rejected", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint(
            "records_discovered >= 0 AND records_loaded >= 0 AND records_rejected >= 0",
            name="ck_pipeline_run_nonnegative_counts",
        ),
        schema="audit",
    )
    op.create_index(
        "ix_pipeline_run_name_started_at",
        "pipeline_run",
        ["pipeline_name", "started_at"],
        schema="audit",
    )
    op.create_index(
        "ix_pipeline_run_status_started_at",
        "pipeline_run",
        ["status", "started_at"],
        schema="audit",
    )

    op.create_table(
        "source_file",
        _uuid_column("source_file_id"),
        sa.Column(
            "pipeline_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit.pipeline_run.pipeline_run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_system",
            sa.String(100),
            sa.ForeignKey("metadata.source_system.source_system_code"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(1024), nullable=False),
        sa.Column("object_path", sa.String(2048), nullable=False),
        sa.Column("sha256_checksum", sa.String(64), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("loaded_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("row_count", sa.BigInteger()),
        *_timestamps(),
        sa.CheckConstraint("file_size_bytes >= 0", name="ck_source_file_nonnegative_size"),
        sa.CheckConstraint(
            "row_count IS NULL OR row_count >= 0",
            name="ck_source_file_nonnegative_row_count",
        ),
        sa.CheckConstraint(
            "length(sha256_checksum) = 64",
            name="ck_source_file_sha256_length",
        ),
        sa.UniqueConstraint(
            "object_path", "sha256_checksum", name="uq_source_file_object_checksum"
        ),
        schema="audit",
    )
    op.create_index(
        "ix_source_file_pipeline_run",
        "source_file",
        ["pipeline_run_id"],
        schema="audit",
    )
    op.create_index(
        "ix_source_file_source_discovered",
        "source_file",
        ["source_system", "discovered_at"],
        schema="audit",
    )
    op.create_index(
        "ix_source_file_status",
        "source_file",
        ["status"],
        schema="audit",
    )

    op.create_table(
        "row_count_reconciliation",
        _uuid_column("row_count_reconciliation_id"),
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
        sa.Column("source_system", sa.String(100), nullable=False),
        sa.Column("stage_name", sa.String(100), nullable=False),
        sa.Column("expected_row_count", sa.BigInteger(), nullable=False),
        sa.Column("actual_row_count", sa.BigInteger(), nullable=False),
        sa.Column("difference", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "reconciled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        *_timestamps(),
        schema="audit",
    )
    op.create_index(
        "ix_row_count_reconciliation_run",
        "row_count_reconciliation",
        ["pipeline_run_id", "reconciled_at"],
        schema="audit",
    )
    op.create_index(
        "ix_row_count_reconciliation_status",
        "row_count_reconciliation",
        ["status"],
        schema="audit",
    )

    op.create_table(
        "access_event",
        _uuid_column("access_event_id"),
        sa.Column(
            "pipeline_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit.pipeline_run.pipeline_run_id", ondelete="SET NULL"),
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("actor_type", sa.String(50), nullable=False),
        sa.Column("actor_identifier", sa.String(255), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_name", sa.String(255), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("purpose", sa.String(255)),
        sa.Column("query_fingerprint", sa.String(64)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        schema="audit",
    )
    op.create_index(
        "ix_access_event_occurred_at",
        "access_event",
        ["occurred_at"],
        schema="audit",
    )
    op.create_index(
        "ix_access_event_actor_occurred",
        "access_event",
        ["actor_identifier", "occurred_at"],
        schema="audit",
    )
    op.create_index(
        "ix_access_event_resource_action",
        "access_event",
        ["resource_type", "resource_name", "action"],
        schema="audit",
    )

    op.create_table(
        "rejected_record",
        _uuid_column("rejected_record_id"),
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
        sa.Column("source_system", sa.String(100), nullable=False),
        sa.Column("source_row_number", sa.BigInteger(), nullable=False),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("metadata.data_quality_rule.rule_id"),
            nullable=False,
        ),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "resolution_status",
            sa.String(30),
            nullable=False,
            server_default="unresolved",
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolution_notes", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint(
            "source_row_number > 0",
            name="ck_rejected_record_positive_row_number",
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'error', 'critical')",
            name="ck_rejected_record_severity",
        ),
        schema="quarantine",
    )
    op.create_index(
        "ix_rejected_record_pipeline_run",
        "rejected_record",
        ["pipeline_run_id"],
        schema="quarantine",
    )
    op.create_index(
        "ix_rejected_record_source_file",
        "rejected_record",
        ["source_file_id"],
        schema="quarantine",
    )
    op.create_index(
        "ix_rejected_record_source_detected",
        "rejected_record",
        ["source_system", "detected_at"],
        schema="quarantine",
    )
    op.create_index(
        "ix_rejected_record_rule",
        "rejected_record",
        ["rule_id"],
        schema="quarantine",
    )
    op.create_index(
        "ix_rejected_record_resolution",
        "rejected_record",
        ["resolution_status", "detected_at"],
        schema="quarantine",
    )


def downgrade() -> None:
    """Drop operational tables and all project schemas."""

    op.drop_table("rejected_record", schema="quarantine")
    op.drop_table("access_event", schema="audit")
    op.drop_table("row_count_reconciliation", schema="audit")
    op.drop_table("source_file", schema="audit")
    op.drop_table("pipeline_run", schema="audit")
    op.drop_table("data_quality_rule", schema="metadata")
    op.drop_table("data_contract", schema="metadata")
    op.drop_table("source_system", schema="metadata")

    for schema in reversed(SCHEMAS):
        op.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}"'))
