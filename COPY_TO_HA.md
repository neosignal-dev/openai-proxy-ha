# 📋 Файлы для копирования в Home Assistant

## Исправленные файлы (обязательно скопировать):

### 1. telegram_bot.py
```bash
scp custom_components/openai_voice_proxy/app/integrations/telegram_bot.py \
    user@ha-server:/config/custom_components/openai_voice_proxy/app/integrations/
```
**Изменено**: Lazy initialization Bot для избежания blocking call

### 2. memory_v2/long_term.py
```bash
scp custom_components/openai_voice_proxy/app/services/memory_v2/long_term.py \
    user@ha-server:/config/custom_components/openai_voice_proxy/app/services/memory_v2/
```
**Изменено**: ChromaDB сделан опциональным

### 3. memory.py
```bash
scp custom_components/openai_voice_proxy/app/services/memory.py \
    user@ha-server:/config/custom_components/openai_voice_proxy/app/services/
```
**Изменено**: ChromaDB сделан опциональным

### 4. habr.py
```bash
scp custom_components/openai_voice_proxy/app/integrations/habr.py \
    user@ha-server:/config/custom_components/openai_voice_proxy/app/integrations/
```
**Изменено**: Lazy initialization httpx.AsyncClient

### 5. main_v2.py
```bash
scp custom_components/openai_voice_proxy/app/main_v2.py \
    user@ha-server:/config/custom_components/openai_voice_proxy/app/
```
**Изменено**: ChromaDB сделан опциональной зависимостью

---

## 🚀 Быстрая команда (скопировать все сразу)

```bash
# Из директории проекта
cd /Users/neosignal/Documents/Develop/PythonProjects/openai-proxy-ha

# Скопировать все исправленные файлы
scp custom_components/openai_voice_proxy/app/integrations/telegram_bot.py \
    custom_components/openai_voice_proxy/app/integrations/habr.py \
    custom_components/openai_voice_proxy/app/services/memory.py \
    custom_components/openai_voice_proxy/app/services/memory_v2/long_term.py \
    custom_components/openai_voice_proxy/app/main_v2.py \
    user@ha-server:/tmp/

# Затем на HA сервере:
mv /tmp/telegram_bot.py /config/custom_components/openai_voice_proxy/app/integrations/
mv /tmp/habr.py /config/custom_components/openai_voice_proxy/app/integrations/
mv /tmp/memory.py /config/custom_components/openai_voice_proxy/app/services/
mv /tmp/long_term.py /config/custom_components/openai_voice_proxy/app/services/memory_v2/
mv /tmp/main_v2.py /config/custom_components/openai_voice_proxy/app/
```

---

## ✅ После копирования

1. **Перезагрузите Home Assistant**:
   ```
   Settings → System → Restart Home Assistant
   ```

2. **Проверьте логи**:
   ```
   Settings → System → Logs
   ```

   Должно быть:
   ```
   ✅ [openai_voice_proxy] Starting FastAPI server
   ✅ [openai_voice_proxy] FastAPI server is ready
   ✅ [openai_voice_proxy] OpenAI Voice conversation agent registered
   ```

   Допустимые warnings:
   ```
   ⚠️  ChromaDB not available. Long-term memory disabled
   ⚠️  Telegram bot will be initialized on first use
   ```

3. **Не должно быть**:
   ```
   ❌ Detected blocking call to load_verify_locations
   ❌ No module named 'chromadb'
   ❌ Failed to import FastAPI app
   ```

---

## 🎯 Проверка работы

После перезагрузки попробуйте:

```
Settings → Voice assistants → + Add Assistant
Conversation agent: OpenAI Voice Proxy
```

Если всё работает - интеграция успешно установлена! 🎉

---

## ⚠️ Если всё еще ошибки

1. **"Failed to import FastAPI app"**
   - Убедитесь что папка `app/` полностью скопирована
   - Проверьте: `ls /config/custom_components/openai_voice_proxy/app/`

2. **"No module named 'X'"**
   - Установите зависимости: `pip3 install fastapi uvicorn openai`

3. **"Blocking call"**
   - Убедитесь что скопированы ВСЕ 5 файлов выше
