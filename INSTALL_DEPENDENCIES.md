# Установка зависимостей

## ⚠️ ВАЖНО

Home Assistant требует ручной установки зависимостей для этой интеграции.

## Способ 1: Через SSH (рекомендуется)

1. **Подключитесь к Home Assistant через SSH**

2. **Установите зависимости:**

```bash
# Войдите в контейнер HA (если используете Container/Supervised)
docker exec -it homeassistant bash

# Или подключитесь через SSH Add-on

# Установите зависимости
pip3 install \
  fastapi==0.115.6 \
  "uvicorn[standard]==0.34.0" \
  openai==1.59.7 \
  aiohttp==3.11.11 \
  pydantic==2.10.5 \
  structlog==24.4.0 \
  prometheus-client==0.21.1 \
  aiosqlite==0.20.0 \
  feedparser==6.0.11

# ChromaDB (опционально, для long-term памяти)
# Может требовать дополнительных системных зависимостей
pip3 install chromadb==0.5.23
```

3. **Перезагрузите Home Assistant**

```bash
ha core restart
```

## Способ 2: Через Terminal & SSH Add-on

1. Установите **Terminal & SSH** add-on из магазина add-ons

2. Откройте Terminal в веб-интерфейсе HA

3. Выполните команды:

```bash
pip3 install \
  fastapi==0.115.6 \
  "uvicorn[standard]==0.34.0" \
  openai==1.59.7 \
  aiohttp==3.11.11 \
  pydantic==2.10.5 \
  structlog==24.4.0 \
  prometheus-client==0.21.1 \
  aiosqlite==0.20.0 \
  feedparser==6.0.11
```

4. Перезагрузите HA через Settings → System → Restart

## Способ 3: Через configuration.yaml

Добавьте в `configuration.yaml`:

```yaml
shell_command:
  install_openai_deps: >
    pip3 install fastapi==0.115.6 uvicorn[standard]==0.34.0 openai==1.59.7 
    aiohttp==3.11.11 pydantic==2.10.5 structlog==24.4.0 
    prometheus-client==0.21.1 aiosqlite==0.20.0 feedparser==6.0.11
```

Затем вызовите через Developer Tools → Services:

```yaml
service: shell_command.install_openai_deps
```

## Проверка установки

Проверьте что зависимости установлены:

```bash
pip3 list | grep -E "fastapi|openai|uvicorn"
```

Должно показать:
```
fastapi         0.115.6
openai          1.59.7
uvicorn         0.34.0
```

## Troubleshooting

### Ошибка: "No module named 'fastapi'"

Зависимости не установлены. Повторите установку.

### Ошибка: "pip3: command not found"

На некоторых системах используйте `pip` вместо `pip3`:

```bash
pip install fastapi==0.115.6 ...
```

### ChromaDB не устанавливается

ChromaDB опционален и может требовать компиляции. Если не удается установить:

1. Пропустите ChromaDB
2. В `app/core/config.py` установите:
   ```python
   LONG_TERM_MEMORY_ENABLED = False
   ```

## После установки

1. Добавьте интеграцию через UI:
   - Settings → Devices & Services → Add Integration
   - Найдите "OpenAI Voice Assistant Proxy"

2. Введите API ключи

3. Настройте Voice Assistant

---

**Примечание**: В будущих версиях планируется автоматическая установка зависимостей.
