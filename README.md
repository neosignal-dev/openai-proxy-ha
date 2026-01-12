# 🏠 OpenAI Voice Assistant Proxy for Home Assistant

> **Production-ready voice-first LLM assistant as HACS custom component**

[![Version](https://img.shields.io/badge/version-2.0.0-blue)](https://github.com/yourusername/openai-proxy-ha)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

---

## ⚡ Quick Overview

**OpenAI Voice Assistant Proxy** - это голосовой ассистент для Home Assistant, работающий на базе OpenAI Realtime API. Устанавливается через HACS как custom component и интегрируется с conversation platform.

### 🌟 Ключевые возможности

- 🎙️ **OpenAI Realtime API** — real-time голосовое взаимодействие (<500ms latency)
- 🧠 **Policy-Based Memory** — умная память с автоматической классификацией
- 🔍 **Smart Web Search** — интеграция с Perplexity для актуальных данных
- 🏗️ **Modular Pipeline** — продуманная архитектура обработки команд
- 🔐 **Safety First** — подтверждения, audit log, rate limiting
- 📊 **Full Observability** — метрики, health checks, structured logging
- 🎯 **Native HA Integration** — conversation agent, services, sensors

---

## 📦 Установка через HACS

### Шаг 1: Добавить custom repository

1. Откройте **HACS** в Home Assistant
2. Нажмите на три точки (⋮) в правом верхнем углу
3. Выберите **Custom repositories**
4. Добавьте:
   - **Repository**: `https://github.com/yourusername/openai-proxy-ha`
   - **Category**: `Integration`
5. Нажмите **Add**

### Шаг 2: Установить интеграцию

1. В HACS найдите **"OpenAI Voice Assistant Proxy"**
2. Нажмите **Download**
3. Перезагрузите Home Assistant

**Примечание**: Зависимости установятся автоматически при первом добавлении интеграции. Это может занять несколько минут.

### Шаг 3: Настроить интеграцию

1. Перейдите в **Settings** → **Devices & Services**
2. Нажмите **+ Add Integration**
3. Найдите **"OpenAI Voice Assistant Proxy"**
4. Введите настройки:
   - **OpenAI API Key** (обязательно)
   - **Perplexity API Key** (опционально)
   - **Assistant Name** (по умолчанию: "Домовой")
   - **TTS Voice** (alloy, echo, fable, onyx, nova, shimmer)
   - **Telegram Bot Token** (опционально)
   - **Telegram Chat ID** (опционально)

### Шаг 4: Настроить Voice Assistant

1. Перейдите в **Settings** → **Voice assistants**
2. Нажмите **+ Add Assistant**
3. Выберите **Conversation agent**: `OpenAI Voice Proxy`
4. Настройте Speech-to-Text (например, Whisper)
5. Сохраните

---

## 🎯 Использование

### Голосовое управление

После настройки Voice Assistant можно использовать голосовые команды:

```
"Привет, Домовой!"
"Включи свет в гостиной"
"Какая погода сегодня?"
"Найди последние новости по искусственному интеллекту"
"Создай автоматизацию: включать свет когда я прихожу домой"
```

### Сервисы Home Assistant

Интеграция предоставляет несколько сервисов:

#### 1. Web Search (Perplexity)

```yaml
service: openai_voice_proxy.search
data:
  query: "latest AI news"
```

#### 2. Send Telegram

```yaml
service: openai_voice_proxy.send_telegram
data:
  message: "Hello from Home Assistant!"
  parse_mode: "Markdown"
```

#### 3. Search Habr

```yaml
service: openai_voice_proxy.search_habr
data:
  query: "Python asyncio"
  tags: "python,backend"
  days: 30
```

#### 4. Get HA Context

```yaml
service: openai_voice_proxy.get_context
```

### Sensors

Интеграция создает несколько sensor entities для мониторинга:

- `sensor.openai_voice_proxy_health_status` - статус здоровья
- `sensor.openai_voice_proxy_total_requests` - количество запросов
- `sensor.openai_voice_proxy_tokens_used` - использованные токены

---

## 🛠️ Архитектура

Проект использует гибридный подход:

```
Home Assistant
  └── Custom Component (openai_voice_proxy)
      ├── Conversation Agent (голосовой интерфейс)
      ├── Config Flow (UI настройка)
      ├── Services (API обёртки)
      ├── Sensors (мониторинг)
      └── FastAPI Manager
          └── FastAPI Server (внутренний процесс)
              ├── OpenAI Integration
              ├── Perplexity Search
              ├── Memory System (SQLite + ChromaDB)
              ├── Command Pipeline
              └── Monitoring (Prometheus)
```

### Компоненты

#### Conversation Agent
Реализует `conversation.AbstractConversationAgent` для нативной интеграции с Voice Assistant.

#### FastAPI Manager
Управляет запуском и взаимодействием с FastAPI сервером внутри Home Assistant.

#### Command Pipeline
- **Intent Analyzer** - анализ намерений пользователя
- **Context Resolver** - разрешение контекста (areas, entities)
- **Planner** - планирование действий
- **Executor** - выполнение команд в HA
- **Response Composer** - формирование ответа

#### Memory System
- **Short-term**: SQLite для последних 20 сообщений
- **Long-term**: ChromaDB для семантического поиска

---

## 📊 Возможности

### ✅ Голосовое управление
- OpenAI Realtime API с WebSocket
- 6 голосов TTS (alloy, echo, fable, onyx, nova, shimmer)
- Streaming audio responses
- Barge-in поддержка

### ✅ LLM-планирование
- Преобразование команд в структурированные действия
- Валидация entity_id
- Подтверждение опасных действий
- Контекстное понимание

### ✅ Память и контекст
- Short-term память (последние диалоги)
- Long-term память (семантический поиск)
- Пользовательские правила и предпочтения
- Построение полного контекста для LLM

### ✅ Интеграции
- **OpenAI**: TTS, Realtime API, Embeddings
- **Perplexity**: Умный веб-поиск с актуальностью
- **Habr.com**: Поиск статей (RSS + HTML)
- **Telegram**: Уведомления и логи

### ✅ Мониторинг
- Prometheus metrics (15+ метрик)
- Structured logging (JSON)
- Health checks
- Rate limiting

---

## 🔐 Безопасность

### Rate Limiting
- Общий: 60 запросов/минуту
- Perplexity: 20 запросов/минуту
- Habr: 10 запросов/минуту

### Service Allowlist
Настраиваемый список разрешённых HA сервисов (по умолчанию: `light.*`, `switch.*`, `cover.*`, `climate.*`, `scene.*`, `script.*`)

### Подтверждение действий
Автоматическое подтверждение для опасных сервисов:
- `alarm_control_panel.*`
- `lock.*`
- `garage_door.*`

### Audit Log
Все действия логируются в базу данных с user_id, timestamp, intent, actions, success/error.

---

## 📝 Требования

### Home Assistant
- Home Assistant 2024.1+
- Python 3.12+

### API Keys
- **OpenAI API Key** (обязательно) - [platform.openai.com](https://platform.openai.com)
- **Perplexity API Key** (опционально) - [perplexity.ai](https://www.perplexity.ai)
- **Telegram Bot Token** (опционально) - [@BotFather](https://t.me/botfather)

### Зависимости
Все зависимости устанавливаются автоматически через HACS:
- fastapi
- uvicorn
- openai
- aiohttp
- pydantic
- chromadb
- structlog
- prometheus-client
- aiosqlite
- feedparser

---

## 🔧 Расширенная настройка

### Options Flow

После установки можно изменить настройки через **Configure**:
- Assistant Name
- TTS Voice
- Log Level (DEBUG, INFO, WARNING, ERROR)
- Rate Limit (requests per minute)

### Автоматизации

Можно использовать events для автоматизаций:

```yaml
automation:
  - alias: "Search completed"
    trigger:
      - platform: event
        event_type: openai_voice_proxy_search_result
    action:
      - service: notify.mobile_app
        data:
          message: "Search completed: {{ trigger.event.data.query }}"
```

---

## 📚 Дополнительная информация

- **Подробная документация**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Issues**: [GitHub Issues](https://github.com/yourusername/openai-proxy-ha/issues)
- **License**: MIT

---

## 🙏 Благодарности

- Home Assistant community
- OpenAI team
- Perplexity AI

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

---

**Made with ❤️ for Home Assistant community**
