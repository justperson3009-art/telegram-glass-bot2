"""
Бот психологической поддержки
"""
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

from database import db
from exercises import get_all_exercises, format_exercise, EXERCISES
from quotes import get_random_quote, get_support_message, get_quote_by_mood

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()


class MoodState(StatesGroup):
    waiting_for_mood = State()
    waiting_for_note = State()


# === Клавиатуры ===

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню"""
    kb = [
        [KeyboardButton(text="😊 Как я себя чувствую"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="🧘 Упражнения"), KeyboardButton(text="📝 Трекер привычек")],
        [KeyboardButton(text="💬 Поддержка"), KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_mood_keyboard() -> InlineKeyboardMarkup:
    """Выбор настроения"""
    builder = InlineKeyboardBuilder()
    emojis = ["😢", "😟", "😐", "🙂", "😊", "😄", "🤩"]
    for i in range(1, 8):
        builder.button(text=f"{emojis[i-1]} {i}", callback_data=f"mood_{i}")
    builder.adjust(7)
    return builder.as_markup()


def get_exercises_keyboard() -> InlineKeyboardMarkup:
    """Список упражнений"""
    builder = InlineKeyboardBuilder()
    for ex_id, ex_data in EXERCISES.items():
        builder.button(text=ex_data['name'], callback_data=f"ex_{ex_id}")
    builder.adjust(1)
    builder.button(text="🔙 Назад", callback_data="back_menu")
    return builder.as_markup()


def get_habits_keyboard(habits: list) -> InlineKeyboardMarkup:
    """Список привычек"""
    builder = InlineKeyboardBuilder()
    for habit in habits:
        status = "✅" if habit.completed_today else "⬜"
        builder.button(text=f"{status} {habit.name}", callback_data=f"habit_{habit.id}")
    builder.button(text="➕ Добавить привычку", callback_data="habit_add")
    builder.button(text="🔙 Назад", callback_data="back_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_support_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура поддержки"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💙 Получить поддержку", callback_data="support_message")
    builder.button(text="📖 Мотивационная цитата", callback_data="quote")
    builder.button(text="🧘 Дыхательное упражнение", callback_data="exercises")
    builder.button(text="🔙 Назад", callback_data="back_menu")
    builder.adjust(1, 1)
    return builder.as_markup()


# === Хендлеры ===

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start"""
    user_id = await db.get_or_create_user(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.first_name or "Друг"
    )

    await state.set_state(None)

    await message.answer(
        f"💙 **Привет, {message.from_user.first_name}!**\n\n"
        "Я — бот психологической поддержки. Я здесь, чтобы помочь тебе:\n\n"
        "• 📊 **Отслеживать настроение** — записывай, как ты себя чувствуешь\n"
        "• 🧘 **Делать упражнения** — дыхательные техники для успокоения\n"
        "• 📝 **Вести привычки** — забота о себе каждый день\n"
        "• 💬 **Получать поддержку** — мотивация и добрые слова\n\n"
        "Помни: ты не один(на). Ты важен(на). Ты справишься.\n\n"
        "Выбери, что хочешь сделать:",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.text == "😊 Как я себя чувствую")
async def check_mood(message: Message, state: FSMContext):
    """Проверка настроения"""
    await state.set_state(MoodState.waiting_for_mood)
    await message.answer(
        "💭 **Как ты себя чувствуешь сейчас?**\n\n"
        "Оцени своё настроение от 1 до 7:\n\n"
        "1 😢 — Очень плохо\n"
        "2 😟 — Плохо\n"
        "3 😐 — Нормально\n"
        "4 🙂 — Хорошо\n"
        "5 😊 — Очень хорошо\n"
        "6 😄 — Отлично\n"
        "7 🤩 — Прекрасно\n\n"
        "Нажми на кнопку:",
        reply_markup=get_mood_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("mood_"))
