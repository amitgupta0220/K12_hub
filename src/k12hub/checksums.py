"""Streaming checksums for source-file ingestion."""

from __future__ import annotations

import hashlib
from pathlib import Path

CHECKSUM_CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    """Calculate a file's SHA-256 checksum without loading it all into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        while chunk := source_file.read(CHECKSUM_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()
