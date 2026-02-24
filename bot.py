"""
Telegram бот Эрудит - PvP игра в слова
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, 
    InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import db, Player, Game, GameMode, GameStatus
from game_logic import (
    GameBoard, TileBag, LETTER_POINTS,
    generate_initial_tiles, refill_tiles, check_game_end
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Единый роутер для всех хендлеров
router = Router()

# Алиасы для совместимости
main_router = router
game_router = router
search_router = router


# === States ===
class GameState(StatesGroup):
    """Состояния FSM"""
    menu = State()
    searching = State()
    waiting_for_nickname = State()
    choosing_mode = State()
    choosing_time = State()
    playing = State()
    placing_word = State()


# === Клавиатуры ===

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню"""
    kb = [
        [KeyboardButton(text="🎮 Новая игра"), KeyboardButton(text="📊 Рейтинг")],
        [KeyboardButton(text="📈 Моя статистика"), KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_mode_keyboard() -> InlineKeyboardMarkup:
    """Выбор режима игры"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⏱️ Блиц (3 мин)", callback_data="mode_time_words_180")
    builder.button(text="🕐 Классика (10 мин)", callback_data="mode_time_words_600")
    builder.button(text="📝 На очки (до 1000)", callback_data="mode_points_only_0")
    builder.button(text="🔙 Назад", callback_data="back_menu")
    builder.adjust(1, 1, 1)
    return builder.as_markup()


def get_search_opponent_keyboard() -> InlineKeyboardMarkup:
    """Выбор способа поиска соперника"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎲 Случайный соперник", callback_data="search_random")
    builder.button(text="👤 По нику", callback_data="search_nickname")
    builder.button(text="🔙 Назад", callback_data="back_menu")
    builder.adjust(1, 1)
    return builder.as_markup()


def get_game_keyboard(game: Game, player_telegram_id: int) -> InlineKeyboardMarkup:
    """Клавиатура во время игры"""
    builder = InlineKeyboardBuilder()
    
    is_my_turn = game.current_turn == player_telegram_id
    
    # Кнопки действий
    if is_my_turn:
        builder.button(text="📝 Сделать ход", callback_data="action_make_move")
        builder.button(text="🔄 Обменять буквы", callback_data="action_exchange")
        builder.button(text="⏭️ Пропустить ход", callback_data="action_pass")
    else:
        builder.button(text="🔄 Обновить", callback_data="action_refresh")
    
    # Кнопки управления
    builder.button(text="💬 Чат", callback_data="action_chat")
    builder.button(text="📋 История", callback_data="action_history")
    builder.button(text="❌ Сдаться", callback_data="action_surrender")
    
    builder.adjust(3, 2, 1)
    return builder.as_markup()


def get_tiles_keyboard(tiles: list, prefix: str = "tile_") -> InlineKeyboardMarkup:
    """Клавиатура с буквами"""
    builder = InlineKeyboardBuilder()
    
    for i, tile in enumerate(tiles):
        points = LETTER_POINTS.get(tile.lower(), 1)
        builder.button(text=f"{tile.upper()}[{points}]", callback_data=f"{prefix}{i}_{tile}")
    
    builder.button(text="✅ Готово", callback_data=f"{prefix}done")
    builder.button(text="❌ Отмена", callback_data=f"{prefix}cancel")
    builder.adjust(7, 7, 2)
    return builder.as_markup()


def get_board_preview(board: GameBoard) -> str:
    """Текстовое превью поля"""
    display = board.get_display()
    
    # Нумерация колонок
    header = "   " + " ".join(f"{i:2}" for i in range(15)) + "\n"
    header += "   " + "─" * 44 + "\n"
    
    rows = ""
    for i, row in enumerate(display):
        rows += f"{i:2} │" + " ".join(f"{c:2}" for c in row) + "│\n"
    
    return header + rows


def get_game_status_text(game: Game, player1: Player, player2: Player, 
                          current_player_id: int) -> str:
    """Текст статуса игры"""
    mode_names = {
        GameMode.TIME_WORDS: "⏱️ Блиц (больше слов за время)",
        GameMode.TIME_POINTS: "⏱️ Блиц (больше очков за время)",
        GameMode.POINTS_ONLY: "📝 На очки (до 1000)"
    }
    
    time_str = ""
    if game.time_limit > 0:
        mins = game.time_remaining // 60
        secs = game.time_remaining % 60
        time_str = f"\n⏰ Время: {mins}:{secs:02d}"
    
    turn_emoji = "➡️" if game.current_turn == current_player_id else "⏳"
    
    text = f"""
{mode_names.get(game.mode, "Игра")}
{time_str}

👤 {player1.first_name}: {game.player1_score} оч. | {game.player1_words} слов
👤 {player2.first_name}: {game.player2_score} оч. | {game.player2_words} слов

{turn_emoji} Ход: {'Ваш' if game.current_turn == current_player_id else 'Соперника'}
"""
    return text.strip()


# === Хендлеры ===

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start"""
    player = await db.get_or_create_player(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.first_name or "Игрок"
    )
    
    await state.set_state(GameState.menu)
    
    await message.answer(
        f"👋 Привет, {player.first_name}!\n\n"
        "Добро пожаловать в **Эрудит** — игру слов!\n\n"
        "📚 **Правила:**\n"
        "• Составляйте слова из букв на поле 15x15\n"
        "• Каждая буква имеет свою стоимость\n"
        "• Премиум-клетки умножают очки\n"
        "• Побеждает набравший больше очков/слов\n\n"
        "Выберите действие в меню:",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.text == "🎮 Новая игра")
async def new_game_menu(message: Message, state: FSMContext):
    """Меню новой игры"""
    # Проверка активной игры
    active_game = await db.get_active_game(message.from_user.id)
    if active_game and active_game.status == GameStatus.ACTIVE:
        await message.answer(
            "⚠️ У вас уже есть активная игра!\n"
            "Завершите её перед началом новой."
        )
        return
    
    await state.set_state(GameState.choosing_mode)
    await message.answer(
        "🎮 **Выберите режим игры:**\n\n"
        "⏱️ **Блиц** — больше слов за отведённое время\n"
        "📝 **На очки** — игра до набора 1000 очков",
        reply_markup=get_mode_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.text == "📊 Рейтинг")
async def show_leaderboard(message: Message):
    """Показать лидерборд"""
    players = await db.get_leaderboard(10)
    
    text = "🏆 **Топ игроков**\n\n"
    for i, player in enumerate(players, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} **{player.first_name}** — {player.rating} оч. "
        text += f"({player.games_won}/{player.games_played})\n"
    
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "📈 Моя статистика")
async def show_stats(message: Message):
    """Показать статистику игрока"""
    player = await db.get_player_by_telegram_id(message.from_user.id)
    
    if not player:
        await message.answer("❌ Игрок не найден")
        return
    
    win_rate = (player.games_won / player.games_played * 100) if player.games_played > 0 else 0
    
    text = f"""
📊 **Статистика: {player.first_name}**

🏅 Рейтинг: {player.rating}
🎮 Игр сыграно: {player.games_played}
✅ Побед: {player.games_won}
📈 Процент побед: {win_rate:.1f}%
"""
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "❓ Помощь")
async def show_help(message: Message):
    """Показать справку"""
    text = """
❓ **Помощь**

🎮 **Как играть:**
1. Найдите соперника или играйте с другом
2. Составляйте слова из 7 букв
3. Размещайте слова на поле 15x15
4. Первое слово должно пройти через центр ★

📊 **Подсчёт очков:**
• Каждая буква имеет стоимость (1-10 очков)
• 🟩 x2 буква — удваивает стоимость буквы
• 🟪 x3 буква — утраивает стоимость буквы  
• 🟦 x2 слово — удваивает всё слово
• 🟥 x3 слово — утраивает всё слово

🏆 **Победа:**
• В режиме "Блиц" — больше слов/очков за время
• В режиме "На очки" — первым набрать 1000 очков

💡 **Советы:**
• Используйте длинные слова для больше очков
• Ставьте буквы на премиум-клетки
• Следите за временем в блице!
"""
    await message.answer(text, parse_mode="Markdown")


# === Выбор режима ===

@router.callback_query(F.data.startswith("mode_"))
async def mode_selected(callback: CallbackQuery, state: FSMContext):
    """Выбран режим игры"""
    parts = callback.data.split("_")
    mode_name = parts[1]
    time_limit = int(parts[2]) if len(parts) > 2 else 0
    
    mode_map = {
        "time_words": GameMode.TIME_WORDS,
        "time_points": GameMode.TIME_POINTS,
        "points_only": GameMode.POINTS_ONLY
    }
    
    mode = mode_map.get(mode_name, GameMode.TIME_WORDS)
    
    # Сохраняем выбор в состоянии
    await state.update_data(mode=mode.value, time_limit=time_limit)
    await state.set_state(GameState.searching)
    
    await callback.message.edit_text(
        "🔍 **Поиск соперника**\n\n"
        "Выберите способ поиска:",
        reply_markup=get_search_opponent_keyboard(),
        parse_mode="Markdown"
    )


# === Поиск соперника ===

@router.callback_query(F.data == "search_random")
async def search_random(callback: CallbackQuery, state: FSMContext):
    """Поиск случайного соперника"""
    data = await state.get_data()
    mode = GameMode(data.get("mode", "time_words"))
    time_limit = data.get("time_limit", 180)
    
    # Добавляем в очередь
    await db.add_to_queue(callback.from_user.id, mode, time_limit)
    
    # Проверяем есть ли соперник
    match = await db.find_match(callback.from_user.id)
    
    if match:
        # Нашли соперника!
        await db.remove_from_queue(callback.from_user.id)
        await db.remove_from_queue(match["telegram_id"])
        
        # Создаём игру
        player1 = await db.get_player_by_telegram_id(callback.from_user.id)
        player2 = await db.get_player_by_telegram_id(match["telegram_id"])
        
        game = await db.create_game(player1.id, player2.id, mode, time_limit)
        
        # Генерируем начальные буквы
        tiles1, tiles2 = generate_initial_tiles()
        game.player1_tiles = "".join(tiles1)
        game.player2_tiles = "".join(tiles2)
        game.current_turn = player1.telegram_id
        game.started_at = datetime.now().isoformat()
        
        if time_limit > 0:
            game.time_remaining = time_limit
        
        await db.update_game(game)
        
        # Уведомляем обоих игроков
        await callback.message.edit_text(
            f"🎮 **Игра началась!**\n\n"
            f"Ваш соперник: @{match['username'] or match['first_name']}\n\n"
            f"Ваши буквы: {' '.join(t.upper() for t in tiles1)}\n\n"
            f"{'➡️ Ваш ход!' if game.current_turn == callback.from_user.id else '⏳ Ход соперника'}",
            reply_markup=get_game_keyboard(game, callback.from_user.id),
            parse_mode="Markdown"
        )
        
        # Отправляем уведомление сопернику
        try:
            await callback.bot.send_message(
                match["telegram_id"],
                f"🎮 **Игра началась!**\n\n"
                f"Ваш соперник: @{callback.from_user.username or callback.from_user.first_name}\n\n"
                f"Ваши буквы: {' '.join(t.upper() for t in tiles2)}\n\n"
                f"{'➡️ Ваш ход!' if game.current_turn == match['telegram_id'] else '⏳ Ход соперника'}",
                reply_markup=get_game_keyboard(game, match["telegram_id"]),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение сопернику: {e}")
    else:
        await callback.message.edit_text(
            "⏳ **Поиск соперника...**\n\n"
            "Ожидаем подключения другого игрока.\n"
            "Вы можете отменить поиск командой /cancel",
            parse_mode="Markdown"
        )


@router.callback_query(F.data == "search_nickname")
async def search_nickname(callback: CallbackQuery, state: FSMContext):
    """Поиск по нику"""
    await state.set_state(GameState.waiting_for_nickname)
    await callback.message.edit_text(
        "👤 **Поиск по нику**\n\n"
        "Введите @username соперника:",
        parse_mode="Markdown"
    )


@router.message(GameState.waiting_for_nickname)
async def nickname_entered(message: Message, state: FSMContext):
    """Введён ник соперника"""
    username = message.text.strip().lstrip('@')
    
    opponent = await db.search_player_by_username(username)
    
    if not opponent:
        await message.answer(
            f"❌ Игрок @{username} не найден.\n"
            "Попробуйте ещё раз или выберите другой способ поиска.",
            reply_markup=get_search_opponent_keyboard()
        )
        return
    
    if opponent.telegram_id == message.from_user.id:
        await message.answer(
            "❌ Нельзя играть с самим собой!",
            reply_markup=get_search_opponent_keyboard()
        )
        return
    
    # Проверяем активные игры
    active_game = await db.get_active_game(opponent.telegram_id)
    if active_game:
        await message.answer(
            f"❌ @{username} сейчас в игре.\n"
            "Попробуйте позже или выберите другого соперника.",
            reply_markup=get_search_opponent_keyboard()
        )
        return
    
    # Создаём игру
    data = await state.get_data()
    mode = GameMode(data.get("mode", "time_words"))
    time_limit = data.get("time_limit", 180)
    
    player1 = await db.get_player_by_telegram_id(message.from_user.id)
    player2 = opponent
    
    game = await db.create_game(player1.id, player2.id, mode, time_limit)
    
    tiles1, tiles2 = generate_initial_tiles()
    game.player1_tiles = "".join(tiles1)
    game.player2_tiles = "".join(tiles2)
    game.current_turn = player1.telegram_id
    game.started_at = datetime.now().isoformat()
    
    if time_limit > 0:
        game.time_remaining = time_limit
    
    await db.update_game(game)
    
    await state.set_state(GameState.playing)
    
    await message.answer(
        f"🎮 **Игра началась!**\n\n"
        f"Ваш соперник: @{opponent.username or opponent.first_name}\n\n"
        f"Ваши буквы: {' '.join(t.upper() for t in tiles1)}\n\n"
        f"{'➡️ Ваш ход!' if game.current_turn == message.from_user.id else '⏳ Ход соперника'}",
        reply_markup=get_game_keyboard(game, message.from_user.id),
        parse_mode="Markdown"
    )
    
    # Уведомляем соперника
    try:
        await message.bot.send_message(
            opponent.telegram_id,
            f"🎮 **Вас вызвали на игру!**\n\n"
            f"Соперник: @{message.from_user.username or message.from_user.first_name}\n\n"
            f"Ваши буквы: {' '.join(t.upper() for t in tiles2)}\n\n"
            f"{'➡️ Ваш ход!' if game.current_turn == opponent.telegram_id else '⏳ Ход соперника'}",
            reply_markup=get_game_keyboard(game, opponent.telegram_id),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение сопернику: {e}")


@router.callback_query(F.data == "back_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Вернуться в меню"""
    await state.set_state(GameState.menu)
    await db.remove_from_queue(callback.from_user.id)
    
    await callback.message.edit_text(
        "🏠 Главное меню",
        reply_markup=get_main_keyboard()
    )


# === Игровой процесс ===

@router.callback_query(F.data == "action_make_move")
async def make_move(callback: CallbackQuery, state: FSMContext):
    """Начать ход — выбор букв"""
    game = await db.get_active_game(callback.from_user.id)
    
    if not game:
        await callback.answer("❌ Активная игра не найдена", show_alert=True)
        return
    
    if game.current_turn != callback.from_user.id:
        await callback.answer("⏳ Сейчас не ваш ход!", show_alert=True)
        return
    
    # Определяем чьи буквы показывать
    player = await db.get_player_by_telegram_id(callback.from_user.id)
    is_player1 = player.id == game.player1_id
    tiles = list(game.player1_tiles if is_player1 else game.player2_tiles)
    
    await state.update_data(
        game_id=game.id,
        selected_tiles=[],
        current_tiles=tiles
    )
    await state.set_state(GameState.placing_word)
    
    await callback.message.edit_text(
        f"📝 **Ваш ход**\n\n"
        f"Буквы: {' '.join(t.upper() for t in tiles)}\n\n"
        "Выберите буквы для слова (в порядке составления):",
        reply_markup=get_tiles_keyboard(tiles, "select_"),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("select_"))
async def select_tile(callback: CallbackQuery, state: FSMContext):
    """Выбор буквы для слова"""
    data = await callback.data.split("_")
    
    if data[1] == "done":
        # Завершили выбор — спрашиваем куда поставить
        selected = await state.get_data()
        tiles = selected.get("selected_tiles", [])
        
        if not tiles:
            await callback.answer("❌ Выберите хотя бы одну букву", show_alert=True)
            return
        
        word = "".join(t[1] for t in tiles)  # буква это второй элемент кортежа
        
        await state.update_data(current_word=word)
        await callback.message.edit_text(
            f"📝 Слово: **{word.upper()}**\n\n"
            f"Введите координаты и направление:\n"
            "Пример: `7 7 г` (строка, колонка, г=горизонтально/в=вертикально)\n\n"
            "Или /cancel для отмены",
            parse_mode="Markdown"
        )
        return
    
    if data[1] == "cancel":
        await state.set_state(GameState.playing)
        await callback.message.edit_text(
            "❌ Ход отменён",
            reply_markup=get_game_keyboard(await db.get_active_game(callback.from_user.id), callback.from_user.id)
        )
        return
    
    # Выбор буквы
    idx = int(data[1])
    letter = data[2]
    
    state_data = await state.get_data()
    selected = state_data.get("selected_tiles", [])
    current_tiles = state_data.get("current_tiles", [])
    
    # Удаляем выбранную букву из доступных
    current_tiles.pop(idx)
    selected.append((idx, letter))
    
    await state.update_data(
        selected_tiles=selected,
        current_tiles=current_tiles
    )
    
    await callback.message.edit_text(
        f"📝 **Ваш ход**\n\n"
        f"Буквы: {' '.join(t.upper() for t in [t[1] for t in selected])}\n"
        f"Осталось: {' '.join(t.upper() for t in current_tiles) if current_tiles else 'ничего'}\n\n"
        "Выбирайте ещё или нажмите ✅ Готово:",
        reply_markup=get_tiles_keyboard(current_tiles, "select_"),
        parse_mode="Markdown"
    )


@router.message(GameState.placing_word)
async def place_word_input(message: Message, state: FSMContext):
    """Ввод координат для размещения слова"""
    if message.text.startswith('/'):
        if message.text == "/cancel":
            await state.set_state(GameState.playing)
            await message.answer(
                "❌ Ход отменён",
                reply_markup=get_game_keyboard(await db.get_active_game(message.from_user.id), message.from_user.id)
            )
        return
    
    parts = message.text.lower().strip().split()
    
    if len(parts) != 3:
        await message.answer(
            "❌ Неверный формат.\n"
            "Пример: `7 7 г` (строка, колонка, направление)\n"
            "г = горизонтально, в = вертикально"
        )
        return
    
    try:
        row = int(parts[0])
        col = int(parts[1])
        direction = parts[2]
        
        if not (0 <= row <= 14 and 0 <= col <= 14):
            raise ValueError("Координаты вне поля")
        
        horizontal = direction in ('г', 'h', 'горизонтально')
        
    except (ValueError, IndexError) as e:
        await message.answer(f"❌ Ошибка: {e}")
        return
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    game_id = state_data.get("game_id")
    word = state_data.get("current_word", "").lower()
    
    if not word:
        await message.answer("❌ Слово не выбрано")
        return
    
    # Загружаем игру и поле
    game = await db.get_game(game_id)
    board = GameBoard.from_json(game.board)
    bag = TileBag()  # Для реигры нужно сохранять состояние мешка
    
    # Определяем игрока
    player = await db.get_player_by_telegram_id(message.from_user.id)
    is_player1 = player.id == game.player1_id
    tiles = list(game.player1_tiles if is_player1 else game.player2_tiles)
    
    # Первый ход?
    is_first_move = game.player1_score == 0 and game.player2_score == 0
    
    # Проверяем размещение
    placed = board.can_place_word(word, row, col, horizontal, tiles, is_first_move)
    
    if not placed:
        await message.answer(
            "❌ Нельзя разместить слово здесь.\n\n"
            "Проверьте:\n"
            "• Слово должно проходить через центр (первый ход)\n"
            "• Все буквы должны быть на поле\n"
            "• Смежные слова должны быть валидны"
        )
        return
    
    # Проверяем слово в словаре
    word_exists = await db.check_word(word)
    
    if not word_exists:
        # Для MVP позволяем любое слово (можно усилить проверку)
        logger.info(f"Слово '{word}' не найдено в словаре, разрешаем для MVP")
    
    # Размещаем слово
    board.place_word(placed)
    
    # Обновляем счёт
    if is_player1:
        game.player1_score += placed.points
        game.player1_words += 1
    else:
        game.player2_score += placed.points
        game.player2_words += 1
    
    # Обновляем буквы
    new_tiles = list(tiles)
    for _, _, letter in placed.new_letters:
        if letter in new_tiles:
            new_tiles.remove(letter)
    
    new_tiles = refill_tiles(bag, new_tiles)
    
    if is_player1:
        game.player1_tiles = "".join(new_tiles)
    else:
        game.player2_tiles = "".join(new_tiles)
    
    # Сохраняем поле
    game.board = board.to_json()
    
    # Добавляем ход в историю
    await db.add_move(game.id, player.id, word, placed.points)
    
    # Передаём ход
    opponent_id = game.player2_id if is_player1 else game.player1_id
    opponent = await db.get_player_by_id(opponent_id)
    game.current_turn = opponent.telegram_id
    
    # Проверяем окончание игры
    winner = check_game_end(board, bag, 
                           list(game.player1_tiles) if is_player1 else new_tiles,
                           new_tiles if is_player1 else list(game.player2_tiles))
    
    if winner:
        game.status = GameStatus.FINISHED
        game.finished_at = datetime.now().isoformat()
        game.winner_id = winner
        # Обновляем рейтинг и статистику
        # ...
    
    await db.update_game(game)
    
    await state.set_state(GameState.playing)
    
    # Показываем результат
    board_preview = board.get_display()
    preview_text = "   " + " ".join(f"{i:2}" for i in range(min(10, 15))) + "\n"
    for i, row in enumerate(board_preview[:10]):
        preview_text += f"{i:2} │" + " ".join(f"{c:2}" for c in row[:10]) + "│\n"
    
    await message.answer(
        f"✅ **Слово размещено!**\n\n"
        f"📝 {word.upper()} — {placed.points} оч.\n\n"
        f"👤 Вы: {game.player1_score if is_player1 else game.player2_score} оч.\n"
        f"👤 Соперник: {game.player2_score if is_player1 else game.player1_score} оч.\n\n"
        f"{'🎉 Победа!' if winner and winner == (1 if is_player1 else 2) else '⏳ Ход соперника'}\n\n"
        f"```\n{preview_text}\n```",
        parse_mode="Markdown"
    )
    
    # Уведомляем соперника
    try:
        await message.bot.send_message(
            opponent.telegram_id,
            f"📝 **Соперник сделал ход!**\n\n"
            f"Слово: {word.upper()} ({placed.points} оч.)\n\n"
            f"👤 Вы: {game.player2_score if is_player1 else game.player1_score} оч.\n"
            f"👤 Соперник: {game.player1_score if is_player1 else game.player2_score} оч.\n\n"
            f"➡️ **Ваш ход!**",
            reply_markup=get_game_keyboard(game, opponent.telegram_id),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить соперника: {e}")


@router.callback_query(F.data == "action_refresh")
async def refresh_game(callback: CallbackQuery):
    """Обновить состояние игры"""
    game = await db.get_active_game(callback.from_user.id)
    
    if not game:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return
    
    player1 = await db.get_player_by_id(game.player1_id)
    player2 = await db.get_player_by_id(game.player2_id)
    
    is_player1 = player1.telegram_id == callback.from_user.id
    
    tiles = list(game.player1_tiles if is_player1 else game.player2_tiles)
    
    text = get_game_status_text(game, player1, player2, callback.from_user.id)
    text += f"\n\nВаши буквы: {' '.join(t.upper() for t in tiles)}"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_game_keyboard(game, callback.from_user.id),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "action_surrender")
async def surrender(callback: CallbackQuery):
    """Сдаться"""
    game = await db.get_active_game(callback.from_user.id)
    
    if not game:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return
    
    # Определяем победителя
    player = await db.get_player_by_telegram_id(callback.from_user.id)
    is_player1 = player.id == game.player1_id
    winner_id = 2 if is_player1 else 1
    
    game.status = GameStatus.FINISHED
    game.finished_at = datetime.now().isoformat()
    game.winner_id = winner_id
    await db.update_game(game)
    
    # Обновляем статистику
    await db.update_stats(player.id, False)
    
    opponent_id = game.player2_id if is_player1 else game.player1_id
    opponent = await db.get_player_by_id(opponent_id)
    await db.update_stats(opponent.id, True)
    
    await callback.message.edit_text(
        "🏳️ **Вы сдались**\n\n"
        f"Победитель: @{opponent.username or opponent.first_name}",
        parse_mode="Markdown"
    )


# === Таймер игры ===

async def game_timer(bot: Bot):
    """Фоновая задача для таймеров игр"""
    while True:
        try:
            # Получаем все активные игры с таймером
            # Для упрощения — проверяем раз в секунду
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Ошибка в таймере: {e}")


# === Запуск ===

async def main():
    """Точка входа"""
    # Подключение к БД
    await db.connect()
    
    # Инициализация бота
    bot = Bot(token="YOUR_BOT_TOKEN")  # Заменить на токен из .env
    dp = Dispatcher()
    
    dp.include_routers(main_router, game_router, search_router)
    
    # Запуск поллинга
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
