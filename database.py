from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

POINTS_PER_PACK = 50_000
RARITY_ODDS = {"Common": 50, "Rare": 27, "Epic": 15, "Legendary": 7, "Mythic": 1}

STARTER_CARDS: list[dict[str, Any]] = [
    {"name": "OG Vanguard", "rarity": "Common", "theme": "Clan Member", "edition": "Base", "ovr": 72, "pac": 70, "atk": 73, "deff": 69, "skl": 71},
    {"name": "Dragon Scout", "rarity": "Common", "theme": "Fantasy Creature", "edition": "Base", "ovr": 74, "pac": 78, "atk": 70, "deff": 66, "skl": 75},
    {"name": "OG Tactician", "rarity": "Rare", "theme": "Clan Member", "edition": "Base", "ovr": 80, "pac": 73, "atk": 79, "deff": 78, "skl": 82},
    {"name": "Ember Drake", "rarity": "Rare", "theme": "Fantasy Creature", "edition": "Base", "ovr": 81, "pac": 82, "atk": 84, "deff": 73, "skl": 79},
    {"name": "OG Trailblazer", "rarity": "Epic", "theme": "Clan Legend", "edition": "Base", "ovr": 87, "pac": 86, "atk": 88, "deff": 81, "skl": 85},
    {"name": "Storm Wyrm", "rarity": "Epic", "theme": "Fantasy Creature", "edition": "Base", "ovr": 89, "pac": 91, "atk": 90, "deff": 82, "skl": 87},
    {"name": "OG Sovereign", "rarity": "Legendary", "theme": "Clan Legend", "edition": "Base", "ovr": 94, "pac": 92, "atk": 95, "deff": 91, "skl": 94},
    {"name": "Astral Dragon", "rarity": "Legendary", "theme": "Fantasy Creature", "edition": "Base", "ovr": 96, "pac": 95, "atk": 97, "deff": 92, "skl": 96},
    {"name": "OG Eternal", "rarity": "Mythic", "theme": "Special Edition", "edition": "Launch Mythic", "ovr": 99, "pac": 98, "atk": 99, "deff": 97, "skl": 99},
]

class CardStore:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def _init_db(self) -> None:
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS profiles (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    points_total INTEGER NOT NULL DEFAULT 0 CHECK(points_total >= 0),
                    points_progress INTEGER NOT NULL DEFAULT 0 CHECK(points_progress >= 0 AND points_progress < 50000),
                    packs INTEGER NOT NULL DEFAULT 0 CHECK(packs >= 0),
                    PRIMARY KEY(guild_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS card_instances (
                    instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL, owner_id INTEGER NOT NULL,
                    name TEXT NOT NULL, rarity TEXT NOT NULL, theme TEXT NOT NULL, edition TEXT NOT NULL,
                    ovr INTEGER NOT NULL, pac INTEGER NOT NULL, atk INTEGER NOT NULL, deff INTEGER NOT NULL, skl INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_cards_owner ON card_instances(guild_id, owner_id, instance_id DESC);
                CREATE TABLE IF NOT EXISTS point_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                    actor_id INTEGER NOT NULL, amount INTEGER NOT NULL CHECK(amount > 0),
                    reason TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)

    @staticmethod
    def _ensure_profile(db: sqlite3.Connection, guild_id: int, user_id: int) -> None:
        db.execute("INSERT OR IGNORE INTO profiles(guild_id,user_id) VALUES(?,?)", (guild_id, user_id))

    def get_profile(self, guild_id: int | None, user_id: int) -> dict[str, int]:
        if guild_id is None:
            return {"points_total": 0, "progress": 0, "packs": 0, "card_count": 0}
        with self.connect() as db:
            self._ensure_profile(db, guild_id, user_id)
            row = db.execute("SELECT points_total,points_progress,packs FROM profiles WHERE guild_id=? AND user_id=?", (guild_id,user_id)).fetchone()
            count = db.execute("SELECT COUNT(*) AS n FROM card_instances WHERE guild_id=? AND owner_id=?", (guild_id,user_id)).fetchone()["n"]
            return {"points_total": row["points_total"], "progress": row["points_progress"], "packs": row["packs"], "card_count": count}

    def credit_points(self, guild_id: int, user_id: int, amount: int, actor_id: int, reason: str) -> int:
        if amount <= 0:
            raise ValueError("Points amount must be positive")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._ensure_profile(db, guild_id, user_id)
            db.execute("INSERT INTO point_ledger(guild_id,user_id,actor_id,amount,reason) VALUES(?,?,?,?,?)", (guild_id,user_id,actor_id,amount,reason))
            row = db.execute("SELECT points_total,points_progress,packs FROM profiles WHERE guild_id=? AND user_id=?", (guild_id,user_id)).fetchone()
            earned_packs, remainder = divmod(row["points_progress"] + amount, POINTS_PER_PACK)
            db.execute("UPDATE profiles SET points_total=?,points_progress=?,packs=? WHERE guild_id=? AND user_id=?", (row["points_total"]+amount,remainder,row["packs"]+earned_packs,guild_id,user_id))
            return earned_packs

    def consume_pack(self, guild_id: int, user_id: int) -> bool:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._ensure_profile(db, guild_id, user_id)
            row = db.execute("SELECT packs FROM profiles WHERE guild_id=? AND user_id=?", (guild_id,user_id)).fetchone()
            if row["packs"] < 1:
                return False
            db.execute("UPDATE profiles SET packs=packs-1 WHERE guild_id=? AND user_id=?", (guild_id,user_id))
            return True

    def add_card(self, guild_id: int, user_id: int, card: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as db:
            cur = db.execute("""INSERT INTO card_instances(guild_id,owner_id,name,rarity,theme,edition,ovr,pac,atk,deff,skl)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (guild_id,user_id,card["name"],card["rarity"],card["theme"],card["edition"],card["ovr"],card["pac"],card["atk"],card["deff"],card["skl"]))
            return {"instance_id": cur.lastrowid, **card}

    def get_collection(self, guild_id: int | None, user_id: int, limit: int = 15) -> list[dict[str, Any]]:
        if guild_id is None:
            return []
        with self.connect() as db:
            rows = db.execute("SELECT * FROM card_instances WHERE guild_id=? AND owner_id=? ORDER BY instance_id DESC LIMIT ?", (guild_id,user_id,limit)).fetchall()
            return [dict(row) for row in rows]

    def get_recent_audit(self, guild_id: int | None, limit: int = 10) -> list[dict[str, Any]]:
        if guild_id is None:
            return []
        with self.connect() as db:
            rows = db.execute("SELECT user_id,actor_id,amount,reason FROM point_ledger WHERE guild_id=? ORDER BY id DESC LIMIT ?", (guild_id,limit)).fetchall()
            return [dict(row) for row in rows]
