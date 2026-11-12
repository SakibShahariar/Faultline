"""Local SQLite storage with explicit schema versioning."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from .models import Boot, Event, Finding

SCHEMA_VERSION = 2


def default_database_path() -> Path:
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_home / "faultline" / "crashes.db"


class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self.path.parent.chmod(0o700)
        except OSError:
            pass
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self._migrate()
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def _migrate(self) -> None:
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(f"Database schema {version} is newer than supported {SCHEMA_VERSION}")
        if version < 1:
            with self.connection:
                self.connection.executescript("""
                    CREATE TABLE boots (
                        boot_id TEXT PRIMARY KEY,
                        first_seen TEXT,
                        last_seen TEXT,
                        boot_index INTEGER,
                        is_current INTEGER NOT NULL DEFAULT 0,
                        shutdown_status TEXT NOT NULL DEFAULT 'unknown'
                    );
                    CREATE TABLE events (
                        id INTEGER PRIMARY KEY,
                        boot_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        source TEXT NOT NULL,
                        unit TEXT,
                        priority INTEGER,
                        event_type TEXT NOT NULL,
                        message TEXT NOT NULL,
                        signature TEXT NOT NULL,
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        FOREIGN KEY (boot_id) REFERENCES boots(boot_id) ON DELETE CASCADE
                    );
                    CREATE INDEX events_boot_time ON events(boot_id, timestamp);
                    CREATE INDEX events_signature ON events(signature);
                    CREATE TABLE findings (
                        id INTEGER PRIMARY KEY,
                        boot_id TEXT NOT NULL,
                        category TEXT NOT NULL,
                        title TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        confidence TEXT NOT NULL,
                        evidence_json TEXT NOT NULL DEFAULT '[]',
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (boot_id) REFERENCES boots(boot_id) ON DELETE CASCADE
                    );
                    CREATE TABLE source_status (
                        source TEXT PRIMARY KEY,
                        available INTEGER NOT NULL,
                        detail TEXT NOT NULL,
                        checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    PRAGMA user_version = 1;
                """)
        if version < 2:
            with self.connection:
                self.connection.executescript("""
                    CREATE TABLE samples (
                        id INTEGER PRIMARY KEY,
                        boot_id TEXT NOT NULL,
                        captured_at TEXT NOT NULL,
                        cpu_percent REAL,
                        memory_used_bytes INTEGER,
                        memory_total_bytes INTEGER,
                        swap_used_bytes INTEGER,
                        swap_total_bytes INTEGER,
                        temperature_c REAL,
                        gpu_busy_percent REAL,
                        metadata_json TEXT NOT NULL DEFAULT '{}'
                    );
                    CREATE INDEX samples_time ON samples(captured_at);
                    CREATE INDEX samples_boot_time ON samples(boot_id, captured_at);
                    PRAGMA user_version = 2;
                """)

    def upsert_boot(self, boot: Boot) -> None:
        with self.connection:
            self.connection.execute("""
                INSERT INTO boots(boot_id, first_seen, last_seen, boot_index, is_current, shutdown_status)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(boot_id) DO UPDATE SET
                  first_seen=excluded.first_seen, last_seen=excluded.last_seen,
                  boot_index=excluded.boot_index, is_current=excluded.is_current,
                  shutdown_status=excluded.shutdown_status
            """, (boot.boot_id, boot.first_seen, boot.last_seen, boot.index,
                  int(boot.current), boot.shutdown_status))

    def add_events(self, events: Iterable[Event]) -> int:
        rows = [(e.boot_id, e.timestamp, e.source, e.unit, e.priority, e.event_type,
                 e.message, e.signature, json.dumps(e.metadata, sort_keys=True))
                for e in events]
        with self.connection:
            before = self.connection.total_changes
            self.connection.executemany("""
                INSERT INTO events(boot_id,timestamp,source,unit,priority,event_type,message,signature,metadata_json)
                SELECT ?,?,?,?,?,?,?,?,?
                WHERE NOT EXISTS (
                    SELECT 1 FROM events
                    WHERE boot_id=? AND timestamp=? AND source=? AND signature=?
                )
            """, [r + (r[0], r[1], r[2], r[7]) for r in rows])
            return self.connection.total_changes - before

    def add_findings(
        self,
        boot_id: str,
        findings: Iterable[Finding],
        replace_categories: Iterable[str] | None = None,
    ) -> None:
        rows = list(findings)
        categories = None if replace_categories is None else sorted(set(replace_categories))
        with self.connection:
            if categories is None:
                self.connection.execute("DELETE FROM findings WHERE boot_id = ?", (boot_id,))
            elif categories:
                placeholders = ",".join("?" for _ in categories)
                self.connection.execute(
                    f"DELETE FROM findings WHERE boot_id = ? AND category IN ({placeholders})",
                    [boot_id, *categories],
                )
            if rows:
                self.connection.executemany("""
                    INSERT INTO findings(boot_id,category,title,summary,confidence,evidence_json)
                    VALUES(?,?,?,?,?,?)
                """, [(boot_id, f.category, f.title, f.summary, f.confidence,
                       json.dumps(f.evidence)) for f in rows])

    def add_sample(self, sample: dict) -> None:
        with self.connection:
            self.connection.execute("""
                INSERT INTO samples(
                    boot_id,captured_at,cpu_percent,memory_used_bytes,memory_total_bytes,
                    swap_used_bytes,swap_total_bytes,temperature_c,gpu_busy_percent,metadata_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """, (
                sample["boot_id"], sample["captured_at"], sample.get("cpu_percent"),
                sample.get("memory_used_bytes"), sample.get("memory_total_bytes"),
                sample.get("swap_used_bytes"), sample.get("swap_total_bytes"),
                sample.get("temperature_c"), sample.get("gpu_busy_percent"),
                json.dumps(sample.get("metadata", {}), sort_keys=True),
            ))

    def latest_samples(self, limit: int = 100) -> list[sqlite3.Row]:
        limit = max(1, min(int(limit), 1000))
        return self.connection.execute(
            "SELECT * FROM samples ORDER BY captured_at DESC LIMIT ?", (limit,)
        ).fetchall()

    def prune_samples(self, retention_hours: int) -> int:
        cutoff = (datetime.now().astimezone() - timedelta(
            hours=max(1, min(int(retention_hours), 720))
        )).isoformat()
        with self.connection:
            cursor = self.connection.execute(
                "DELETE FROM samples WHERE captured_at < ?", (cutoff,)
            )
            return cursor.rowcount

    def set_source_status(self, source: str, available: bool, detail: str) -> None:
        with self.connection:
            self.connection.execute("""
                INSERT INTO source_status(source,available,detail,checked_at)
                VALUES(?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(source) DO UPDATE SET
                  available=excluded.available, detail=excluded.detail,
                  checked_at=CURRENT_TIMESTAMP
            """, (source, int(available), detail))

    def prune_old_boots(self, retention_days: int) -> int:
        """Delete records for boots older than the configured retention window."""
        cutoff = datetime.now() - timedelta(days=max(1, min(int(retention_days), 3650)))
        candidates = self.connection.execute(
            "SELECT boot_id, last_seen FROM boots WHERE is_current = 0"
        ).fetchall()
        expired = []
        for row in candidates:
            value = row["last_seen"]
            if not value:
                continue
            try:
                last_seen = datetime.strptime(value, "%a %Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if last_seen < cutoff:
                expired.append((row["boot_id"],))
        if expired:
            with self.connection:
                self.connection.executemany(
                    "DELETE FROM boots WHERE boot_id = ?", expired
                )
        return len(expired)

    def close(self) -> None:
        self.connection.close()