async def mood_selected(callback: CallbackQuery, state: FSMContext):
    """Выбрано настроение"""
    mood = int(callback.data.split("_")[1])
    await state.update_data(mood=mood)
    await state.set_state(MoodState.waiting_for_note)
    
    emojis = ["😢", "😟", "😐", "🙂", "😊", "😄", "🤩"]
    mood_names = ["Очень плохо", "Плохо", "Нормально", "Хорошо", "Очень хорошо", "Отлично", "Прекрасно"]
    
    await callback.message.answer(
        f"Спасибо! Ты оценил(а) своё настроение как **{mood_names[mood-1]} {emojis[mood-1]}**\n\n"
        "Хочешь добавить заметку? Напиши, что ты чувствуешь (или нажми /skip чтобы пропустить):",
        parse_mode="Markdown"
    )


@router.message(MoodState.waiting_for_note, F.text == "/skip")
@router.message(MoodState.waiting_for_note, F.text == "❌ Пропустить")
async def skip_note(message: Message, state: FSMContext):
    """Пропустить заметку"""
    data = await state.get_data()
    mood = data.get("mood", 5)
    user_id = message.from_user.id
    
    await db.add_mood(user_id, mood, "")
    
    quote = get_quote_by_mood(mood)
    
    await message.answer(
        f"✅ **Настроение записано!**\n\n"
        f"💭 {quote['text']}\n"
        f"_{quote['author']}_\n\n"
        "Заходи завтра, чтобы снова отметить своё настроение! 💙",
        parse_mode="Markdown"
    )
    await state.set_state(None)
    await message.answer("Главное меню", reply_markup=get_main_keyboard())


@router.message(MoodState.waiting_for_note)
async def save_note(message: Message, state: FSMContext):
    """Сохранить заметку"""
    data = await state.get_data()
    mood = data.get("mood", 5)
    note = message.text
    user_id = message.from_user.id
    
    await db.add_mood(user_id, mood, note)
    
    quote = get_quote_by_mood(mood)
    
    await message.answer(
        f"✅ **Настроение и заметка записаны!**\n\n"
        f"📝 _{note}_\n\n"
        f"💭 {quote['text']}\n"
        f"_{quote['author']}_\n\n"
        "Заходи завтра, чтобы снова отметить своё настроение! 💙",
        parse_mode="Markdown"
    )
    await state.set_state(None)
    await message.answer("Главное меню", reply_markup=get_main_keyboard())


@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    """Показать статистику"""
    user_id = message.from_user.id
    stats = await db.get_mood_stats(user_id, days=7)
    
    if stats['count'] == 0:
        await message.answer(
            "📊 **Статистика**\n\n"
            "Пока нет записей о настроении.\n"
            "Начни отслеживать своё состояние! 💙",
            parse_mode="Markdown"
        )
        return
    
    mood_emoji = "😢" if stats['avg'] <= 3 else "😐" if stats['avg'] <= 5 else "😊"
    
    text = f"""
📊 **Твоя статистика за 7 дней** {mood_emoji}

📈 Среднее настроение: **{stats['avg']}**
📉 Минимальное: **{stats['min']}**
📈 Максимальное: **{stats['max']}**
📝 Всего записей: **{stats['count']}**

💙 Продолжай отслеживать своё состояние!
"""
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "🧘 Упражнения")
async def show_exercises(message: Message):
    """Показать упражнения"""
    await message.answer(
        "🧘 **Дыхательные упражнения**\n\n"
        "Выберите технику для расслабления:",
        reply_markup=get_exercises_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("ex_"))
async def show_exercise(callback: CallbackQuery):
    """Показать упражнение"""
    ex_id = callback.data.split("_")[1]
    text = format_exercise(ex_id)
    
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()


@router.message(F.text == "📝 Трекер привычек")
async def show_habits(message: Message):
    """Показать привычки"""
    user_id = message.from_user.id
    habits = await db.get_habits(user_id)
    
    if not habits:
        await message.answer(
            "📝 **Трекер привычек**\n\n"
            "У тебя пока нет привычек. Давай добавим!\n\n"
            "Нажми '➕ Добавить привычку' чтобы начать:",
            reply_markup=get_habits_keyboard([]),
            parse_mode="Markdown"
        )
        return
    
    text = "📝 **Твои привычки на сегодня**\n\n"
    for i, habit in enumerate(habits, 1):
        status = "✅" if habit.completed_today else "⬜"
        text += f"{i}. {status} {habit.name}\n"
    
    await message.answer(
        text + "\nНажми на привычку, чтобы отметить выполнение:",
        reply_markup=get_habits_keyboard(habits),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "habit_add")
