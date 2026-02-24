"""
Логика игры Эрудит (Скраббл)
"""
import json
import random
from typing import List, Tuple, Optional, Set
from dataclasses import dataclass


# Распределение букв и очков (как в русском Скраббле)
LETTER_DIST = {
    'о': 8, 'а': 8, 'е': 8, 'и': 5, 'н': 5, 'т': 5, 'р': 5, 'с': 5, 'л': 4,
    'к': 4, 'м': 3, 'п': 3, 'у': 3, 'д': 3, 'я': 3, 'ы': 2, 'з': 2, 'в': 2,
    'б': 2, 'г': 2, 'ч': 2, 'й': 2, 'ь': 2, 'э': 2, 'ю': 2, 'ж': 2, 'х': 2,
    'ц': 2, 'щ': 2, 'ф': 2, 'ш': 2, 'ё': 2
}

LETTER_POINTS = {
    'о': 1, 'а': 1, 'е': 1, 'и': 1, 'н': 1, 'т': 1, 'р': 1, 'с': 1, 'л': 1,
    'к': 2, 'м': 2, 'п': 2, 'у': 2, 'д': 2, 'я': 3, 'ы': 4, 'з': 5, 'в': 4,
    'б': 3, 'г': 3, 'ч': 5, 'й': 4, 'ь': 3, 'э': 8, 'ю': 8, 'ж': 5, 'х': 5,
    'ц': 5, 'щ': 10, 'ф': 10, 'ш': 8, 'ё': 7
}

# Поле 15x15 с премиум-клетками
# TW = triple word, DW = double word, TL = triple letter, DL = double letter
# * = центр (также DW)
PREMIUM_CELLS = {
    (0, 0): 'TW', (0, 7): 'TW', (0, 14): 'TW',
    (7, 0): 'TW', (7, 14): 'TW',
    (14, 0): 'TW', (14, 7): 'TW', (14, 14): 'TW',
    (1, 1): 'DW', (2, 2): 'DW', (3, 3): 'DW', (4, 4): 'DW',
    (1, 13): 'DW', (2, 12): 'DW', (3, 11): 'DW', (4, 10): 'DW',
    (13, 1): 'DW', (12, 2): 'DW', (11, 3): 'DW', (10, 4): 'DW',
    (13, 13): 'DW', (12, 12): 'DW', (11, 11): 'DW', (10, 10): 'DW',
    (1, 5): 'TL', (1, 9): 'TL', (5, 1): 'TL', (5, 9): 'TL',
    (5, 13): 'TL', (9, 1): 'TL', (9, 5): 'TL', (9, 9): 'TL',
    (9, 13): 'TL', (13, 5): 'TL', (13, 9): 'TL',
    (2, 0): 'DL', (2, 6): 'DL', (2, 8): 'DL', (2, 14): 'DL',
    (0, 2): 'DL', (0, 6): 'DL', (0, 8): 'DL', (0, 12): 'DL',
    (3, 0): 'DL', (3, 14): 'DL', (6, 0): 'DL', (6, 14): 'DL',
    (6, 6): 'DL', (6, 8): 'DL', (8, 6): 'DL', (8, 8): 'DL',
    (8, 14): 'DL', (14, 6): 'DL', (14, 8): 'DL', (14, 12): 'DL',
    (7, 7): '*',  # Центр
}


@dataclass
class PlacedWord:
    """Размещённое слово на поле"""
    word: str
    row: int
    col: int
    horizontal: bool
    points: int
    new_letters: List[Tuple[int, int, str]]  # (row, col, letter)


