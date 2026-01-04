# Инструкция по обновлению кода

## Процесс обновления

### 1. Локальная разработка

```bash
# 1. Внесите изменения в код
# ... редактируйте файлы ...

# 2. Протестируйте локально
docker-compose down
docker-compose build
docker-compose up -d

# 3. Проверьте работу
docker-compose logs -f

# 4. Закоммитьте изменения
git add .
git commit -m "Описание изменений"
git push origin main
```

### 2. Автоматическая сборка образа

После push в GitHub:
- GitHub Actions автоматически запустится
- Соберет Docker образ
- Запушит образ в Docker Hub как `finallot/website-monitoring:latest`
- Обычно занимает 2-5 минут

Проверить статус сборки:
```
https://github.com/bbogdanv/website-monitoring/actions
```

### 3. Обновление на продакшен сервере

#### Вариант A: Обновление только образа (рекомендуется)

```bash
cd /opt/website-monitoring

# 1. Обновить образ из Docker Hub
docker compose pull

# 2. Перезапустить контейнеры
docker compose down
docker compose up -d

# 3. Проверить статус
docker compose ps

# 4. Проверить логи
docker compose logs -f
```

#### Вариант B: Обновление конфигурации (targets.yml, .env)

```bash
cd /opt/website-monitoring

# 1. Обновить конфигурацию
nano targets.yml  # или nano .env

# 2. Перезапустить контейнеры (конфигурация загружается при каждом запуске)
docker compose restart

# 3. Проверить логи
docker compose logs -f
```

#### Вариант C: Обновление docker-compose.yml

```bash
cd /opt/website-monitoring

# 1. Скачать актуальный docker-compose.yml
wget https://raw.githubusercontent.com/bbogdanv/website-monitoring/main/docker-compose.prod.yml -O docker-compose.yml

# 2. Обновить образ и перезапустить
docker compose pull
docker compose down
docker compose up -d

# 3. Проверить статус
docker compose ps
```

## Типы обновлений

### Обновление кода приложения (Python файлы)

1. Внесите изменения в код
2. Закоммитьте и запушьте в GitHub
3. Дождитесь завершения GitHub Actions (2-5 минут)
4. На сервере: `docker compose pull && docker compose down && docker compose up -d`

### Обновление конфигурации (targets.yml)

1. Отредактируйте `targets.yml` на сервере
2. Перезапустите контейнеры: `docker compose restart`
3. Конфигурация загружается при каждом запуске, пересборка не нужна

### Обновление переменных окружения (.env)

1. Отредактируйте `.env` на сервере
2. Перезапустите контейнеры: `docker compose restart`
3. Переменные загружаются при каждом запуске

### Обновление docker-compose.yml

1. Скачайте актуальный файл из GitHub или обновите вручную
2. Перезапустите: `docker compose down && docker compose up -d`

## Проверка после обновления

```bash
# Проверить статус контейнеров
docker compose ps

# Проверить логи мониторинга
docker compose logs website-monitoring --tail=20

# Проверить логи бота
docker compose logs telegram-bot --tail=20

# Проверить работу мониторинга
docker compose exec website-monitoring python3 monitor.py

# Проверить работу бота
docker compose exec telegram-bot python3 -c "
from telegram_bot import TelegramBot
from config import Config
from db import Database
import os
from dotenv import load_dotenv
load_dotenv('/app/.env')
bot = TelegramBot(os.getenv('BOT_TOKEN'), Database('/app/data/monitor.db'), Config('/app/targets.yml'))
print('Бот инициализирован успешно')
"
```

## Откат к предыдущей версии

Если что-то пошло не так:

```bash
# 1. Посмотреть доступные теги
docker images | grep finallot/website-monitoring

# 2. Использовать конкретный тег (если есть)
# Или откатить через git и пересобрать

# 3. Или использовать предыдущий образ из кеша
docker compose down
docker compose up -d
```

## Автоматическое обновление (опционально)

Создайте скрипт для автоматического обновления:

```bash
#!/bin/bash
# /opt/website-monitoring/update.sh

cd /opt/website-monitoring
docker compose pull
docker compose down
docker compose up -d
docker system prune -f

echo "Обновление завершено: $(date)"
```

Добавьте в cron для автоматического обновления (например, раз в неделю):
```bash
0 3 * * 1 /opt/website-monitoring/update.sh >> /opt/website-monitoring/update.log 2>&1
```

