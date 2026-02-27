"""
Скрипт для тестирования бота - создаёт тестового соперника
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db, GameMode


async def create_test_bot():
    """Создать тестового бота для игры"""
    await db.connect()
    
    # Создаём тестового игрока
    test_bot = await db.get_or_create_player(
        telegram_id=999999999,  # фейковый ID
        username="erudit_bot_partner",
        first_name="Тестовый соперник"
    )
    
    print(f"✅ Тестовый игрок создан: ID={test_bot.id}, Telegram ID={test_bot.telegram_id}")
    print(f"   Username: @{test_bot.username}")
    print(f"   Рейтинг: {test_bot.rating}")
    
    await db.close()


if __name__ == "__main__":
    print("Создание тестового соперника...")
    asyncio.run(create_test_bot())
    print("Готово!")
