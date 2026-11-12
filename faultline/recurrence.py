"""Cross-boot recurrence queries over normalized event signatures."""
from __future__ import annotations

from .storage import Database


def find_recurring_events(
    db: Database,
    minimum_boots: int = 2,
    max_groups: int = 25,
    max_occurrences: int = 100,
) -> list[dict]:
    minimum_boots = max(2, min(int(minimum_boots), 100))
    max_groups = max(1, min(int(max_groups), 100))
    max_occurrences = max(1, min(int(max_occurrences), 500))
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
        LIMIT ?
    """, (minimum_boots, max_groups)).fetchall()

    recurring = []
    for row in rows:
        item = dict(row)
        item["occurrences"] = [
            dict(event) for event in db.connection.execute("""
                SELECT boot_id, timestamp, source, message
                FROM events WHERE signature = ?
                ORDER BY timestamp, boot_id LIMIT ?
            """, (item["signature"], max_occurrences)).fetchall()
        ]
        item["occurrences_truncated"] = item["event_count"] > len(item["occurrences"])
        recurring.append(item)
    return recurring
