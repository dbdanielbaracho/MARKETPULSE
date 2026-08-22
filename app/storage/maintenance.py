from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class BackupResult:
    path: str
    created_at: datetime
    size_bytes: int
    integrity: str
    retained: int


class DatabaseMaintenance:
    """Online SQLite backup, integrity verification and bounded retention."""

    def __init__(self, database_path: str, backup_directory: str, retention: int = 7) -> None:
        self.database_path = Path(database_path)
        self.backup_directory = Path(backup_directory)
        if retention < 1 or retention > 90:
            raise ValueError("backup retention must be between 1 and 90")
        self.retention = retention

    @staticmethod
    def integrity(path: str | Path) -> str:
        target = Path(path)
        if not target.is_file():
            raise FileNotFoundError(str(target))
        uri = f"file:{target.resolve()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=10) as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()
        result = str(row[0] if row else "missing_result")
        if result != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {result}")
        return result

    def backup(self, now: datetime | None = None) -> BackupResult:
        if not self.database_path.is_file():
            raise FileNotFoundError(str(self.database_path))
        created_at = now or datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            raise ValueError("backup time must be timezone-aware")
        self.backup_directory.mkdir(parents=True, exist_ok=True)
        if self.backup_directory.resolve() == self.database_path.resolve():
            raise ValueError("backup directory cannot be the database file")
        stamp = created_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = self.backup_directory / f"predibeacon-{stamp}-{uuid4().hex[:8]}.db"
        try:
            with sqlite3.connect(self.database_path, timeout=10) as source:
                with sqlite3.connect(destination, timeout=10) as target:
                    source.backup(target, pages=256)
            integrity = self.integrity(destination)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        backups = sorted(
            self.backup_directory.glob("predibeacon-*.db"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for expired in backups[self.retention :]:
            expired.unlink(missing_ok=True)
        retained = len(list(self.backup_directory.glob("predibeacon-*.db")))
        return BackupResult(
            path=str(destination),
            created_at=created_at.astimezone(timezone.utc),
            size_bytes=destination.stat().st_size,
            integrity=integrity,
            retained=retained,
        )

    def verify_restore(self, backup_path: str, restore_path: str) -> str:
        source = Path(backup_path)
        destination = Path(restore_path)
        if destination.exists():
            raise FileExistsError(str(destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(source, timeout=10) as backup:
                with sqlite3.connect(destination, timeout=10) as restored:
                    backup.backup(restored, pages=256)
            return self.integrity(destination)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
