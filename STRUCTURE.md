# Project Structure

```
openai-proxy-ha/
├── custom_components/               # Home Assistant Custom Component
│   └── openai_voice_proxy/         # Main integration directory
│       ├── __init__.py              # Component setup and entry point
│       ├── manifest.json            # Integration metadata
│       ├── config_flow.py           # UI configuration flow
│       ├── const.py                 # Constants and configuration
│       ├── conversation.py          # Conversation agent platform
│       ├── sensor.py                # Sensor entities
│       ├── fastapi_manager.py       # FastAPI server manager
│       ├── services.yaml            # Service definitions
│       ├── strings.json             # UI strings
│       └── translations/            # Localization files
│           ├── en.json              # English translations
│           └── ru.json              # Russian translations
│
├── app/                             # FastAPI Application
│   ├── main_v2.py                   # Main FastAPI app
│   ├── main.py                      # Legacy main (v1)
│   │
│   ├── agents/                      # LLM Agents
│   │   ├── base.py                  # Base agent class
│   │   ├── realtime_voice_agent.py  # Real-time voice agent
│   │   └── text_agent.py            # Text-based agent
│   │
│   ├── api/                         # API Endpoints
│   │   ├── routes_v2.py             # V2 routes
│   │   ├── routes.py                # V1 routes
│   │   └── schemas.py               # Pydantic schemas
│   │
│   ├── core/                        # Core Components
│   │   ├── config.py                # Configuration management
│   │   ├── database.py              # Database setup
│   │   ├── logging.py               # Logging configuration
│   │   └── rate_limiter.py          # Rate limiting
│   │
│   ├── integrations/                # External Integrations
│   │   ├── homeassistant.py         # Home Assistant client
│   │   ├── openai_client.py         # OpenAI API client
│   │   ├── perplexity.py            # Perplexity search
│   │   ├── habr.py                  # Habr.com search
│   │   └── telegram_bot.py          # Telegram bot
│   │
│   └── services/                    # Business Logic Services
│       ├── command_processor.py     # Command processing
│       ├── monitoring.py            # Metrics and monitoring
│       ├── observability.py         # Observability utilities
│       │
│       ├── memory_v2/               # Memory Management V2
│       │   ├── manager.py           # Memory manager
│       │   ├── short_term.py        # Short-term memory (SQLite)
│       │   ├── long_term.py         # Long-term memory (ChromaDB)
│       │   ├── embeddings.py        # Embeddings generation
│       │   └── policy.py            # Memory policies
│       │
│       ├── pipeline/                # Command Processing Pipeline
│       │   ├── orchestrator.py      # Pipeline orchestrator
│       │   ├── intent_analyzer.py   # Intent analysis
│       │   ├── context_resolver.py  # Context resolution
│       │   ├── planner.py           # Action planning
│       │   ├── executor.py          # Action execution
│       │   └── response_composer.py # Response composition
│       │
│       ├── search/                  # Search Services
│       │   ├── perplexity_enhanced.py # Enhanced Perplexity search
│       │   └── policies.py          # Search policies
│       │
│       └── tts/                     # Text-to-Speech
│           ├── base.py              # Base TTS interface
│           └── openai_tts.py        # OpenAI TTS implementation
│
├── migrations/                      # Database Migrations
│   └── add_memory_v2_fields.sql    # V2 memory fields migration
│
├── scripts/                         # Utility Scripts
│   └── migrate_db.py               # Database migration script
│
├── tests/                           # Test Suite
│   ├── conftest.py                 # Test configuration
│   ├── test_memory_policies.py     # Memory policy tests
│   ├── test_pipeline.py            # Pipeline tests
│   ├── test_search_policies.py     # Search policy tests
│   └── test_tts.py                 # TTS tests
│
├── README.md                        # Main documentation
├── DEPLOYMENT.md                    # Deployment guide
├── CHANGELOG.md                     # Version history
├── STRUCTURE.md                     # This file
├── LICENSE                          # MIT License
│
├── hacs.json                        # HACS integration metadata
├── info.md                          # HACS info page
├── requirements.txt                 # Python dependencies
├── pyproject.toml                   # Python project configuration
├── pytest.ini                       # Pytest configuration
└── .gitignore                       # Git ignore rules
```