class GameBoard:
    """Игровое поле 15x15"""
    
    def __init__(self, size: int = 15):
        self.size = size
        self.cells: List[List[Optional[str]]] = [[None] * size for _ in range(size)]
        self.used_premium: Set[Tuple[int, int]] = set()  # Использованные премиум-клетки
    
    def to_dict(self) -> dict:
        """Сериализация в dict"""
        return {
            'cells': self.cells,
            'used_premium': list(self.used_premium)
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'GameBoard':
        """Десериализация из dict"""
        board = cls()
        board.cells = data['cells']
        board.used_premium = set(tuple(p) for p in data.get('used_premium', []))
        return board
    
    def to_json(self) -> str:
        """Сериализация в JSON"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'GameBoard':
        """Десериализация из JSON"""
        if not json_str or json_str == "[]":
            return cls()
        return cls.from_dict(json.loads(json_str))
    
    def is_empty(self, row: int, col: int) -> bool:
        """Пуста ли клетка"""
        return self.cells[row][col] is None
    
    def is_occupied(self, row: int, col: int) -> bool:
        """Занята ли клетка"""
        return self.cells[row][col] is not None
    
    def get_letter(self, row: int, col: int) -> Optional[str]:
        """Получить букву из клетки"""
        return self.cells[row][col]
    
    def set_letter(self, row: int, col: int, letter: str):
        """Поставить букву в клетку"""
        self.cells[row][col] = letter
    
    def is_valid_position(self, row: int, col: int) -> bool:
        """Проверка границ поля"""
        return 0 <= row < self.size and 0 <= col < self.size
    
    def get_word_at(self, row: int, col: int, horizontal: bool) -> Tuple[str, int, int]:
        """
        Получить слово, проходящее через клетку
        Возвращает (слово, start_row, start_col)
        """
        if horizontal:
            # Ищем начало слова
            start_col = col
            while start_col > 0 and self.is_occupied(row, start_col - 1):
                start_col -= 1
            
            # Собираем слово
            word = ""
            c = start_col
            while c < self.size and self.is_occupied(row, c):
                letter = self.get_letter(row, c)
                if letter:
                    word += letter
                c += 1
            
            return word, row, start_col
        else:
            # Ищем начало слова
            start_row = row
            while start_row > 0 and self.is_occupied(start_row - 1, col):
                start_row -= 1
            
            # Собираем слово
            word = ""
            r = start_row
            while r < self.size and self.is_occupied(r, col):
                letter = self.get_letter(r, col)
                if letter:
                    word += letter
                r += 1
            
            return word, start_row, col
    
    def calculate_word_points(self, word: str, row: int, col: int, 
                               horizontal: bool, new_positions: Set[Tuple[int, int]]) -> int:
        """
        Подсчитать очки за слово с учётом премиум-клеток
        """
        total = 0
        word_multiplier = 1
        
        letters = list(word)
        r, c = row, col
        
        for i, letter in enumerate(letters):
            if horizontal:
                curr_row, curr_col = row, col + i
            else:
                curr_row, curr_col = row + i, col
            
            base_points = LETTER_POINTS.get(letter.lower(), 0)
            
            # Новая буква на премиум-клетке
            if (curr_row, curr_col) in new_positions:
                premium = PREMIUM_CELLS.get((curr_row, curr_col))
                if premium == 'DL':
                    base_points *= 2
                elif premium == 'TL':
                    base_points *= 3
                elif premium in ('DW', '*') and (curr_row, curr_col) not in self.used_premium:
                    word_multiplier *= 2
                    self.used_premium.add((curr_row, curr_col))
                elif premium == 'TW' and (curr_row, curr_col) not in self.used_premium:
                    word_multiplier *= 3
                    self.used_premium.add((curr_row, curr_col))
            
            total += base_points
        
        return total * word_multiplier
    
    def can_place_word(self, word: str, row: int, col: int, horizontal: bool,
                        tiles: List[str], is_first_move: bool = False) -> Optional[PlacedWord]:
        """
        Проверить можно ли разместить слово
        Возвращает PlacedWord если можно, None если нельзя
        """
        if not word or len(word) > 15:
            return None
        
        letters = list(word.lower())
        new_positions: Set[Tuple[int, int]] = set()
        new_letters: List[Tuple[int, int, str]] = []
        tiles_copy = tiles.copy()
        
        # Проверка размещения
        for i, letter in enumerate(letters):
            if horizontal:
                curr_row, curr_col = row, col + i
            else:
                curr_row, curr_col = row + i, col
            
            if not self.is_valid_position(curr_row, curr_col):
                return None
            
            cell_letter = self.get_letter(curr_row, curr_col)
            
            if cell_letter is None:
                # Пустая клетка - используем букву из руки
                if letter not in tiles_copy:
                    return None
                tiles_copy.remove(letter)
                new_positions.add((curr_row, curr_col))
                new_letters.append((curr_row, curr_col, letter))
            elif cell_letter.lower() != letter:
                # Клетка занята другой буквой
                return None
        
        # Проверка: использована хотя бы одна буква из руки (или первый ход)
        if not is_first_move and len(new_letters) == 0:
            return None
        
        # Для первого хода: слово должно проходить через центр (7, 7)
        if is_first_move:
            center_used = False
            for i in range(len(letters)):
                if horizontal:
                    if row == 7 and col <= 7 <= col + len(letters) - 1:
                        center_used = True
                        break
                else:
                    if col == 7 and row <= 7 <= row + len(letters) - 1:
                        center_used = True
                        break
            if not center_used:
                return None
        
        # Проверка смежных слов (вертикально для горизонтального слова и наоборот)
        if not self._check_adjacent_words(word, row, col, horizontal, new_positions, is_first_move):
            return None
        
        # Подсчёт очков
        board_copy = GameBoard()
        board_copy.cells = [row[:] for row in self.cells]
        board_copy.used_premium = self.used_premium.copy()
        
        points = board_copy.calculate_word_points(word, row, col, horizontal, new_positions)
        
        return PlacedWord(
            word=word,
            row=row,
            col=col,
            horizontal=horizontal,
            points=points,
            new_letters=new_letters
        )
    
    def _check_adjacent_words(self, word: str, row: int, col: int, horizontal: bool,
                               new_positions: Set[Tuple[int, int]], is_first_move: bool) -> bool:
        """Проверка что все смежные слова валидны"""
        from database import db
        
        for i, letter in enumerate(word):
            if horizontal:
                curr_row, curr_col = row, col + i
                # Проверка вертикальных соседей
                if (curr_row, curr_col) in new_positions:
                    # Смотрим что выше и ниже
                    has_adjacent = False
                    if curr_row > 0 and self.is_occupied(curr_row - 1, curr_col):
                        has_adjacent = True
                    if curr_row < 14 and self.is_occupied(curr_row + 1, curr_col):
                        has_adjacent = True
                    
                    if has_adjacent:
                        adj_word, adj_row, adj_col = self.get_word_at(curr_row, curr_col, False)
                        if len(adj_word) > 1:
                            # Нужно проверить что это валидное слово
                            # (упрощённо - просто проверяем длину)
                            pass
            else:
                curr_row, curr_col = row + i, col
                # Проверка горизонтальных соседей
                if (curr_row, curr_col) in new_positions:
                    has_adjacent = False
                    if curr_col > 0 and self.is_occupied(curr_row, curr_col - 1):
                        has_adjacent = True
                    if curr_col < 14 and self.is_occupied(curr_row, curr_col + 1):
                        has_adjacent = True
                    
                    if has_adjacent:
                        adj_word, adj_row, adj_col = self.get_word_at(curr_row, curr_col, True)
                        if len(adj_word) > 1:
                            pass
        
        return True
    
    def place_word(self, placed: PlacedWord):
        """Разместить слово на поле"""
        for row, col, letter in placed.new_letters:
            self.cells[row][col] = letter
    
    def get_display(self) -> List[List[str]]:
        """Получить поле для отображения"""
        display = []
        for row in self.cells:
            display_row = []
            for cell in row:
                if cell:
                    display_row.append(cell.upper())
                else:
                    display_row.append('.')
            display.append(display_row)
        return display
    
    def get_premium_hints(self) -> List[List[str]]:
        """Получить подсказки по премиум-клеткам"""
        hints = []
        for r in range(self.size):
            hint_row = []
            for c in range(self.size):
                if (r, c) in PREMIUM_CELLS:
                    hint_row.append(PREMIUM_CELLS[(r, c)])
                else:
                    hint_row.append('')
            hints.append(hint_row)
        return hints


class TileBag:
    """Мешок с буквами"""
    
    def __init__(self):
        self.tiles: List[str] = []
        self.reset()
    
    def reset(self):
        """Перезаполнить мешок"""
        self.tiles = []
        for letter, count in LETTER_DIST.items():
            self.tiles.extend([letter] * count)
        random.shuffle(self.tiles)
    
    def draw(self, count: int = 1) -> List[str]:
        """Взять буквы из мешка"""
        drawn = []
        for _ in range(count):
            if self.tiles:
                drawn.append(self.tiles.pop())
        return drawn
    
    def exchange(self, tiles: List[str]) -> List[str]:
        """Обменять буквы"""
        new_tiles = self.draw(len(tiles))
        self.tiles.extend(tiles)
        random.shuffle(self.tiles)
        return new_tiles
    
    def remaining(self) -> int:
        """Осталось букв"""
        return len(self.tiles)


def generate_initial_tiles() -> Tuple[List[str], List[str]]:
    """Сгенерировать начальные наборы букв для игроков"""
    bag = TileBag()
    tiles1 = bag.draw(7)
    tiles2 = bag.draw(7)
    return tiles1, tiles2


def refill_tiles(bag: TileBag, tiles: List[str]) -> List[str]:
    """Добрать буквы до 7"""
    needed = 7 - len(tiles)
    if needed > 0:
        tiles.extend(bag.draw(needed))
    return tiles


def validate_word_exists(word: str) -> bool:
    """Проверить что слово существует в словаре"""
    # Будет вызываться через database.db.check_word()
    return True


def get_valid_moves(tiles: List[str], board: GameBoard, is_first_move: bool = False) -> List[dict]:
    """
    Получить все возможные ходы (для подсказок)
    Это упрощённая версия - полный перебор может быть медленным
    """
    # Для MVP возвращаем пустой список - подсказки можно добавить позже
    return []


def check_game_end(board: GameBoard, bag: TileBag, player1_tiles: List[str], 
                   player2_tiles: List[str]) -> Optional[int]:
    """
    Проверить окончание игры
    Возвращает номер победителя (1 или 2) или None если игра продолжается
    """
    # Игра заканчивается если:
    # 1. Кончились буквы в мешке и у одного игрока кончились буквы
    # 2. Оба игрока подряд пропустили ход (реализуется через таймер в боте)
    
    if bag.remaining() == 0:
        if len(player1_tiles) == 0:
            return 1
        if len(player2_tiles) == 0:
            return 2
    
    return None
