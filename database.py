import aiosqlite
import json
from datetime import datetime
from typing import Optional, List, Dict, Any


class Database:
    def __init__(self, db_path: str = "casino.db"):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    balance REAL DEFAULT 1.0,
                    total_deposited REAL DEFAULT 0,
                    total_withdrawn REAL DEFAULT 0,
                    total_games INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    total_bet REAL DEFAULT 0,
                    total_won REAL DEFAULT 0,
                    biggest_win REAL DEFAULT 0,
                    level INTEGER DEFAULT 0,
                    last_bonus TIMESTAMP,
                    referrer_id INTEGER,
                    referral_earnings REAL DEFAULT 0,
                    reg_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_banned INTEGER DEFAULT 0
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    game TEXT,
                    bet REAL,
                    win REAL,
                    won INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    type TEXT,
                    amount REAL,
                    address TEXT,
                    status TEXT DEFAULT 'pending',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS promo_codes (
                    code TEXT PRIMARY KEY,
                    amount REAL,
                    uses_left INTEGER,
                    used_by TEXT DEFAULT '[]'
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS mines_games (
                    user_id INTEGER PRIMARY KEY,
                    bet REAL,
                    board TEXT,
                    opened TEXT DEFAULT '[]',
                    mines_count INTEGER,
                    message_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS blackjack_games (
                    user_id INTEGER PRIMARY KEY,
                    bet REAL,
                    state TEXT
                )
            """)
            # Insert default promo codes
            await db.execute("""
                INSERT OR IGNORE INTO promo_codes (code, amount, uses_left)
                VALUES ('LUCKY25', 25.0, 1000), ('BONUS50', 50.0, 500), ('VIP100', 100.0, 100)
            """)
            await db.commit()

    async def register_user(self, user_id: int, username: str, full_name: str, referrer_id: int = None) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            existing = await cursor.fetchone()
            if existing:
                return False
            await db.execute(
                "INSERT INTO users (user_id, username, full_name, referrer_id) VALUES (?, ?, ?, ?)",
                (user_id, username, full_name, referrer_id)
            )
            await db.commit()

            if referrer_id:
                ref_bonus = 5.0
                await db.execute("UPDATE users SET balance = balance + ?, referral_earnings = referral_earnings + ? WHERE user_id = ?",
                                 (ref_bonus, ref_bonus, referrer_id))
                await db.commit()
            return True

    async def get_balance(self, user_id: int) -> float:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return row[0] if row else 0.0

    async def add_balance(self, user_id: int, amount: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()

    async def deduct_balance(self, user_id: int, amount: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
            await db.commit()

    async def record_game(self, user_id: int, game: str, bet: float, win: float, won: bool):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO games (user_id, game, bet, win, won) VALUES (?, ?, ?, ?, ?)",
                (user_id, game, bet, win, 1 if won else 0)
            )
            await db.execute("""
                UPDATE users SET
                    total_games = total_games + 1,
                    wins = wins + ?,
                    total_bet = total_bet + ?,
                    total_won = total_won + ?,
                    biggest_win = MAX(biggest_win, ?),
                    level = MIN(4, total_games / 50)
                WHERE user_id = ?
            """, (1 if won else 0, bet, win, win, user_id))
            await db.commit()

    async def get_user_stats(self, user_id: int) -> Dict:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if not row:
                return {}
            cols = [d[0] for d in cursor.description]
            return dict(zip(cols, row))

    async def get_last_bonus(self, user_id: int) -> Optional[datetime]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
            return None

    async def set_last_bonus(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?",
                             (datetime.now().isoformat(), user_id))
            await db.commit()

    async def record_deposit(self, user_id: int, amount: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO transactions (user_id, type, amount, status) VALUES (?, 'deposit', ?, 'completed')",
                (user_id, amount)
            )
            await db.execute("UPDATE users SET total_deposited = total_deposited + ? WHERE user_id = ?",
                             (amount, user_id))
            await db.commit()

    async def record_withdrawal(self, user_id: int, amount: float, address: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO transactions (user_id, type, amount, address, status) VALUES (?, 'withdraw', ?, ?, 'processing')",
                (user_id, amount, address)
            )
            await db.execute("UPDATE users SET total_withdrawn = total_withdrawn + ? WHERE user_id = ?",
                             (amount, user_id))
            await db.commit()

    async def use_promo(self, user_id: int, code: str) -> Dict:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM promo_codes WHERE code = ?", (code,))
            promo = await cursor.fetchone()

            if not promo:
                return {"success": False, "error": "Промокод не найден!"}

            _, amount, uses_left, used_by_str = promo
            used_by = json.loads(used_by_str)

            if user_id in used_by:
                return {"success": False, "error": "Вы уже использовали этот промокод!"}

            if uses_left <= 0:
                return {"success": False, "error": "Промокод исчерпан!"}

            used_by.append(user_id)
            await db.execute(
                "UPDATE promo_codes SET uses_left = uses_left - 1, used_by = ? WHERE code = ?",
                (json.dumps(used_by), code)
            )
            await db.commit()
            return {"success": True, "amount": amount}

    async def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT username, total_won FROM users ORDER BY total_won DESC LIMIT ?", (limit,)
            )
            rows = await cursor.fetchall()
            return [{"username": r[0] or "Анонимный игрок", "total_won": r[1]} for r in rows]

    async def get_game_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT game, bet, win, won, timestamp FROM games WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit)
            )
            rows = await cursor.fetchall()
            return [{"game": r[0], "bet": r[1], "win": r[2], "won": bool(r[3]), "ts": r[4]} for r in rows]

    async def get_referral_count(self, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_referral_earnings(self, user_id: int) -> float:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT referral_earnings FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return row[0] if row else 0.0

    async def save_mines_game(self, user_id: int, bet: float, board: list, mines_count: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO mines_games (user_id, bet, board, opened, mines_count) VALUES (?, ?, ?, '[]', ?)",
                (user_id, bet, json.dumps(board), mines_count)
            )
            await db.commit()

    async def get_mines_game(self, user_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT bet, board, opened, mines_count FROM mines_games WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return {"bet": row[0], "board": json.loads(row[1]), "opened": json.loads(row[2]), "mines_count": row[3]}

    async def update_mines_opened(self, user_id: int, opened: list):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE mines_games SET opened = ? WHERE user_id = ?", (json.dumps(opened), user_id))
            await db.commit()

    async def update_mines_message(self, user_id: int, message_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE mines_games SET message_id = ? WHERE user_id = ?", (message_id, user_id))
            await db.commit()

    async def delete_mines_game(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM mines_games WHERE user_id = ?", (user_id,))
            await db.commit()

    async def save_blackjack_game(self, user_id: int, bet: float, state: dict):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO blackjack_games (user_id, bet, state) VALUES (?, ?, ?)",
                (user_id, bet, json.dumps(state))
            )
            await db.commit()

    async def get_blackjack_game(self, user_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT bet, state FROM blackjack_games WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return {"bet": row[0], "state": json.loads(row[1])}

    async def delete_blackjack_game(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM blackjack_games WHERE user_id = ?", (user_id,))
            await db.commit()

    async def get_global_stats(self) -> Dict:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*), SUM(total_games), SUM(total_bet), SUM(total_won) FROM users")
            row = await cursor.fetchone()
            total_users, total_games, total_bet, total_won = row
            return {
                "total_users": total_users or 0,
                "total_games": total_games or 0,
                "total_turnover": total_bet or 0,
                "total_paid": total_won or 0,
                "casino_profit": (total_bet or 0) - (total_won or 0)
            }

    async def get_all_users(self) -> List[int]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM users WHERE is_banned = 0")
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


db = Database()
