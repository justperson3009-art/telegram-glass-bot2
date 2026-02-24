"""
Модуль работы с базой данных SQLite
"""
import aiosqlite
import asyncio
from datetime import datetime
from typing import Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum


class GameMode(Enum):
    """Режимы игры"""
    TIME_WORDS = "time_words"      # Время + больше слов
    TIME_POINTS = "time_points"    # Время + больше очков
    POINTS_ONLY = "points_only"    # Без времени, до 1000 очков


class GameStatus(Enum):
    """Статусы игры"""
    SEARCHING = "searching"        # Поиск соперника
    ACTIVE = "active"              # Игра активна
    FINISHED = "finished"          # Игра завершена
    ABANDONED = "abandoned"        # Игрок вышел


@dataclass
class Player:
    """Игрок"""
    id: int
    telegram_id: int
    username: str
    first_name: str
    rating: int = 1000
    games_played: int = 0
    games_won: int = 0
    created_at: datetime = None


@dataclass
class Game:
    """Игра"""
    id: int
    player1_id: int
    player2_id: int
    mode: GameMode
    status: GameStatus
    board: str  # JSON строка
    current_turn: int  # чей ход (telegram_id)
    player1_tiles: str  # буквы игрока 1
    player2_tiles: str  # буквы игрока 2
    player1_score: int = 0
    player2_score: int = 0
    player1_words: int = 0
    player2_words: int = 0
    time_limit: int = 0  # секунд, 0 = безлимита
    time_remaining: int = 0
    created_at: datetime = None
    started_at: datetime = None
    finished_at: datetime = None
    winner_id: int = None


