# 🎮 Эрудит Bot — Telegram PvP игра в слова

**Эрудит** — это классическая игра в слова (аналог Скраббла) для Telegram с возможностью игры против других игроков онлайн.

## 📋 Возможности

- 🎯 **PvP сражения** — играй против случайных соперников или друзей
- ⏱️ **Режимы игры**:
  - Блиц (3 мин) — больше слов за время
  - Классика (10 мин) — больше очков за время
  - На очки — игра до 1000 очков
- 🔍 **Поиск соперника**:
  - Случайный подбор
  - По нику (@username)
- 📊 **Рейтинг и статистика** — глобальный лидерборд
- 💬 **Игровой чат** — общение во время игры

## 🚀 Быстрый старт

### 1. Клонирование/создание проекта

```bash
cd erudit_bot
```

### 2. Создание виртуального окружения

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```env
# Токен бота от @BotFather
BOT_TOKEN=1234567890:AABBccDDeeFFggHHiiJJkkLLmmNNooP

# ID администратора (ваш Telegram ID, можно узнать у @userinfobot)
ADMIN_ID=123456789
```

### 5. Запуск

```bash
python main.py
```

## 🐳 Запуск через Docker

### Требования
- Docker
- Docker Compose

### Установка и запуск

```bash
# Копирование .env файла
cp .env.example .env

# Редактирование .env (добавить BOT_TOKEN)

# Сборка и запуск
docker-compose up -d --build

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

## 📖 Как играть

1. **Запустите бота** — нажмите `/start`
2. **Выберите режим** — Блиц или На очки
3. **Найдите соперника** — случайно или по нику
4. **Составляйте слова** из 7 букв
5. **Размещайте на поле** 15x15
6. **Побеждайте** — набрав больше очков/слов!

### Правила

- Первое слово должно пройти через центр поля ★
- Каждая буква имеет стоимость (1-10 очков)
- Премиум-клетки умножают очки:
  - 🟩 **x2 буква** — удваивает стоимость буквы
  - 🟪 **x3 буква** — утраивает стоимость буквы
  - 🟦 **x2 слово** — удваивает всё слово
  - 🟥 **x3 слово** — утраивает всё слово

## 📁 Структура проекта

```
erudit_bot/
├── main.py           # Точка входа
├── bot.py            # Хендлеры и логика бота
├── database.py       # Работа с SQLite
├── game_logic.py     # Логика игры (поле, буквы, очки)
├── requirements.txt  # Зависимости Python
├── Dockerfile        # Docker образ
├── docker-compose.yml # Docker Compose
├── .env.example      # Шаблон переменных окружения
└── README.md         # Этот файл
```

## 🔧 Настройка для продакшена

### 1. Получение токена бота

1. Откройте @BotFather в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Скопируйте токен в `.env`

### 2. Хостинг

#### Railway.app

```bash
# Установите Railway CLI
npm i -g @railway/cli

# Авторизуйтесь
railway login

# Инициализируйте проект
railway init

# Добавьте переменные окружения
railway variables set BOT_TOKEN=xxx

# Деплой
railway up
```

#### VPS (Ubuntu)

```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Клонирование проекта
git clone <your-repo> erudit_bot
cd erudit_bot

# Настройка .env
cp .env.example .env
nano .env  # добавьте BOT_TOKEN

# Запуск
docker-compose up -d
```

## 📝 Расширение словаря

Для добавления слов в словарь используйте SQL:

```sql
INSERT OR IGNORE INTO words (word, length) VALUES ('слово', 5);
```

Или через Python:

```python
from database import db
await db.add_word("новое_слово")
```

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте ветку (`git checkout -b feature/amazing`)
3. Закоммитьте изменения (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing`)
5. Откройте Pull Request

## 📄 Лицензия

MIT License — используйте на здоровье!

## 👨‍💻 Контакты

- Telegram: @your_username
- GitHub: your_username

---

**Приятной игры! 🎉**
