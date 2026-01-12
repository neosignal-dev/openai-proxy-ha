# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-01-12

### 🎉 Major Release - HACS Integration

Complete rewrite as Home Assistant custom component installable via HACS.

### Added
- **HACS Integration**: Custom component structure for easy installation
- **Config Flow**: UI-based configuration through Settings → Devices & Services
- **Conversation Platform**: Native integration with Home Assistant Voice Assistant
- **Sensor Entities**: 
  - Health Status sensor
  - Total Requests counter
  - Tokens Used counter
- **Services**: 
  - `search` - Web search via Perplexity
  - `send_telegram` - Send Telegram messages
  - `search_habr` - Search Habr.com articles
  - `get_context` - Get full HA context
- **Translations**: English and Russian UI translations
- **FastAPI Manager**: Embedded FastAPI server management within HA
- **Options Flow**: Configure settings after installation

### Changed
- **Architecture**: From standalone server to hybrid HACS component
- **Configuration**: From `.env` file to UI-based config flow
- **Installation**: From Docker to HACS (or manual copy)
- **Documentation**: Complete rewrite with README.md and DEPLOYMENT.md

### Removed
- Docker Compose setup (use HACS instead)
- Home Assistant Add-on (superseded by custom component)
- Standalone server mode (integrated into HA)
- Multiple documentation files (consolidated to README + DEPLOYMENT)
- `env.example` (replaced by config flow)

### Migration from 1.x

If upgrading from standalone version:

1. **Backup your data**:
   ```bash
   cp -r data/ data.backup/
   cp -r chroma_data/ chroma_data.backup/
   ```

2. **Stop old Docker container**:
   ```bash
   docker-compose down
   ```

3. **Install via HACS** (see DEPLOYMENT.md)

4. **Migrate data** (optional):
   ```bash
   # Copy databases to new location
   cp data.backup/openai_proxy.db /config/data/
   cp -r chroma_data.backup/* /config/chroma_data/
   ```

5. **Configure integration** with your API keys

## [1.0.0] - 2025-01-01

### Initial Release

- OpenAI Realtime API integration
- FastAPI REST API server
- Memory system (SQLite + ChromaDB)
- Home Assistant integration via REST
- Perplexity web search
- Habr.com search
- Telegram notifications
- Prometheus metrics
- Docker deployment
- Home Assistant Add-on

---

## Upcoming Features

### [2.1.0] - Planned
- [ ] Multi-user support with user profiles
- [ ] Custom wake word detection
- [ ] Voice activity detection improvements
- [ ] Advanced context management
- [ ] Integration with more search engines

### [2.2.0] - Planned
- [ ] Support for other LLM providers (Anthropic, Google)
- [ ] Plugin system for custom integrations
- [ ] Visual dashboard in HA
- [ ] Advanced analytics

---

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/openai-proxy-ha/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/openai-proxy-ha/discussions)
- **Documentation**: [README.md](README.md) | [DEPLOYMENT.md](DEPLOYMENT.md)
