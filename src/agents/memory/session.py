import json
from typing import List, Dict, Any
from datetime import datetime

import aiosqlite


class SQLiteSession:
    """Very small async session store backed by SQLite.

    Stores each conversation item as a JSON blob keyed by session_id and an
    auto-incrementing id, preserving order. Designed to match the simple
    needs of `core.agent.AIAgent` (methods: get_items, add_items).
    """

    def __init__(self, session_id: str, db_path: str):
        self.session_id = session_id
        self.db_path = db_path
        self._initialized = False

    async def _init(self):
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS session_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    data TEXT NOT NULL
                )
                """
            )
            await db.commit()
        self._initialized = True

    async def add_items(self, items: List[Dict[str, Any]]):
        """Append items to the session history."""
        if not items:
            return
        await self._init()
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                "INSERT INTO session_items (session_id, created_at, data) VALUES (?, ?, ?)",
                [
                    (self.session_id, now, json.dumps(item, ensure_ascii=False))
                    for item in items
                ],
            )
            await db.commit()

    async def get_items(self) -> List[Dict[str, Any]]:
        """Return session history in insertion order as a list of dicts."""
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT data FROM session_items WHERE session_id = ? ORDER BY id ASC",
                (self.session_id,),
            ) as cursor:
                rows = await cursor.fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            try:
                result.append(json.loads(row["data"]))
            except Exception:
                # If a row can't be parsed, skip it rather than failing the agent
                continue
        return result
