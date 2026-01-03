#!/bin/bash
# Диагностика Telegram бота на удаленном сервере

echo "=== ДИАГНОСТИКА TELEGRAM БОТА ==="
echo ""

echo "1. Статус контейнеров:"
docker compose ps
echo ""

echo "2. Логи бота (последние 20 строк):"
docker compose logs telegram-bot --tail=20
echo ""

echo "3. Проверка процесса бота:"
docker compose exec telegram-bot ps aux | grep python || echo "❌ Процесс не найден"
echo ""

echo "4. Проверка переменных окружения:"
docker compose exec telegram-bot python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('/app/.env')
bot_token = os.getenv('BOT_TOKEN')
chat_id = os.getenv('CHAT_ID')
print('BOT_TOKEN:', '✅ Установлен (' + str(len(bot_token)) + ' символов)' if bot_token else '❌ Не установлен')
print('CHAT_ID:', f'✅ Установлен: {chat_id}' if chat_id else '❌ Не установлен')
"
echo ""

echo "5. Проверка конфигурации:"
docker compose exec telegram-bot python3 -c "
from config import Config
try:
    config = Config('/app/targets.yml')
    print(f'✅ Конфигурация загружена: {len(config.pages)} страниц')
except Exception as e:
    print(f'❌ Ошибка загрузки конфигурации: {e}')
"
echo ""

echo "6. Проверка базы данных:"
docker compose exec telegram-bot python3 -c "
from db import Database
try:
    db = Database('/app/data/monitor.db')
    count = db.conn.execute('SELECT COUNT(*) FROM checks').fetchone()[0]
    print(f'✅ База данных доступна: {count} записей')
except Exception as e:
    print(f'❌ Ошибка доступа к БД: {e}')
"
echo ""

echo "7. Проверка получения обновлений:"
docker compose exec telegram-bot python3 -c "
from telegram_bot import TelegramBot
from config import Config
from db import Database
import os
from dotenv import load_dotenv
load_dotenv('/app/.env')
try:
    bot = TelegramBot(os.getenv('BOT_TOKEN'), Database('/app/data/monitor.db'), Config('/app/targets.yml'))
    updates = bot.get_updates()
    print(f'Обновлений получено: {len(updates)}')
    if len(updates) > 0:
        print('✅ Бот получает обновления')
        last = updates[-1]
        if 'message' in last:
            print(f'Последнее сообщение: {last[\"message\"].get(\"text\", \"N/A\")}')
    else:
        print('⚠️ Обновлений нет (это нормально, если бот только что запущен)')
except Exception as e:
    print(f'❌ Ошибка: {e}')
    import traceback
    traceback.print_exc()
"
echo ""

echo "8. Тест формирования сообщения:"
docker compose exec telegram-bot python3 -c "
from telegram_bot import TelegramBot
from config import Config
from db import Database
import os
from dotenv import load_dotenv
load_dotenv('/app/.env')
try:
    bot = TelegramBot(os.getenv('BOT_TOKEN'), Database('/app/data/monitor.db'), Config('/app/targets.yml'))
    msg = bot.get_status_message()
    print(f'✅ Сообщение формируется: {len(msg)} символов')
    print('Первые 200 символов:')
    print(msg[:200] + '...')
except Exception as e:
    print(f'❌ Ошибка: {e}')
    import traceback
    traceback.print_exc()
"
echo ""

echo "=== КОНЕЦ ДИАГНОСТИКИ ==="