class Database:
    """Класс для работы с БД"""
    
    def __init__(self, db_path: str = "erudit.db"):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Подключение к БД"""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._init_tables()
        await self._init_words()
    
    async def close(self):
        """Закрытие подключения"""
        if self._connection:
            await self._connection.close()
    
    async def _init_tables(self):
        """Создание таблиц"""
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                rating INTEGER DEFAULT 1000,
                games_played INTEGER DEFAULT 0,
                games_won INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player1_id INTEGER NOT NULL,
                player2_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'searching',
                board TEXT,
                current_turn INTEGER,
                player1_tiles TEXT,
                player2_tiles TEXT,
                player1_score INTEGER DEFAULT 0,
                player2_score INTEGER DEFAULT 0,
                player1_words INTEGER DEFAULT 0,
                player2_words INTEGER DEFAULT 0,
                time_limit INTEGER DEFAULT 0,
                time_remaining INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                winner_id INTEGER,
                FOREIGN KEY (player1_id) REFERENCES players(id),
                FOREIGN KEY (player2_id) REFERENCES players(id)
            )
        """)
        
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT UNIQUE NOT NULL,
                length INTEGER NOT NULL
            )
        """)
        
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS game_moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                points INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games(id)
            )
        """)
        
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS search_queue (
                telegram_id INTEGER PRIMARY KEY,
                mode TEXT NOT NULL,
                time_limit INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self._connection.commit()
    
    async def _init_words(self):
        """Инициализация словаря (базовые слова)"""
        cursor = await self._connection.execute("SELECT COUNT(*) FROM words")
        result = await cursor.fetchone()
        
        if result[0] == 0:
            # Базовый набор слов для старта (нужно будет дополнить)
            base_words = [
                "дом", "лес", "кот", "ток", "рот", "нос", "сон", "лев", "бык", "мир",
                "вода", "земля", "огонь", "ветер", "небо", "луна", "солнце", "звезда",
                "дерево", "цветок", "трава", "камень", "река", "озеро", "море", "океан",
                "гора", "поле", "город", "село", "дорога", "мост", "окно", "дверь",
                "стол", "стул", "книга", "ручка", "бумага", "экран", "телефон",
                "компьютер", "интернет", "сайт", "программа", "данные", "файл",
                "время", "день", "ночь", "утро", "вечер", "неделя", "месяц", "год",
                "человек", "друг", "семья", "мама", "папа", "брат", "сестра",
                "работа", "учеба", "школа", "университет", "класс", "урок",
                "еда", "вода", "хлеб", "мясо", "рыба", "овощ", "фрукт", "ягода",
                "животное", "птица", "зверь", "кошка", "собака", "конь", "корова",
                "цвет", "красный", "синий", "зеленый", "желтый", "белый", "черный",
                "большой", "малый", "новый", "старый", "молодой", "умный", "сильный",
                "хороший", "плохой", "красивый", "быстрый", "медленный", "теплый",
                "играть", "работать", "учиться", "читать", "писать", "говорить",
                "думать", "знать", "понимать", "любить", "видеть", "слышать",
                "идти", "бежать", "ехать", "лететь", "плыть", "стоять", "сидеть",
                "делать", "создавать", "строить", "рисовать", "петь", "танцевать",
                "игра", "победа", "поражение", "очко", "счет", "уровень", "приз",
                "команда", "игрок", "соперник", "друг", "партнер", "лидер",
                "телеграм", "бот", "сообщение", "чат", "группа", "канал",
                "слово", "буква", "текст", "знак", "символ", "цифра", "число",
                "программа", "код", "алгоритм", "функция", "класс", "объект",
                "сервер", "клиент", "база", "данные", "запрос", "ответ",
                "сеть", "связь", "информация", "знание", "наука", "техника",
                "машина", "механизм", "инструмент", "прибор", "устройство",
                "система", "процесс", "результат", "эффект", "причина", "следствие",
                "проблема", "решение", "задача", "цель", "план", "проект",
                "идея", "мысль", "мнение", "взгляд", "позиция", "принцип",
                "правило", "закон", "порядок", "метод", "способ", "средство",
                "материал", "вещество", "элемент", "компонент", "часть", "целое",
                "форма", "содержание", "суть", "смысл", "значение", "ценность",
                "качество", "количество", "мера", "степень", "уровень", "стандарт",
                "образец", "пример", "модель", "тип", "вид", "род", "категория",
                "группа", "класс", "ряд", "цепь", "серия", "набор", "комплект",
                "состав", "структура", "организация", "управление", "контроль",
                "анализ", "синтез", "исследование", "эксперимент", "опыт", "тест",
                "проверка", "оценка", "измерение", "расчет", "вычисление",
                "формула", "уравнение", "выражение", "отношение", "пропорция",
                "функция", "график", "диаграмма", "схема", "карта", "план",
                "рисунок", "картина", "изображение", "фото", "видео", "звук",
                "музыка", "песня", "мелодия", "ритм", "такт", "нота", "аккорд",
                "искусство", "культура", "история", "философия", "религия",
                "политика", "экономика", "бизнес", "торговля", "рынок", "цена",
                "деньги", "валюта", "банк", "кредит", "долг", "налог", "бюджет",
                "доход", "расход", "прибыль", "убыток", "капитал", "актив",
                "ресурс", "запас", "фонд", "счет", "платеж", "перевод", "оплата",
                "покупка", "продажа", "заказ", "доставка", "услуга", "клиент",
                "поставщик", "производитель", "потребитель", "покупатель", "продавец"
            ]
            
            await self._connection.executemany(
                "INSERT OR IGNORE INTO words (word, length) VALUES (?, ?)",
                [(w, len(w)) for w in base_words]
            )
            await self._connection.commit()
    
    # === Игроки ===
    
    async def get_or_create_player(self, telegram_id: int, username: str, first_name: str) -> Player:
        """Получить или создать игрока"""
        cursor = await self._connection.execute(
            "SELECT * FROM players WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            # Обновить имя если изменилось
            await self._connection.execute(
                "UPDATE players SET username = ?, first_name = ? WHERE telegram_id = ?",
                (username, first_name, telegram_id)
            )
            await self._connection.commit()
            return self._row_to_player(row)
        
        # Создать нового
        cursor = await self._connection.execute(
            "INSERT INTO players (telegram_id, username, first_name) VALUES (?, ?, ?)",
            (telegram_id, username, first_name)
        )
        await self._connection.commit()
        
        cursor = await self._connection.execute(
            "SELECT * FROM players WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_player(row)
    
    async def get_player_by_id(self, player_id: int) -> Optional[Player]:
        """Получить игрока по ID"""
        cursor = await self._connection.execute(
            "SELECT * FROM players WHERE id = ?",
            (player_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_player(row) if row else None
    
    async def get_player_by_telegram_id(self, telegram_id: int) -> Optional[Player]:
        """Получить игрока по Telegram ID"""
        cursor = await self._connection.execute(
            "SELECT * FROM players WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_player(row) if row else None
    
    async def update_rating(self, player_id: int, delta: int):
        """Обновить рейтинг игрока"""
        await self._connection.execute(
            "UPDATE players SET rating = rating + ? WHERE id = ?",
            (delta, player_id)
        )
        await self._connection.commit()
    
    async def update_stats(self, player_id: int, won: bool):
        """Обновить статистику игр"""
        await self._connection.execute(
            "UPDATE players SET games_played = games_played + 1, games_won = games_won + ? WHERE id = ?",
            (1 if won else 0, player_id)
        )
        await self._connection.commit()
    
    async def get_leaderboard(self, limit: int = 10) -> List[Player]:
        """Получить топ игроков"""
        cursor = await self._connection.execute(
            "SELECT * FROM players ORDER BY rating DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [self._row_to_player(r) for r in rows]
    
    async def search_player_by_username(self, username: str) -> Optional[Player]:
        """Поиск игрока по username"""
        cursor = await self._connection.execute(
            "SELECT * FROM players WHERE username = ?",
            (username.lstrip('@'),)
        )
        row = await cursor.fetchone()
        return self._row_to_player(row) if row else None
    
    # === Очередь поиска ===
    
    async def add_to_queue(self, telegram_id: int, mode: GameMode, time_limit: int):
        """Добавить в очередь поиска"""
        await self._connection.execute(
            "INSERT OR REPLACE INTO search_queue (telegram_id, mode, time_limit) VALUES (?, ?, ?)",
            (telegram_id, mode.value, time_limit)
        )
        await self._connection.commit()
    
    async def remove_from_queue(self, telegram_id: int):
        """Удалить из очереди"""
        await self._connection.execute(
            "DELETE FROM search_queue WHERE telegram_id = ?",
            (telegram_id,)
        )
        await self._connection.commit()
    
    async def get_queue(self) -> List[dict]:
        """Получить всех в очереди"""
        cursor = await self._connection.execute(
            "SELECT * FROM search_queue ORDER BY created_at"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    
    async def find_match(self, telegram_id: int) -> Optional[dict]:
        """Найти соперника в очереди (не себя)"""
        cursor = await self._connection.execute(
            """SELECT sq.*, p.id as player_id, p.telegram_id as t_id, p.username, p.first_name 
               FROM search_queue sq
               JOIN players p ON p.telegram_id = sq.telegram_id
               WHERE sq.telegram_id != ? 
               ORDER BY sq.created_at LIMIT 1""",
            (telegram_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    
    # === Игры ===
    
    async def create_game(self, player1_id: int, player2_id: int, mode: GameMode, 
                          time_limit: int = 0) -> Game:
        """Создать новую игру"""
        cursor = await self._connection.execute(
            """INSERT INTO games (player1_id, player2_id, mode, status, time_limit) 
               VALUES (?, ?, ?, 'active', ?)""",
            (player1_id, player2_id, mode.value, time_limit)
        )
        await self._connection.commit()
        
        game_id = cursor.lastrowid
        return await self.get_game(game_id)
    
    async def get_game(self, game_id: int) -> Optional[Game]:
        """Получить игру по ID"""
        cursor = await self._connection.execute(
            "SELECT * FROM games WHERE id = ?",
            (game_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_game(row) if row else None
    
    async def get_active_game(self, telegram_id: int) -> Optional[Game]:
        """Получить активную игру игрока"""
        cursor = await self._connection.execute(
            """SELECT * FROM games 
               WHERE (player1_id = (SELECT id FROM players WHERE telegram_id = ?)
                   OR player2_id = (SELECT id FROM players WHERE telegram_id = ?))
               AND status = 'active'
               ORDER BY created_at DESC LIMIT 1""",
            (telegram_id, telegram_id)
        )
        row = await cursor.fetchone()
        return self._row_to_game(row) if row else None
    
    async def update_game(self, game: Game):
        """Обновить игру"""
        await self._connection.execute(
            """UPDATE games SET 
               board = ?, current_turn = ?, player1_tiles = ?, player2_tiles = ?,
               player1_score = ?, player2_score = ?, player1_words = ?, player2_words = ?,
               time_remaining = ?, status = ?, winner_id = ?, finished_at = ?
               WHERE id = ?""",
            (game.board, game.current_turn, game.player1_tiles, game.player2_tiles,
             game.player1_score, game.player2_score, game.player1_words, game.player2_words,
             game.time_remaining, game.status.value, game.winner_id, game.finished_at, game.id)
        )
        await self._connection.commit()
    
    async def add_move(self, game_id: int, player_id: int, word: str, points: int):
        """Добавить ход в историю"""
        await self._connection.execute(
            "INSERT INTO game_moves (game_id, player_id, word, points) VALUES (?, ?, ?, ?)",
            (game_id, player_id, word, points)
        )
        await self._connection.commit()
    
    async def get_game_moves(self, game_id: int) -> List[dict]:
        """Получить все ходы игры"""
        cursor = await self._connection.execute(
            "SELECT * FROM game_moves WHERE game_id = ? ORDER BY created_at",
            (game_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    
    # === Словарь ===
    
    async def check_word(self, word: str) -> bool:
        """Проверить существование слова"""
        cursor = await self._connection.execute(
            "SELECT 1 FROM words WHERE word = ?",
            (word.lower(),)
        )
        row = await cursor.fetchone()
        return row is not None
    
    async def add_word(self, word: str):
        """Добавить слово в словарь"""
        await self._connection.execute(
            "INSERT OR IGNORE INTO words (word, length) VALUES (?, ?)",
            (word.lower(), len(word))
        )
        await self._connection.commit()
    
    async def get_words_by_length(self, length: int, limit: int = 100) -> List[str]:
        """Получить слова определенной длины"""
        cursor = await self._connection.execute(
            "SELECT word FROM words WHERE length = ? ORDER BY RANDOM() LIMIT ?",
            (length, limit)
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]
    
    # === Утилиты ===
    
    def _row_to_player(self, row: aiosqlite.Row) -> Player:
        """Конвертировать строку в Player"""
        return Player(
            id=row["id"],
            telegram_id=row["telegram_id"],
            username=row["username"],
            first_name=row["first_name"],
            rating=row["rating"],
            games_played=row["games_played"],
            games_won=row["games_won"],
            created_at=row["created_at"]
        )
    
    def _row_to_game(self, row: aiosqlite.Row) -> Game:
        """Конвертировать строку в Game"""
        return Game(
            id=row["id"],
            player1_id=row["player1_id"],
            player2_id=row["player2_id"],
            mode=GameMode(row["mode"]),
            status=GameStatus(row["status"]),
            board=row["board"] or "[]",
            current_turn=row["current_turn"],
            player1_tiles=row["player1_tiles"] or "",
            player2_tiles=row["player2_tiles"] or "",
            player1_score=row["player1_score"] or 0,
            player2_score=row["player2_score"] or 0,
            player1_words=row["player1_words"] or 0,
            player2_words=row["player2_words"] or 0,
            time_limit=row["time_limit"] or 0,
            time_remaining=row["time_remaining"] or 0,
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            winner_id=row["winner_id"]
        )


# Глобальный экземпляр
db = Database()
