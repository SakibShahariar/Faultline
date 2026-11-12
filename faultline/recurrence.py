"""Cross-boot recurrence queries over normalized event signatures."""
from __future__ import annotations

from .storage import Database


def find_recurring_events(db: Database, minimum_boots: int = 2) -> list[dict]:
    minimum_boots = max(2, min(int(minimum_boots), 100))
    rows = db.connection.execute("""
        SELECT signature,
               COUNT(*) AS event_count,
               COUNT(DISTINCT boot_id) AS boot_count,
               MIN(timestamp) AS first_seen,
               MAX(timestamp) AS last_seen,
               MIN(source) AS source,
               GROUP_CONCAT(DISTINCT source) AS sources,
               COUNT(DISTINCT source) AS source_count,
               MIN(message) AS example
        FROM events
        WHERE signature != ''
        GROUP BY signature
        HAVING COUNT(DISTINCT boot_id) >= ?
        ORDER BY boot_count DESC, event_count DESC, last_seen DESC
    """, (minimum_boots,)).fetchall()
    return [dict(row) for row in rows]