async def add_habit_prompt(callback: CallbackQuery):
    """Добавить привычку"""
    await callback.message.answer(
        "➕ **Новая привычка**\n\n"
        "Напиши название привычки (например: 'Выпить 8 стаканов воды'):\n\n"
        "Или нажми /cancel чтобы отменить",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("habit_"))
async def toggle_habit(callback: CallbackQuery):
    """Отметить привычку"""
    habit_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    habits = await db.get_habits(user_id)
    habit = next((h for h in habits if h.id == habit_id), None)
    
    if not habit:
        await callback.answer("❌ Привычка не найдена", show_alert=True)
        return
    
    if habit.completed_today:
        await db.uncomplete_habit(habit_id, user_id)
        await callback.answer("❌ Отменено", show_alert=True)
    else:
        await db.complete_habit(habit_id, user_id)
        await callback.answer("✅ Молодец! Так держать! 💙", show_alert=True)
    
    # Обновить список
    habits = await db.get_habits(user_id)
    await callback.message.edit_reply_markup(reply_markup=get_habits_keyboard(habits))


@router.message(F.text == "💬 Поддержка")
async def show_support(message: Message):
    """Показать поддержку"""
    await message.answer(
        "💙 **Поддержка**\n\n"
        "Я здесь, чтобы поддержать тебя. Выбери:",
        reply_markup=get_support_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "support_message")
async def send_support(callback: CallbackQuery):
    """Отправить сообщение поддержки"""
    msg = get_support_message()
    await callback.message.answer(
        f"🤗 {msg}\n\n"
        "Помни: ты не один(на). Я всегда здесь, чтобы поддержать тебя! 💙",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "quote")
async def send_quote(callback: CallbackQuery):
    """Отправить цитату"""
    quote = get_random_quote()
    await callback.message.answer(
        f"📖 **Цитата дня**\n\n"
        f"_{quote['text']}_\n\n"
        f"— {quote['author']}\n\n"
        "💙 Возвращайся за новой порцией мотивации!",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "exercises")
async def show_exercises_menu(callback: CallbackQuery):
    """Показать меню упражнений"""
    await callback.message.answer(
        "🧘 **Дыхательные упражнения**\n\n"
        "Выберите технику:",
        reply_markup=get_exercises_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "back_menu")
async def back_to_menu(callback: CallbackQuery):
    """Вернуться в меню"""
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "🏠 **Главное меню**\n\n"
        "Выбери, что хочешь сделать:",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(F.text == "❓ Помощь")
async def show_help(message: Message):
    """Показать справку"""
    text = """
❓ **Помощь**

Я — бот психологической поддержки. Вот что я умею:

😊 **Как я себя чувствую**
• Оцени своё настроение от 1 до 7
• Добавь заметку о том, что чувствуешь
• Получи цитату поддержки

📊 **Статистика**
• Посмотри среднее настроение за неделю
• Отслеживай динамику состояния

🧘 **Упражнения**
• Квадратное дыхание — от тревоги
• Волна расслабления — перед сном
• Заземление 5-4-3-2-1 — при панике
• Энергетическое дыхание — для бодрости

📝 **Трекер привычек**
• Добавляй полезные привычки
• Отмечай выполнение каждый день
• Заботься о себе регулярно

💬 **Поддержка**
• Получи доброе сообщение
• Прочитай мотивационную цитату
• Сделай дыхательное упражнение

💙 **Помни:**
• Ты не один(на)
• Ты важен(на)
• Ты справишься
• Просьба о помощи — это нормально

**Экстренная помощь:**
Если тебе очень плохо, обратись к специалисту:
• Телефон доверия: 8-800-2000-122 (бесплатно)
• МЧС психологическая помощь: +7 (495) 989-50-50
"""
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    """Отменить текущее действие"""
    await state.set_state(None)
    await message.answer(
        "❌ Отменено",
        reply_markup=get_main_keyboard()
    )


@router.message(Command("skip"))
async def skip_command(message: Message, state: FSMContext):
    """Пропустить заметку"""
    if await state.get_state() == MoodState.waiting_for_note:
        await skip_note(message, state)
