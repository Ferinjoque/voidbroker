from __future__ import annotations

import pytest

from voidbroker.models import Item
from voidbroker.storage import Storage, backup_archive


def test_backup_creates_verified_copy(tmp_path):
    db = tmp_path / "archive.duckdb"
    s = Storage(db)
    s.upsert_items([Item(id="x", slug="x", name="X", tags=[])])
    s.close()  # release the write lock before copying

    dest = backup_archive(db, tmp_path / "backups")
    assert dest.exists()
    assert dest.parent.name == "backups"

    # The copy must be a real, queryable archive.
    copy = Storage(dest)
    assert copy.count("items") == 1
    copy.close()


def test_backup_rejects_memory_and_missing(tmp_path):
    with pytest.raises(ValueError):
        backup_archive(":memory:")
    with pytest.raises(ValueError):
        backup_archive(tmp_path / "does-not-exist.duckdb")


def test_backup_default_dir_is_beside_archive(tmp_path):
    db = tmp_path / "archive.duckdb"
    s = Storage(db)
    s.close()
    dest = backup_archive(db)
    assert dest.parent == tmp_path / "backups"
