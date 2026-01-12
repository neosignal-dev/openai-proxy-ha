# 🚀 Deployment Guide - OpenAI Voice Assistant Proxy

Полное руководство по установке и настройке OpenAI Voice Assistant Proxy для Home Assistant через HACS.

---

## 📋 Содержание

1. [Предварительные требования](#предварительные-требования)
2. [Установка через HACS](#установка-через-hacs)
3. [Получение API ключей](#получение-api-ключей)
4. [Настройка интеграции](#настройка-интеграции)
5. [Настройка Voice Assistant](#настройка-voice-assistant)
6. [Проверка работоспособности](#проверка-работоспособности)
7. [Расширенная настройка](#расширенная-настройка)
8. [Troubleshooting](#troubleshooting)
9. [Обновление](#обновление)

---

## Предварительные требования

### Home Assistant

- **Version**: 2024.1.0 или новее
- **Python**: 3.12+
- **HACS**: Установлен и настроен ([hacs.xyz](https://hacs.xyz))
- **Доступ**: Supervisor или Container mode

### API Keys

Вам понадобятся:

1. **OpenAI API Key** (обязательно)
   - Регистрация: [platform.openai.com](https://platform.openai.com)
   - Стоимость: ~$0.01 за 1K tokens (GPT-4)
   - Рекомендуется установить billing limit

2. **Perplexity API Key** (опционально, для web search)
   - Регистрация: [perplexity.ai](https://www.perplexity.ai)
   - Есть бесплатный tier

3. **Telegram Bot Token** (опционально, для уведомлений)
   - Создание бота: [@BotFather](https://t.me/botfather)
   - Бесплатно

### Системные требования

- **RAM**: Минимум 2GB свободной памяти
- **Storage**: ~500MB для зависимостей
- **Network**: Доступ к OpenAI API (не работает из России без VPN)

---

## Установка через HACS

### Метод 1: Через UI (рекомендуется)

1. **Откройте HACS**
   - Перейдите в Home Assistant
   - Sidebar → HACS

2. **Добавьте custom repository**
   - Нажмите три точки (⋮) в правом верхнем углу
   - Выберите **Custom repositories**
   - В поле **Repository** введите:
     ```
     https://github.com/yourusername/openai-proxy-ha
     ```
   - В поле **Category** выберите: `Integration`
   - Нажмите **Add**

3. **Установите интеграцию**
   - В HACS перейдите в раздел **Integrations**
   - Нажмите кнопку **Explore & Download Repositories**
   - Найдите **"OpenAI Voice Assistant Proxy"**
   - Нажмите на интеграцию
   - Нажмите **Download**
   - Выберите последнюю версию
   - Нажмите **Download** еще раз

4. **Перезагрузите Home Assistant**
   - Settings → System → Restart Home Assistant
   - Дождитесь полной перезагрузки (~1-2 минуты)

### Метод 2: Ручная установка

Если HACS недоступен:

```bash
# Подключитесь к серверу Home Assistant
cd /config

# Клонируйте репозиторий
git clone https://github.com/yourusername/openai-proxy-ha.git temp

# Скопируйте custom_components
cp -r temp/custom_components/openai_voice_proxy custom_components/

# Удалите временную директорию
rm -rf temp

# Перезагрузите HA
ha core restart
```

---

## Получение API ключей

### OpenAI API Key

1. **Регистрация**
   - Перейдите на [platform.openai.com](https://platform.openai.com)
   - Создайте аккаунт или войдите

2. **Создание API ключа**
   - Перейдите в [API Keys](https://platform.openai.com/api-keys)
   - Нажмите **Create new secret key**
   - Введите имя: `HomeAssistant`
   - Скопируйте ключ (показывается только раз!)
   - Формат: `sk-proj-...`

3. **Настройка billing** (важно!)
   - Перейдите в [Billing](https://platform.openai.com/account/billing)
   - Добавьте способ оплаты
   - Установите **Usage limit**: $10-20/месяц
   - Включите email уведомления

### Perplexity API Key (опционально)

1. Перейдите на [perplexity.ai](https://www.perplexity.ai)
2. Войдите в аккаунт
3. Перейдите в [API Settings](https://www.perplexity.ai/settings/api)
4. Создайте новый ключ
5. Скопируйте ключ (формат: `pplx-...`)

### Telegram Bot Token (опционально)

1. **Создание бота**
   - Откройте Telegram
   - Найдите [@BotFather](https://t.me/botfather)
   - Отправьте команду: `/newbot`
   - Следуйте инструкциям
   - Скопируйте токен (формат: `1234567890:ABCdef...`)

2. **Получение Chat ID**
   - Отправьте сообщение вашему боту
   - Откройте: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Найдите `"chat":{"id":123456789}` в JSON
   - Скопируйте число (ваш Chat ID)

---

## Настройка интеграции

### Шаг 1: Добавление интеграции

1. **Откройте Settings**
   - Home Assistant → Settings
   - Devices & Services

2. **Добавьте интеграцию**
   - Нажмите **+ Add Integration**
   - Введите в поиск: `OpenAI Voice`
   - Выберите **OpenAI Voice Assistant Proxy**

### Шаг 2: Ввод настроек

#### Обязательные параметры:

```yaml
OpenAI API Key: sk-proj-xxxxxxxxxxxxx
```

#### Опциональные параметры:

```yaml
Perplexity API Key: pplx-xxxxxxxxxxxxx
Assistant Name: Домовой
TTS Voice: alloy  # или echo, fable, onyx, nova, shimmer
Telegram Bot Token: 1234567890:ABCdef...
Telegram Chat ID: 123456789
```

#### Описание голосов:

- **alloy**: Нейтральный, сбалансированный
- **echo**: Мужской, уверенный
- **fable**: Британский акцент, выразительный
- **onyx**: Глубокий мужской
- **nova**: Женский, энергичный
- **shimmer**: Женский, мягкий

### Шаг 3: Завершение настройки

1. Нажмите **Submit**
2. Дождитесь валидации API ключа (~5-10 секунд)
3. Если всё OK, увидите сообщение: **Success!**
4. Интеграция добавлена в **Devices & Services**

---

## Настройка Voice Assistant

### Создание нового ассистента

1. **Откройте Voice Assistants**
   - Settings → Voice assistants
   - Или прямая ссылка: `http://homeassistant.local:8123/config/voice-assistants/assistant`

2. **Создайте ассистента**
   - Нажмите **+ Add Assistant**
   - Введите имя: `OpenAI Домовой`

3. **Настройте компоненты**

   **Conversation agent:**
   ```
   OpenAI Voice Proxy
   ```

   **Speech-to-Text:**
   - Рекомендуется: **Whisper** (локальный)
   - Или **faster-whisper** (быстрее)
   - Или **Google Cloud STT** (облачный)

   **Text-to-Speech:**
   ```
   OpenAI TTS (автоматически)
   ```

   **Wake word:**
   - Опционально: настройте wake word detection
   - Или используйте push-to-talk

4. **Сохраните**
   - Нажмите **Create**

### Установка Whisper (рекомендуется)

Если еще не установлен:

```bash
# Через HACS
HACS → Integrations → Explore → Whisper

# Или через Add-on
Settings → Add-ons → Add-on Store → Whisper
```

---

## Проверка работоспособности

### 1. Проверка интеграции

**Devices & Services:**
- Settings → Devices & Services
- Найдите **OpenAI Voice Assistant Proxy**
- Должен быть статус: **Configured**

**Entities:**
Проверьте что созданы entities:
```
sensor.openai_voice_proxy_health_status
sensor.openai_voice_proxy_total_requests
sensor.openai_voice_proxy_tokens_used
```

### 2. Проверка FastAPI сервера

**Logs:**
```bash
# Settings → System → Logs
# Найдите строки:
[openai_voice_proxy] FastAPI server started successfully
[openai_voice_proxy] OpenAI Voice conversation agent registered
```

**Health check (Advanced):**
```bash
# SSH в HA
curl http://127.0.0.1:8000/healthz

# Должен вернуть:
{
  "status": "healthy",
  "version": "2.0.0"
}
```

### 3. Тестовая команда

**Developer Tools → Services:**

```yaml
service: conversation.process
data:
  agent_id: conversation.openai_voice_proxy
  text: "Привет!"
```

Ожидаемый ответ в **Response**:
```json
{
  "response": {
    "speech": {
      "plain": {
        "speech": "Привет! Я Домовой, ваш голосовой ассистент..."
      }
    }
  }
}
```

### 4. Голосовая команда

1. Откройте Home Assistant на мобильном устройстве
2. Нажмите иконку микрофона
3. Скажите: **"Привет, Домовой!"**
4. Дождитесь ответа

---

## Расширенная настройка

### Options Flow

Изменить настройки после установки:

1. Settings → Devices & Services
2. Найдите **OpenAI Voice Assistant Proxy**
3. Нажмите **Configure**
4. Измените параметры:
   - Assistant Name
   - TTS Voice
   - Log Level (DEBUG для отладки)
   - Rate Limit
5. Нажмите **Submit**

### Настройка сервисов

#### 1. Web Search

Создайте автоматизацию для поиска:

```yaml
automation:
  - alias: "Daily AI news"
    trigger:
      - platform: time
        at: "09:00:00"
    action:
      - service: openai_voice_proxy.search
        data:
          query: "latest AI news today"
      - wait_for_trigger:
          - platform: event
            event_type: openai_voice_proxy_search_result
        timeout: "00:00:30"
      - service: notify.mobile_app
        data:
          message: "{{ wait.trigger.event.data.result.summary }}"
```

#### 2. Telegram уведомления

Отправка логов действий в Telegram:

```yaml
automation:
  - alias: "Notify on command"
    trigger:
      - platform: state
        entity_id: sensor.openai_voice_proxy_total_requests
    action:
      - service: openai_voice_proxy.send_telegram
        data:
          message: |
            ✅ Команда выполнена
            Время: {{ now().strftime('%H:%M:%S') }}
            Запросов всего: {{ states('sensor.openai_voice_proxy_total_requests') }}
```

### Dashboard карточка

Добавьте на dashboard:

```yaml
type: entities
title: OpenAI Voice Assistant
entities:
  - entity: sensor.openai_voice_proxy_health_status
    name: Status
  - entity: sensor.openai_voice_proxy_total_requests
    name: Total Requests
  - entity: sensor.openai_voice_proxy_tokens_used
    name: Tokens Used
show_header_toggle: false
```

### Логирование

Включить подробное логирование:

**configuration.yaml:**
```yaml
logger:
  default: info
  logs:
    custom_components.openai_voice_proxy: debug
    app.main_v2: debug
```

---

## Troubleshooting

### Проблема: Интеграция не загружается

**Симптомы:**
- Ошибка при добавлении интеграции
- "Integration not found"

**Решение:**
```bash
# 1. Проверьте установку
ls -la /config/custom_components/openai_voice_proxy/

# Должны быть файлы:
# __init__.py, manifest.json, config_flow.py, etc.

# 2. Проверьте права
chmod -R 755 /config/custom_components/openai_voice_proxy/

# 3. Очистите кэш
rm -rf /config/.storage/core.config_entries

# 4. Перезагрузите HA
ha core restart
```

### Проблема: FastAPI сервер не запускается

**Симптомы:**
- В логах: "Failed to start FastAPI server"
- Sensor entities не обновляются

**Решение:**

1. **Проверьте порт 8000:**
   ```bash
   netstat -tulpn | grep 8000
   # Если занят, измените в const.py
   ```

2. **Проверьте зависимости:**
   ```bash
   # SSH в HA
   pip3 list | grep -i fastapi
   pip3 list | grep -i uvicorn
   
   # Если отсутствуют:
   pip3 install -r /config/custom_components/openai_voice_proxy/requirements.txt
   ```

3. **Проверьте логи:**
   ```bash
   tail -f /config/logs/home-assistant.log | grep -i fastapi
   ```

### Проблема: OpenAI API ошибки

**Симптомы:**
- "Invalid API key"
- "Rate limit exceeded"
- "Insufficient quota"

**Решение:**

1. **Проверьте API ключ:**
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer sk-proj-YOUR_KEY"
   ```

2. **Проверьте billing:**
   - [platform.openai.com/account/billing](https://platform.openai.com/account/billing)
   - Убедитесь что есть положительный баланс

3. **Увеличьте rate limit:**
   - Settings → Devices & Services
   - Configure → Rate Limit = 30

### Проблема: Голос не работает

**Симптомы:**
- Текстовые команды работают
- Голосовые команды не распознаются

**Решение:**

1. **Проверьте STT:**
   ```yaml
   # Developer Tools → Services
   service: stt.whisper_speech_to_text
   data:
     # Тестовый аудио файл
   ```

2. **Проверьте микрофон:**
   - Mobile app → Settings → Permissions → Microphone
   - Разрешите доступ

3. **Проверьте Voice Assistant:**
   - Settings → Voice assistants
   - Убедитесь что выбран правильный agent

### Проблема: Высокое потребление токенов

**Симптомы:**
- Быстрый рост `sensor.openai_voice_proxy_tokens_used`
- Высокие счета от OpenAI

**Решение:**

1. **Отключите long-term память:**
   - Редактируйте `app/core/config.py`
   - `LONG_TERM_MEMORY_ENABLED = False`

2. **Уменьшите short-term память:**
   - `SHORT_TERM_MEMORY_SIZE = 10` (вместо 20)

3. **Используйте более дешевую модель:**
   - В `app/integrations/openai_client.py`
   - Замените `gpt-4` на `gpt-3.5-turbo`

---

## Обновление

### Через HACS (рекомендуется)

1. HACS → Integrations
2. Найдите **OpenAI Voice Assistant Proxy**
3. Если доступно обновление, нажмите **Update**
4. Дождитесь загрузки
5. Перезагрузите Home Assistant

### Вручную

```bash
cd /config/custom_components
rm -rf openai_voice_proxy

# Клонируйте новую версию
git clone https://github.com/yourusername/openai-proxy-ha.git temp
cp -r temp/custom_components/openai_voice_proxy ./
rm -rf temp

# Перезагрузите HA
ha core restart
```

### После обновления

1. Проверьте логи на ошибки
2. Проверьте что entities доступны
3. Протестируйте голосовые команды
4. Проверьте changelog: [GitHub Releases](https://github.com/yourusername/openai-proxy-ha/releases)

---

## Удаление

Если нужно удалить интеграцию:

1. **Удалите интеграцию:**
   - Settings → Devices & Services
   - Найдите **OpenAI Voice Assistant Proxy**
   - Нажмите три точки → **Delete**

2. **Удалите через HACS:**
   - HACS → Integrations
   - Найдите интеграцию
   - Три точки → **Remove**

3. **Очистите файлы (опционально):**
   ```bash
   rm -rf /config/custom_components/openai_voice_proxy
   rm -rf /config/data/openai_proxy.db
   rm -rf /config/chroma_data
   ```

4. **Перезагрузите HA**

---

## 🆘 Поддержка

### Документация
- [README.md](README.md) - Основная документация
- [GitHub Issues](https://github.com/yourusername/openai-proxy-ha/issues)

### Community
- [Home Assistant Community Forum](https://community.home-assistant.io)
- [Discord Channel](https://discord.gg/home-assistant)

### Контакты
- GitHub: [@yourusername](https://github.com/yourusername)
- Email: your.email@example.com

---

**Удачной установки! 🎉**
