#!/bin/bash
# Скрипт для проверки и применения изменений конфигурации

echo "🔄 Проверка конфигурации..."

# Проверка синтаксиса YAML
if command -v python3 &> /dev/null; then
    python3 -c "
import yaml
import sys
try:
    with open('targets.yml', 'r') as f:
        yaml.safe_load(f)
    print('✅ Синтаксис YAML корректен')
except Exception as e:
    print(f'❌ Ошибка в YAML: {e}')
    sys.exit(1)
"
fi

# Проверка конфигурации в контейнере
echo ""
echo "📦 Проверка конфигурации в Docker контейнере..."
docker-compose exec monitor python3 -c "
from config import Config
try:
    c = Config('/app/targets.yml')
    print(f'✅ Конфигурация загружена успешно')
    print(f'📄 Количество страниц: {len(c.pages)}')
    for p in c.pages:
        print(f'   - {p.target_id}: {p.url} (каждые {p.every_sec}с)')
except Exception as e:
    print(f'❌ Ошибка загрузки: {e}')
    import traceback
    traceback.print_exc()
"

echo ""
echo "💡 Изменения применятся автоматически при следующем запуске cron (до 1 минуты)"
echo "   Или перезапустите контейнер: docker-compose restart"

