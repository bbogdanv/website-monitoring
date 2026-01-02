# Быстрый старт

## Локальное развертывание в Docker

### 1. Подготовка

```bash
# Клонируйте репозиторий (или используйте текущую директорию)
cd WebSite-Monitoring

# Создайте .env файл
cat > .env << EOF
BOT_TOKEN=your_bot_token_here
CHAT_ID=your_chat_id_here
EOF
```

### 2. Настройка конфигурации

Отредактируйте `targets.yml` - укажите ваши сайты и страницы для мониторинга.

**Важно**: На каждой странице должен быть HTML-маркер в конце HTML:
```html
<!-- MONITOR:site=example.com page=home id=abc123 -->
```

### 3. Запуск

```bash
# Сборка и запуск
docker-compose up -d

# Или используйте Makefile
make build
make up
```

### 4. Проверка работы

```bash
# Просмотр логов
docker-compose logs -f

# Или
make logs

# Проверка базы данных
docker-compose exec monitor sqlite3 /app/data/monitor.db "SELECT * FROM checks ORDER BY timestamp DESC LIMIT 5;"
```

### 5. Остановка

```bash
docker-compose down
# Или
make down
```

## Настройка CI/CD для Docker Hub

### 1. Создайте репозиторий на GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/WebSite-Monitoring.git
git push -u origin main
```

### 2. Настройте секреты в GitHub

1. Перейдите в Settings → Secrets and variables → Actions
2. Добавьте секреты:
   - `DOCKER_USERNAME` - ваш логин на Docker Hub
   - `DOCKER_PASSWORD` - токен доступа Docker Hub

   **Как получить токен Docker Hub:**
   - Зайдите на https://hub.docker.com/settings/security
   - Нажмите "New Access Token"
   - Создайте токен с правами на запись
   - Используйте его как `DOCKER_PASSWORD`

### 3. Автоматическая сборка

После настройки секретов, при каждом push в `main` или `master`:
- Образ автоматически соберется
- Будет опубликован в Docker Hub как `your-username/website-monitoring:latest`

При создании тега (например, `v1.0.0`):
- Образ будет опубликован с версионными тегами: `v1.0.0`, `v1.0`, `v1`

### 4. Использование образа из Docker Hub

```bash
docker pull your-username/website-monitoring:latest

docker run -d \
  --name mini-monitor \
  --restart unless-stopped \
  -e BOT_TOKEN=your_token \
  -e CHAT_ID=your_chat_id \
  -v $(pwd)/targets.yml:/app/targets.yml:ro \
  -v $(pwd)/data:/app/data \
  your-username/website-monitoring:latest
```

## Полезные команды

```bash
# Просмотр логов
make logs

# Перезапуск
make restart

# Очистка (удалит данные!)
make clean

# Ручной запуск проверки
docker-compose exec monitor python3 monitor.py

# Вход в контейнер
docker-compose exec monitor bash
```

## Структура данных

Все данные сохраняются в `./data/`:
- `monitor.db` - база данных SQLite
- `monitor.log` - логи работы

Эта директория монтируется как volume, поэтому данные сохраняются между перезапусками.

## Troubleshooting

### Контейнер не запускается

Проверьте логи:
```bash
docker-compose logs monitor
```

### Cron не работает

Проверьте, что cron запущен:
```bash
docker-compose exec monitor ps aux | grep cron
```

### Проблемы с правами

Если возникают проблемы с записью:
```bash
chmod -R 777 data/
```

### Тестирование без Docker

```bash
# Установите зависимости
pip3 install -r requirements.txt

# Создайте .env файл
# Запустите
python3 monitor.py
```

