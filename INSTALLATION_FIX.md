# 🔧 Исправление установки - Копирование app/

## Проблема

При ручной установке скопирована только папка `custom_components/openai_voice_proxy/`, но FastAPI серверу нужна папка `app/` с основным кодом.

## ✅ Решение

### Вариант 1: Скопировать app/ в Home Assistant (Быстрое решение)

```bash
# На Mac где находится проект
cd /Users/neosignal/Documents/Develop/PythonProjects/openai-proxy-ha

# Скопировать app/ внутрь интеграции
cp -r app custom_components/openai_voice_proxy/

# Теперь структура должна быть:
# custom_components/openai_voice_proxy/
#   ├── app/                    ← Добавлена!
#   ├── __init__.py
#   ├── config_flow.py
#   └── ...
```

### Вариант 2: Скопировать напрямую в Home Assistant

Если уже установили в HA:

```bash
# На Mac
cd /Users/neosignal/Documents/Develop/PythonProjects/openai-proxy-ha

# Скопировать app/ в HA (через scp если на другом сервере)
scp -r app/* user@ha-server:/config/custom_components/openai_voice_proxy/app/

# Или если HA локально
cp -r app /path/to/homeassistant/config/custom_components/openai_voice_proxy/
```

### Вариант 3: Без FastAPI (Упрощенный)

Если не нужен FastAPI API сервер, можно отключить его запуск:

В `/config/custom_components/openai_voice_proxy/__init__.py` закомментировать:

```python
# async def async_setup_entry(...):
#     ...
#     # Закомментировать эти строки:
#     # manager = FastAPIManager(hass, entry)
#     # await manager.start()
```

## 🚀 После копирования

1. Перезагрузите Home Assistant
2. Проверьте логи - ошибка "No module named 'app'" должна исчезнуть
3. FastAPI сервер должен запуститься

## 📊 Проверка

После перезагрузки в логах должно быть:

```
[openai_voice_proxy] Starting FastAPI server
[openai_voice_proxy] FastAPI server is ready
[openai_voice_proxy] FastAPI server started successfully
```

## ⚠️ Для будущих версий

В следующих версиях интеграции:
- `app/` будет встроена в `custom_components/openai_voice_proxy/`
- Или conversation platform будет работать без FastAPI
- Или FastAPI будет опциональным

---

**Текущее временное решение**: Скопируйте `app/` вручную