## Key Components

### 1. Custom Component (`custom_components/openai_voice_proxy/`)

The Home Assistant integration that:
- Provides UI configuration through config flow
- Manages FastAPI server lifecycle
- Implements conversation agent platform
- Creates sensor entities for monitoring
- Registers services for automation

### 2. FastAPI Application (`app/`)

The backend server that runs inside Home Assistant:
- Processes voice and text commands
- Manages memory (short-term and long-term)
- Integrates with external services
- Provides REST API endpoints
- Handles WebSocket for real-time voice

### 3. Command Pipeline (`app/services/pipeline/`)

Six-stage processing pipeline:
1. **Intent Analyzer** - Understands user intent
2. **Context Resolver** - Resolves entities and areas
3. **Planner** - Plans actions to execute
4. **Executor** - Executes actions in HA
5. **Response Composer** - Creates natural response
6. **Orchestrator** - Manages the pipeline

### 4. Memory System (`app/services/memory_v2/`)

Two-tier memory architecture:
- **Short-term**: Last 20 messages in SQLite
- **Long-term**: Semantic search in ChromaDB
- **Policies**: Automatic importance classification

### 5. Integrations (`app/integrations/`)

External service integrations:
- **OpenAI**: Realtime API, TTS, Embeddings
- **Perplexity**: Web search with recency
- **Habr.com**: Technical articles search
- **Telegram**: Notifications and logs
- **Home Assistant**: REST API client

## Data Flow

```
User Voice Command
    ↓
Home Assistant Conversation Agent (conversation.py)
    ↓
FastAPI Manager (fastapi_manager.py)
    ↓
FastAPI Server (main_v2.py)
    ↓
Command Pipeline (pipeline/)
    ├→ Intent Analyzer
    ├→ Context Resolver
    ├→ Planner
    ├→ Executor (integrations/homeassistant.py)
    └→ Response Composer
    ↓
OpenAI TTS (services/tts/)
    ↓
Voice Response to User
```

## File Naming Conventions

- `__init__.py` - Package initialization
- `*_v2.py` - Version 2 implementations
- `*.py` - Python modules
- `*.yaml` - YAML configuration files
- `*.json` - JSON data files
- `*.md` - Markdown documentation
- `*.sql` - SQL migration files

## Import Paths

From Home Assistant:
```python
from custom_components.openai_voice_proxy import DOMAIN
from custom_components.openai_voice_proxy.const import *
```

From FastAPI app:
```python
from app.core.config import settings
from app.integrations.homeassistant import ha_client
from app.services.pipeline.orchestrator import CommandOrchestrator
```

## Configuration Locations

- **HA Config**: Through UI (Settings → Devices & Services)
- **Environment**: Set by `fastapi_manager.py` from config entry
- **Code Config**: `app/core/config.py` (loads from env vars)
- **Database**: `/config/data/openai_proxy.db`
- **Vector DB**: `/config/chroma_data/`
- **Logs**: Home Assistant logs system

## Development Workflow

1. **Local Development**:
   ```bash
   # Test FastAPI app
   cd app
   python -m main_v2
   ```

2. **HA Testing**:
   ```bash
   # Copy to HA
   cp -r custom_components/openai_voice_proxy /config/custom_components/
   
   # Restart HA
   ha core restart
   ```

3. **Debugging**:
   ```yaml
   # configuration.yaml
   logger:
     logs:
       custom_components.openai_voice_proxy: debug
   ```

## Dependencies

See `requirements.txt` for full list. Key dependencies:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `openai` - OpenAI SDK
- `chromadb` - Vector database
- `aiohttp` - Async HTTP client
- `structlog` - Structured logging
- `pydantic` - Data validation

## Next Steps

1. Read [README.md](README.md) for feature overview
2. Follow [DEPLOYMENT.md](DEPLOYMENT.md) for installation
3. Check [CHANGELOG.md](CHANGELOG.md) for version history
4. Explore `app/` for backend implementation
5. Study `custom_components/` for HA integration
