"""
Модуль работы с базой данных SQLite
Трекер настроения и привычек
"""
import aiosqlite
from datetime import datetime, date
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class MoodRecord:
    """Запись о настроении"""
    id: int
    user_id: int
    mood: int  # 1-10
    note: str
    created_at: datetime


@dataclass
class Habit:
    """Привычка"""
    id: int
    user_id: int
    name: str
    completed_today: bool


class Database:
    """Класс для работы с БД"""

    def __init__(self, db_path: str = "support_bot.db"):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Подключение к БД"""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._init_tables()

    async def close(self):
        """Закрытие подключения"""
        if self._connection:
            await self._connection.close()

    async def _init_tables(self):
        """Создание таблиц"""
        # Таблица настроений
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS moods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                mood INTEGER NOT NULL,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица привычек
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица выполненных привычек
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS habit_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                completed_date DATE NOT NULL,
                FOREIGN KEY (habit_id) REFERENCES habits(id)
            )
        """)

        # Таблица пользователей
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await self._connection.commit()

        # Добавим стандартные привычки для новых пользователей
        await self._init_default_habits()

    async def _init_default_habits(self):
        """Инициализация стандартных привычек"""
        cursor = await self._connection.execute("SELECT COUNT(*) FROM habits")
        result = await cursor.fetchone()
        
        # Если привычек нет, добавим стандартные для всех
        default_habits = [
            "💧 Выпить 8 стаканов воды",
            "😴 7-8 часов сна",
            "🚶 Прогулка на свежем воздухе",
            "📖 Чтение 15 минут",
            "🧘 Медитация или дыхательные упражнения"
        ]

    async def get_or_create_user(self, telegram_id: int, username: str, first_name: str) -> int:
        """Получить или создать пользователя"""
        cursor = await self._connection.execute(
            "SELECT id FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = await cursor.fetchone()

        if row:
            await self._connection.execute(
                "UPDATE users SET username = ?, first_name = ? WHERE telegram_id = ?",
                (username, first_name, telegram_id)
            )
            await self._connection.commit()
            return row[0]

        cursor = await self._connection.execute(
            "INSERT INTO users (telegram_id, username, first_name) VALUES (?, ?, ?)",
            (telegram_id, username, first_name)
        )
        await self._connection.commit()
        
        cursor = await self._connection.execute(
            "SELECT id FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def add_mood(self, user_id: int, mood: int, note: str = ""):
        """Добавить запись о настроении"""
        await self._connection.execute(
            "INSERT INTO moods (user_id, mood, note) VALUES (?, ?, ?)",
            (user_id, mood, note)
        )
        await self._connection.commit()

    async def get_moods_today(self, user_id: int) -> List[MoodRecord]:
        """Получить записи о настроении за сегодня"""
        today = date.today().isoformat()
        cursor = await self._connection.execute(
            """SELECT * FROM moods 
               WHERE user_id = ? AND DATE(created_at) = ?
               ORDER BY created_at DESC""",
            (user_id, today)
        )
        rows = await cursor.fetchall()
        return [self._row_to_mood(r) for r in rows]

    async def get_mood_stats(self, user_id: int, days: int = 7) -> Dict:
        """Получить статистику настроения за N дней"""
        cursor = await self._connection.execute(
            """SELECT AVG(mood) as avg_mood, MIN(mood) as min_mood, 
                      MAX(mood) as max_mood, COUNT(*) as count
               FROM moods
               WHERE user_id = ? 
               AND created_at >= datetime('now', ?)""",
            (user_id, f'-{days} days')
        )
        row = await cursor.fetchone()
        if row:
            return {
                'avg': round(row['avg_mood'], 1) if row['avg_mood'] else 0,
                'min': row['min_mood'] or 0,
                'max': row['max_mood'] or 0,
                'count': row['count'] or 0
            }
        return {'avg': 0, 'min': 0, 'max': 0, 'count': 0}

    async def add_habit(self, user_id: int, name: str) -> int:
        """Добавить привычку"""
        cursor = await self._connection.execute(
            "INSERT INTO habits (user_id, name) VALUES (?, ?)",
            (user_id, name)
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_habits(self, user_id: int) -> List[Habit]:
        """Получить все привычки пользователя"""
        today = date.today().isoformat()
        cursor = await self._connection.execute(
            """SELECT h.id, h.user_id, h.name,
                      CASE WHEN hc.id IS NOT NULL THEN 1 ELSE 0 END as completed_today
               FROM habits h
               LEFT JOIN habit_completions hc 
                 ON h.id = hc.habit_id AND hc.completed_date = ?
               WHERE h.user_id = ?""",
            (today, user_id)
        )
        rows = await cursor.fetchall()
        return [Habit(
            id=r['id'],
            user_id=r['user_id'],
            name=r['name'],
            completed_today=bool(r['completed_today'])
        ) for r in rows]

    async def complete_habit(self, habit_id: int, user_id: int):
        """Отметить привычку выполненной"""
        today = date.today().isoformat()
        await self._connection.execute(
            "INSERT OR IGNORE INTO habit_completions (habit_id, user_id, completed_date) VALUES (?, ?, ?)",
            (habit_id, user_id, today)
        )
        await self._connection.commit()

    async def uncomplete_habit(self, habit_id: int, user_id: int):
        """Убрать отметку о выполнении"""
        today = date.today().isoformat()
        await self._connection.execute(
            "DELETE FROM habit_completions WHERE habit_id = ? AND user_id = ? AND completed_date = ?",
            (habit_id, user_id, today)
        )
        await self._connection.commit()

    async def delete_habit(self, habit_id: int, user_id: int):
        """Удалить привычку"""
        await self._connection.execute(
            "DELETE FROM habits WHERE id = ? AND user_id = ?",
            (habit_id, user_id)
        )
        await self._connection.execute(
            "DELETE FROM habit_completions WHERE habit_id = ? AND user_id = ?",
            (habit_id, user_id)
        )
        await self._connection.commit()

    def _row_to_mood(self, row: aiosqlite.Row) -> MoodRecord:
        """Конвертировать строку в MoodRecord"""
        return MoodRecord(
            id=row['id'],
            user_id=row['user_id'],
            mood=row['mood'],
            note=row['note'] or '',
            created_at=row['created_at']
        )


db = Database()
