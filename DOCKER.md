# Docker развертывание

## Быстрый старт

1. Создайте `.env` файл:
```bash
BOT_TOKEN=your_bot_token
CHAT_ID=your_chat_id
```

2. Настройте `targets.yml`

3. Запустите:
```bash
docker-compose up -d
```

4. Проверьте логи:
```bash
docker-compose logs -f
```

## Структура данных

Все данные сохраняются в директории `./data`:
- `monitor.db` - база данных SQLite
- `monitor.log` - логи работы

## Обновление

### Обновление конфигурации

Просто отредактируйте `targets.yml` и перезапустите:
```bash
docker-compose restart
```

### Обновление кода

1. Остановите контейнер:
```bash
docker-compose down
```

2. Пересоберите образ:
```bash
docker-compose build
```

3. Запустите снова:
```bash
docker-compose up -d
```

## Полезные команды

```bash
# Просмотр логов
docker-compose logs -f monitor

# Выполнение команды в контейнере
docker-compose exec monitor bash

# Просмотр базы данных
docker-compose exec monitor sqlite3 /app/data/monitor.db "SELECT * FROM checks ORDER BY timestamp DESC LIMIT 10;"

# Остановка
docker-compose down

# Остановка с удалением volumes (удалит данные!)
docker-compose down -v
```

## Troubleshooting

### Cron не работает

Проверьте логи:
```bash
docker-compose logs monitor
```

Проверьте, что cron запущен:
```bash
docker-compose exec monitor ps aux | grep cron
```

### Проблемы с правами доступа

Если возникают проблемы с записью в `data/`, проверьте права:
```bash
chmod -R 777 data/
```

Или запустите контейнер с правильным пользователем (добавьте в docker-compose.yml):
```yaml
user: "${UID:-1000}:${GID:-1000}"
```

### Проверка работы вручную

Запустите проверку вручную внутри контейнера:
```bash
docker-compose exec monitor python3 monitor.py
```

## Production развертывание

Для production рекомендуется:

1. Использовать готовый образ из Docker Hub
2. Настроить мониторинг контейнера
3. Настроить ротацию логов
4. Использовать secrets management для токенов

Пример запуска production образа:

```bash
docker run -d \
  --name mini-monitor \
  --restart unless-stopped \
  -e BOT_TOKEN="${BOT_TOKEN}" \
  -e CHAT_ID="${CHAT_ID}" \
  -v /opt/monitor/targets.yml:/app/targets.yml:ro \
  -v /opt/monitor/data:/app/data \
  your-username/website-monitoring:latest
```

