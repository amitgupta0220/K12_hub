"""Index loaded-file checksum lookups.

Revision ID: 20260729_0002
Revises: 20260729_0001
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260729_0002"
down_revision: str | None = "20260729_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the checksum/status index used by duplicate detection."""

    op.create_index(
        "ix_source_file_source_checksum_status",
        "source_file",
        ["source_system", "sha256_checksum", "status"],
        schema="audit",
    )


def downgrade() -> None:
    """Remove the duplicate-detection lookup index."""

    op.drop_index(
        "ix_source_file_source_checksum_status",
        table_name="source_file",
        schema="audit",
    )
