1 """
       2 Модуль работы с базой данных SQLite
       3 """
       4 import aiosqlite
       5 import asyncio
       6 from datetime import datetime
       7 from typing import Optional, List, Tuple
       8 from dataclasses import dataclass
       9 from enum import Enum
      10
      11
      12 class GameMode(Enum):
      13     """Режимы игры"""
      14     TIME_WORDS = "time_words"      # Время + больше слов
      15     TIME_POINTS = "time_points"    # Время + больше очков
      16     POINTS_ONLY = "points_only"    # Без времени, до 1000 очков
      17     PLAYER_VS_BOT = "player_vs_bot"  # Игра с ботом
      18
      19
      20 class GameStatus(Enum):
      21     """Статусы игры"""
      22     SEARCHING = "searching"        # Поиск соперника
      23     ACTIVE = "active"              # Игра активна
      24     FINISHED = "finished"          # Игра завершена
      25     ABANDONED = "abandoned"        # Игрок вышел
      26
      27
      28 @dataclass
      29 class Player:
      30     """Игрок"""
      31     id: int
      32     telegram_id: int
      33     username: str
      34     first_name: str
      35     rating: int = 1000
      36     games_played: int = 0
      37     games_won: int = 0
      38     created_at: datetime = None
      39
      40
      41 @dataclass
      42 class Game:
      43     """Игра"""
      44     id: int
      45     player1_id: int
      46     player2_id: int
      47     mode: GameMode
      48     status: GameStatus
      49     board: str  # JSON строка
      50     current_turn: int  # чей ход (telegram_id)
      51     player1_tiles: str  # буквы игрока 1
      52     player2_tiles: str  # буквы игрока 2
      53     player1_score: int = 0
      54     player2_score: int = 0
      55     player1_words: int = 0
      56     player2_words: int = 0
      57     time_limit: int = 0  # секунд, 0 = безлимита
      58     time_remaining: int = 0
      59     created_at: datetime = None
      60     started_at: datetime = None
      61     finished_at: datetime = None
      62     winner_id: int = None
      63
      64
      65 class Database:
      66     """Класс для работы с БД"""
      67
      68     def __init__(self, db_path: str = "erudit.db"):
      69         self.db_path = db_path
      70         self._connection: Optional[aiosqlite.Connection] = None
      71
      72     async def connect(self):
      73         """Подключение к БД"""
      74         self._connection = await aiosqlite.connect(self.db_path)
      75         self._connection.row_factory = aiosqlite.Row
      76         await self._init_tables()
      77         await self._init_words()
      78
      79     async def close(self):
      80         """Закрытие подключения"""
      81         if self._connection:
      82             await self._connection.close()
      83
      84     async def _init_tables(self):
      85         """Создание таблиц"""
      86         await self._connection.execute("""
      87             CREATE TABLE IF NOT EXISTS players (
      88                 id INTEGER PRIMARY KEY AUTOINCREMENT,
      89                 telegram_id INTEGER UNIQUE NOT NULL,
      90                 username TEXT,
      91                 first_name TEXT,
      92                 rating INTEGER DEFAULT 1000,
      93                 games_played INTEGER DEFAULT 0,
      94                 games_won INTEGER DEFAULT 0,
      95                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      96             )
      97         """)
      98
      99         await self._connection.execute("""
     100             CREATE TABLE IF NOT EXISTS games (
     101                 id INTEGER PRIMARY KEY AUTOINCREMENT,
     102                 player1_id INTEGER NOT NULL,
     103                 player2_id INTEGER NOT NULL,
     104                 mode TEXT NOT NULL,
     105                 status TEXT NOT NULL DEFAULT 'searching',
     106                 board TEXT,
     107                 current_turn INTEGER,
     108                 player1_tiles TEXT,
     109                 player2_tiles TEXT,
     110                 player1_score INTEGER DEFAULT 0,
     111                 player2_score INTEGER DEFAULT 0,
     112                 player1_words INTEGER DEFAULT 0,
     113                 player2_words INTEGER DEFAULT 0,
     114                 time_limit INTEGER DEFAULT 0,
     115                 time_remaining INTEGER DEFAULT 0,
     116                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
     117                 started_at TIMESTAMP,
     118                 finished_at TIMESTAMP,
     119                 winner_id INTEGER,
     120                 FOREIGN KEY (player1_id) REFERENCES players(id),
     121                 FOREIGN KEY (player2_id) REFERENCES players(id)
     122             )
     123         """)
     124
     125         await self._connection.execute("""
     126             CREATE TABLE IF NOT EXISTS words (
     127                 id INTEGER PRIMARY KEY AUTOINCREMENT,
     128                 word TEXT UNIQUE NOT NULL,
     129                 length INTEGER NOT NULL
     130             )
     131         """)
     132
     133         await self._connection.execute("""
     134             CREATE TABLE IF NOT EXISTS game_moves (
     135                 id INTEGER PRIMARY KEY AUTOINCREMENT,
     136                 game_id INTEGER NOT NULL,
     137                 player_id INTEGER NOT NULL,
     138                 word TEXT NOT NULL,
     139                 points INTEGER NOT NULL,
     140                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
     141                 FOREIGN KEY (game_id) REFERENCES games(id)
     142             )
     143         """)
     144
     145         await self._connection.execute("""
     146             CREATE TABLE IF NOT EXISTS search_queue (
     147                 telegram_id INTEGER PRIMARY KEY,
     148                 mode TEXT NOT NULL,
     149                 time_limit INTEGER NOT NULL,
     150                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
     151             )
     152         """)
     153
     154         await self._connection.commit()
     155
     156     async def _init_words(self):
     157         """Инициализация словаря (базовые слова)"""
     158         cursor = await self._connection.execute("SELECT COUNT(*) FROM words")
     159         result = await cursor.fetchone()
     160
     161         if result[0] == 0:
     162             base_words = [
     163                 "дом", "лес", "кот", "ток", "рот", "нос", "сон", "лев", "бык", "мир",
     164                 "вода", "земля", "огонь", "ветер", "небо", "луна", "солнце", "звезда",
     165                 "дерево", "цветок", "трава", "камень", "река", "озеро", "море", "океан",
     166                 "гора", "поле", "город", "село", "дорога", "мост", "окно", "дверь",
     167                 "стол", "стул", "книга", "ручка", "бумага", "экран", "телефон",
     168                 "компьютер", "интернет", "сайт", "программа", "данные", "файл",
     169                 "время", "день", "ночь", "утро", "вечер", "неделя", "месяц", "год",
     170                 "человек", "друг", "семья", "мама", "папа", "брат", "сестра",
     171                 "работа", "учеба", "школа", "университет", "класс", "урок",
     172                 "еда", "вода", "хлеб", "мясо", "рыба", "овощ", "фрукт", "ягода",
     173                 "животное", "птица", "зверь", "кошка", "собака", "конь", "корова",
     174                 "цвет", "красный", "синий", "зеленый", "желтый", "белый", "черный",
     175                 "большой", "малый", "новый", "старый", "молодой", "умный", "сильный",
     176                 "хороший", "плохой", "красивый", "быстрый", "медленный", "теплый",
     177                 "играть", "работать", "учиться", "читать", "писать", "говорить",
     178                 "думать", "знать", "понимать", "любить", "видеть", "слышать",
     179                 "идти", "бежать", "ехать", "лететь", "плыть", "стоять", "сидеть",
     180                 "делать", "создавать", "строить", "рисовать", "петь", "танцевать",
     181                 "игра", "победа", "поражение", "очко", "счет", "уровень", "приз",
     182                 "команда", "игрок", "соперник", "друг", "партнер", "лидер",
     183                 "телеграм", "бот", "сообщение", "чат", "группа", "канал",
     184                 "слово", "буква", "текст", "знак", "символ", "цифра", "число",
     185                 "программа", "код", "алгоритм", "функция", "класс", "объект",
     186                 "сервер", "клиент", "база", "данные", "запрос", "ответ",
     187                 "сеть", "связь", "информация", "знание", "наука", "техника",
     188                 "машина", "механизм", "инструмент", "прибор", "устройство",
     189                 "система", "процесс", "результат", "эффект", "причина", "следствие",
     190                 "проблема", "решение", "задача", "цель", "план", "проект",
     191                 "идея", "мысль", "мнение", "взгляд", "позиция", "принцип",
     192                 "правило", "закон", "порядок", "метод", "способ", "средство",
     193                 "материал", "вещество", "элемент", "компонент", "часть", "целое",
     194                 "форма", "содержание", "суть", "смысл", "значение", "ценность",
     195                 "качество", "количество", "мера", "степень", "уровень", "стандарт",
     196                 "образец", "пример", "модель", "тип", "вид", "род", "категория",
     197                 "группа", "класс", "ряд", "цепь", "серия", "набор", "комплект",
     198                 "состав", "структура", "организация", "управление", "контроль",
     199                 "анализ", "синтез", "исследование", "эксперимент", "опыт", "тест",
     200                 "проверка", "оценка", "измерение", "расчет", "вычисление",
     201                 "формула", "уравнение", "выражение", "отношение", "пропорция",
     202                 "функция", "график", "диаграмма", "схема", "карта", "план",
     203                 "рисунок", "картина", "изображение", "фото", "видео", "звук",
     204                 "музыка", "песня", "мелодия", "ритм", "такт", "нота", "аккорд",
     205                 "искусство", "культура", "история", "философия", "религия",
     206                 "политика", "экономика", "бизнес", "торговля", "рынок", "цена",
     207                 "деньги", "валюта", "банк", "кредит", "долг", "налог", "бюджет",
     208                 "доход", "расход", "прибыль", "убыток", "капитал", "актив",
     209                 "ресурс", "запас", "фонд", "счет", "платеж", "перевод", "оплата",
     210                 "покупка", "продажа", "заказ", "доставка", "услуга", "клиент",
     211                 "поставщик", "производитель", "потребитель", "покупатель", "продавец"
     212             ]
     213
     214             await self._connection.executemany(
     215                 "INSERT OR IGNORE INTO words (word, length) VALUES (?, ?)",
     216                 [(w, len(w)) for w in base_words]
     217             )
     218             await self._connection.commit()
     219
     220     async def get_or_create_player(self, telegram_id: int, username: str, first_name: str) -> Player:
     221         """Получить или создать игрока"""
     222         cursor = await self._connection.execute(
     223             "SELECT * FROM players WHERE telegram_id = ?",
     224             (telegram_id,)
     225         )
     226         row = await cursor.fetchone()
     227
     228         if row:
     229             await self._connection.execute(
     230                 "UPDATE players SET username = ?, first_name = ? WHERE telegram_id = ?",
     231                 (username, first_name, telegram_id)
     232             )
     233             await self._connection.commit()
     234             return self._row_to_player(row)
     235
     236         cursor = await self._connection.execute(
     237             "INSERT INTO players (telegram_id, username, first_name) VALUES (?, ?, ?)",
     238             (telegram_id, username, first_name)
     239         )
     240         await self._connection.commit()
     241
     242         cursor = await self._connection.execute(
     243             "SELECT * FROM players WHERE telegram_id = ?",
     244             (telegram_id,)
     245         )
     246         row = await cursor.fetchone()
     247         return self._row_to_player(row)
     248
     249     async def get_player_by_id(self, player_id: int) -> Optional[Player]:
     250         """Получить игрока по ID"""
     251         cursor = await self._connection.execute(
     252             "SELECT * FROM players WHERE id = ?",
     253             (player_id,)
     254         )
     255         row = await cursor.fetchone()
     256         return self._row_to_player(row) if row else None
     257
     258     async def get_player_by_telegram_id(self, telegram_id: int) -> Optional[Player]:
     259         """Получить игрока по Telegram ID"""
     260         cursor = await self._connection.execute(
     261             "SELECT * FROM players WHERE telegram_id = ?",
     262             (telegram_id,)
     263         )
     264         row = await cursor.fetchone()
     265         return self._row_to_player(row) if row else None
     266
     267     async def update_rating(self, player_id: int, delta: int):
     268         """Обновить рейтинг игрока"""
     269         await self._connection.execute(
     270             "UPDATE players SET rating = rating + ? WHERE id = ?",
     271             (delta, player_id)
     272         )
     273         await self._connection.commit()
     274
     275     async def update_stats(self, player_id: int, won: bool):
     276         """Обновить статистику игр"""
     277         await self._connection.execute(
     278             "UPDATE players SET games_played = games_played + 1, games_won = games_won + ? WHERE id = ?",
     279             (1 if won else 0, player_id)
     280         )
     281         await self._connection.commit()
     282
     283     async def get_leaderboard(self, limit: int = 10) -> List[Player]:
     284         """Получить топ игроков"""
     285         cursor = await self._connection.execute(
     286             "SELECT * FROM players ORDER BY rating DESC LIMIT ?",
     287             (limit,)
     288         )
     289         rows = await cursor.fetchall()
     290         return [self._row_to_player(r) for r in rows]
     291
     292     async def search_player_by_username(self, username: str) -> Optional[Player]:
     293         """Поиск игрока по username"""
     294         cursor = await self._connection.execute(
     295             "SELECT * FROM players WHERE username = ?",
     296             (username.lstrip('@'),)
     297         )
     298         row = await cursor.fetchone()
     299         return self._row_to_player(row) if row else None
     300
     301     async def add_to_queue(self, telegram_id: int, mode: GameMode, time_limit: int):
     302         """Добавить в очередь поиска"""
     303         await self._connection.execute(
     304             "INSERT OR REPLACE INTO search_queue (telegram_id, mode, time_limit) VALUES (?, ?, ?)",
     305             (telegram_id, mode.value, time_limit)
     306         )
     307         await self._connection.commit()
     308
     309     async def remove_from_queue(self, telegram_id: int):
     310         """Удалить из очереди"""
     311         await self._connection.execute(
     312             "DELETE FROM search_queue WHERE telegram_id = ?",
     313             (telegram_id,)
     314         )
     315         await self._connection.commit()
     316
     317     async def get_queue(self) -> List[dict]:
     318         """Получить всех в очереди"""
     319         cursor = await self._connection.execute(
     320             "SELECT * FROM search_queue ORDER BY created_at"
     321         )
     322         rows = await cursor.fetchall()
     323         return [dict(r) for r in rows]
     324
     325     async def find_match(self, telegram_id: int) -> Optional[dict]:
     326         """Найти соперника в очереди (не себя)"""
     327         cursor = await self._connection.execute(
     328             """SELECT sq.*, p.id as player_id, p.telegram_id as t_id, p.username, p.first_name
     329                FROM search_queue sq
     330                JOIN players p ON p.telegram_id = sq.telegram_id
     331                WHERE sq.telegram_id != ?
     332                ORDER BY sq.created_at LIMIT 1""",
     333             (telegram_id,)
     334         )
     335         row = await cursor.fetchone()
     336         return dict(row) if row else None
     337
     338     async def create_game(self, player1_id: int, player2_id: int, mode: GameMode,
     339                           time_limit: int = 0) -> Game:
     340         """Создать новую игру"""
     341         cursor = await self._connection.execute(
     342             """INSERT INTO games (player1_id, player2_id, mode, status, time_limit)
     343                VALUES (?, ?, ?, 'active', ?)""",
     344             (player1_id, player2_id, mode.value, time_limit)
     345         )
     346         await self._connection.commit()
     347
     348         game_id = cursor.lastrowid
     349         return await self.get_game(game_id)
     350
     351     async def get_game(self, game_id: int) -> Optional[Game]:
     352         """Получить игру по ID"""
     353         cursor = await self._connection.execute(
     354             "SELECT * FROM games WHERE id = ?",
     355             (game_id,)
     356         )
     357         row = await cursor.fetchone()
     358         return self._row_to_game(row) if row else None
     359
     360     async def get_active_game(self, telegram_id: int) -> Optional[Game]:
     361         """Получить активную игру игрока"""
     362         cursor = await self._connection.execute(
     363             """SELECT * FROM games
     364                WHERE (player1_id = (SELECT id FROM players WHERE telegram_id = ?)
     365                    OR player2_id = (SELECT id FROM players WHERE telegram_id = ?))
     366                AND status = 'active'
     367                ORDER BY created_at DESC LIMIT 1""",
     368             (telegram_id, telegram_id)
     369         )
     370         row = await cursor.fetchone()
     371         return self._row_to_game(row) if row else None
     372
     373     async def update_game(self, game: Game):
     374         """Обновить игру"""
     375         await self._connection.execute(
     376             """UPDATE games SET
     377                board = ?, current_turn = ?, player1_tiles = ?, player2_tiles = ?,
     378                player1_score = ?, player2_score = ?, player1_words = ?, player2_words = ?,
     379                time_remaining = ?, status = ?, winner_id = ?, finished_at = ?
     380                WHERE id = ?""",
     381             (game.board, game.current_turn, game.player1_tiles, game.player2_tiles,
     382              game.player1_score, game.player2_score, game.player1_words, game.player2_words,
     383              game.time_remaining, game.status.value, game.winner_id, game.finished_at, game.id)
     384         )
     385         await self._connection.commit()
     386
     387     async def add_move(self, game_id: int, player_id: int, word: str, points: int):
     388         """Добавить ход в историю"""
     389         await self._connection.execute(
     390             "INSERT INTO game_moves (game_id, player_id, word, points) VALUES (?, ?, ?, ?)",
     391             (game_id, player_id, word, points)
     392         )
     393         await self._connection.commit()
     394
     395     async def get_game_moves(self, game_id: int) -> List[dict]:
     396         """Получить все ходы игры"""
     397         cursor = await self._connection.execute(
     398             "SELECT * FROM game_moves WHERE game_id = ? ORDER BY created_at",
     399             (game_id,)
     400         )
     401         rows = await cursor.fetchall()
     402         return [dict(r) for r in rows]
     403
     404     async def check_word(self, word: str) -> bool:
     405         """Проверить существование слова"""
     406         cursor = await self._connection.execute(
     407             "SELECT 1 FROM words WHERE word = ?",
     408             (word.lower(),)
     409         )
     410         row = await cursor.fetchone()
     411         return row is not None
     412
     413     async def add_word(self, word: str):
     414         """Добавить слово в словарь"""
     415         await self._connection.execute(
     416             "INSERT OR IGNORE INTO words (word, length) VALUES (?, ?)",
     417             (word.lower(), len(word))
     418         )
     419         await self._connection.commit()
     420
     421     async def get_words_by_length(self, length: int, limit: int = 100) -> List[str]:
     422         """Получить слова определенной длины"""
     423         cursor = await self._connection.execute(
     424             "SELECT word FROM words WHERE length = ? ORDER BY RANDOM() LIMIT ?",
     425             (length, limit)
     426         )
     427         rows = await cursor.fetchall()
     428         return [r[0] for r in rows]
     429
     430     def _row_to_player(self, row: aiosqlite.Row) -> Player:
     431         """Конвертировать строку в Player"""
     432         return Player(
     433             id=row["id"],
     434             telegram_id=row["telegram_id"],
     435             username=row["username"],
     436             first_name=row["first_name"],
     437             rating=row["rating"],
     438             games_played=row["games_played"],
     439             games_won=row["games_won"],
     440             created_at=row["created_at"]
     441         )
     442
     443     def _row_to_game(self, row: aiosqlite.Row) -> Game:
     444         """Конвертировать строку в Game"""
     445         return Game(
     446             id=row["id"],
     447             player1_id=row["player1_id"],
     448             player2_id=row["player2_id"],
     449             mode=GameMode(row["mode"]),
     450             status=GameStatus(row["status"]),
     451             board=row["board"] or "[]",
     452             current_turn=row["current_turn"],
     453             player1_tiles=row["player1_tiles"] or "",
     454             player2_tiles=row["player2_tiles"] or "",
     455             player1_score=row["player1_score"] or 0,
     456             player2_score=row["player2_score"] or 0,
     457             player1_words=row["player1_words"] or 0,
     458             player2_words=row["player2_words"] or 0,
     459             time_limit=row["time_limit"] or 0,
     460             time_remaining=row["time_remaining"] or 0,
     461             created_at=row["created_at"],
     462             started_at=row["started_at"],
     463             finished_at=row["finished_at"],
     464             winner_id=row["winner_id"]
     465         )
     466
     467
     468 db = Database()
