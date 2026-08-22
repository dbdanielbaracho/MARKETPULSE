import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app.storage.maintenance import DatabaseMaintenance


def _database(path):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE events(id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        connection.executemany("INSERT INTO events(value) VALUES (?)", [("a",), ("b",)])


def test_online_backup_integrity_restore_and_retention(tmp_path):
    database = tmp_path / "active.db"
    backups = tmp_path / "backups"
    _database(database)
    maintenance = DatabaseMaintenance(str(database), str(backups), retention=2)
    now = datetime.now(timezone.utc)

    first = maintenance.backup(now - timedelta(days=2))
    second = maintenance.backup(now - timedelta(days=1))
    latest = maintenance.backup(now)

    assert latest.integrity == "ok"
    assert latest.size_bytes > 0
    assert latest.retained == 2
    assert not (backups / first.path.split("/")[-1]).exists()
    assert (backups / second.path.split("/")[-1]).exists()

    restored = tmp_path / "restore" / "verified.db"
    assert maintenance.verify_restore(latest.path, str(restored)) == "ok"
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT value FROM events ORDER BY id").fetchall() == [("a",), ("b",)]


def test_backup_rejects_missing_source_and_naive_time(tmp_path):
    maintenance = DatabaseMaintenance(str(tmp_path / "missing.db"), str(tmp_path / "backups"))
    with pytest.raises(FileNotFoundError):
        maintenance.backup()

    database = tmp_path / "active.db"
    _database(database)
    maintenance = DatabaseMaintenance(str(database), str(tmp_path / "backups"))
    with pytest.raises(ValueError):
        maintenance.backup(datetime.now())


def test_restore_never_overwrites_existing_file(tmp_path):
    database = tmp_path / "active.db"
    _database(database)
    maintenance = DatabaseMaintenance(str(database), str(tmp_path / "backups"))
    backup = maintenance.backup()
    existing = tmp_path / "existing.db"
    existing.write_text("preserve", encoding="utf-8")

    with pytest.raises(FileExistsError):
        maintenance.verify_restore(backup.path, str(existing))
    assert existing.read_text(encoding="utf-8") == "preserve"
