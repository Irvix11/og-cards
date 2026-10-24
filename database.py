from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

POINTS_PER_PACK = 10_000
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
                    points_progress INTEGER NOT NULL DEFAULT 0 CHECK(points_progress >= 0 AND points_progress < 10000),
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
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    proposer_id INTEGER NOT NULL,
                    recipient_id INTEGER NOT NULL,
                    proposer_card_id INTEGER NOT NULL,
                    recipient_card_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','cancelled','declined','expired')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT NOT NULL DEFAULT (datetime('now', '+24 hours')),
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_trades_pending ON trades(guild_id, status, trade_id);
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


    def open_pack_with_card(self, guild_id: int, user_id: int, card: dict[str, Any]) -> dict[str, Any] | None:
        """Consume a pack and insert its card in one transaction, preventing lost packs."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._ensure_profile(db, guild_id, user_id)
            profile = db.execute(
                "SELECT packs FROM profiles WHERE guild_id=? AND user_id=?",
                (guild_id, user_id),
            ).fetchone()
            if profile["packs"] < 1:
                return None
            db.execute(
                "UPDATE profiles SET packs=packs-1 WHERE guild_id=? AND user_id=?",
                (guild_id, user_id),
            )
            cur = db.execute(
                """INSERT INTO card_instances
                (guild_id,owner_id,name,rarity,theme,edition,ovr,pac,atk,deff,skl)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (guild_id,user_id,card["name"],card["rarity"],card["theme"],card["edition"],
                 card["ovr"],card["pac"],card["atk"],card["deff"],card["skl"]),
            )
            return {"instance_id": cur.lastrowid, **card}

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


    def _card_is_locked(self, db: sqlite3.Connection, guild_id: int, card_id: int) -> bool:
        row = db.execute(
            """SELECT 1 FROM trades WHERE guild_id=? AND status='pending'
            AND (proposer_card_id=? OR recipient_card_id=?) AND expires_at > datetime('now') LIMIT 1""",
            (guild_id, card_id, card_id),
        ).fetchone()
        return row is not None

    def create_trade(self, guild_id: int, proposer_id: int, recipient_id: int,
                     proposer_card_id: int, recipient_card_id: int) -> dict[str, Any]:
        if proposer_id == recipient_id:
            raise ValueError("You cannot trade with yourself.")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            offered = db.execute("SELECT * FROM card_instances WHERE guild_id=? AND instance_id=? AND owner_id=?",
                                 (guild_id, proposer_card_id, proposer_id)).fetchone()
            requested = db.execute("SELECT * FROM card_instances WHERE guild_id=? AND instance_id=? AND owner_id=?",
                                   (guild_id, recipient_card_id, recipient_id)).fetchone()
            if offered is None:
                raise ValueError("You don't own the card you offered.")
            if requested is None:
                raise ValueError("That member doesn't own the requested card.")
            if self._card_is_locked(db, guild_id, proposer_card_id) or self._card_is_locked(db, guild_id, recipient_card_id):
                raise ValueError("One of those cards is already locked in a pending trade.")
            cur = db.execute(
                """INSERT INTO trades(guild_id,proposer_id,recipient_id,proposer_card_id,recipient_card_id)
                VALUES(?,?,?,?,?)""",
                (guild_id, proposer_id, recipient_id, proposer_card_id, recipient_card_id),
            )
            return {"trade_id": cur.lastrowid, "proposer_card": dict(offered), "recipient_card": dict(requested)}

    def get_incoming_trades(self, guild_id: int, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT t.*, a.name AS offered_name, a.rarity AS offered_rarity, a.ovr AS offered_ovr,
                b.name AS requested_name, b.rarity AS requested_rarity, b.ovr AS requested_ovr
                FROM trades t
                JOIN card_instances a ON a.instance_id=t.proposer_card_id
                JOIN card_instances b ON b.instance_id=t.recipient_card_id
                WHERE t.guild_id=? AND t.recipient_id=? AND t.status='pending' AND t.expires_at > datetime('now')
                ORDER BY t.trade_id DESC LIMIT ?""", (guild_id, user_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def accept_trade(self, guild_id: int, trade_id: int, user_id: int) -> dict[str, Any]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            trade = db.execute(
                "SELECT * FROM trades WHERE guild_id=? AND trade_id=? AND status='pending'",
                (guild_id, trade_id),
            ).fetchone()
            if trade is None:
                raise ValueError("That trade is not pending.")
            if trade["recipient_id"] != user_id:
                raise ValueError("Only the member receiving this offer can accept it.")
            expired = db.execute("SELECT datetime(?) <= datetime('now')", (trade["expires_at"],)).fetchone()[0]
            if expired:
                db.execute("UPDATE trades SET status='expired',completed_at=CURRENT_TIMESTAMP WHERE trade_id=?", (trade_id,))
                raise ValueError("That trade has expired.")
            a = db.execute("SELECT * FROM card_instances WHERE guild_id=? AND instance_id=? AND owner_id=?",
                           (guild_id, trade["proposer_card_id"], trade["proposer_id"])).fetchone()
            b = db.execute("SELECT * FROM card_instances WHERE guild_id=? AND instance_id=? AND owner_id=?",
                           (guild_id, trade["recipient_card_id"], trade["recipient_id"])).fetchone()
            if a is None or b is None:
                db.execute("UPDATE trades SET status='cancelled',completed_at=CURRENT_TIMESTAMP WHERE trade_id=?", (trade_id,))
                raise ValueError("A card is no longer owned by the expected member; the trade was cancelled.")
            db.execute("UPDATE card_instances SET owner_id=? WHERE instance_id=?", (trade["recipient_id"], trade["proposer_card_id"]))
            db.execute("UPDATE card_instances SET owner_id=? WHERE instance_id=?", (trade["proposer_id"], trade["recipient_card_id"]))
            db.execute("UPDATE trades SET status='accepted',completed_at=CURRENT_TIMESTAMP WHERE trade_id=?", (trade_id,))
            return {"trade_id": trade_id, "proposer_id": trade["proposer_id"], "recipient_id": trade["recipient_id"],
                    "proposer_card": dict(a), "recipient_card": dict(b)}

    def close_trade(self, guild_id: int, trade_id: int, user_id: int, decline: bool = False) -> str:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            trade = db.execute("SELECT * FROM trades WHERE guild_id=? AND trade_id=? AND status='pending'",
                               (guild_id, trade_id)).fetchone()
            if trade is None:
                raise ValueError("That trade is not pending.")
            if user_id not in (trade["proposer_id"], trade["recipient_id"]):
                raise ValueError("Only a member involved in this trade can close it.")
            status = "declined" if decline and user_id == trade["recipient_id"] else "cancelled"
            db.execute("UPDATE trades SET status=?,completed_at=CURRENT_TIMESTAMP WHERE trade_id=?", (status, trade_id))
            return status

    def get_trade_history(self, guild_id: int, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT * FROM trades WHERE guild_id=? AND (proposer_id=? OR recipient_id=?)
                ORDER BY trade_id DESC LIMIT ?""", (guild_id, user_id, user_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]
