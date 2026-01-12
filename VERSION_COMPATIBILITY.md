# Version Compatibility Notes

## Dependencies Resolution

### Problem
Home Assistant Core already includes certain Python packages. Installing different versions causes conflicts.

### Solution
Use flexible version constraints (`>=` instead of `==`) and exclude packages already in HA Core.

## Excluded from requirements (already in HA Core)

- ✅ **pydantic** - HA Core uses 2.12.2
  - Our code is compatible with pydantic 2.10+
  - No need to specify in requirements

- ✅ **aiohttp** - Built into HA Core
  - Always available
  - No need to specify

## Included in requirements (flexible versions)

```json
"requirements": [
  "openai>=1.30.0",        // OpenAI SDK (not in HA Core)
  "fastapi>=0.100.0",      // Web framework (not in HA Core)
  "uvicorn>=0.20.0",       // ASGI server (not in HA Core)
  "aiosqlite>=0.19.0",     // Async SQLite (not in HA Core)
  "structlog>=24.1.0",     // Structured logging (not in HA Core)
  "prometheus-client>=0.19.0",  // Metrics (not in HA Core)
  "feedparser>=6.0.0"      // RSS parsing (not in HA Core)
]
```

## Not included (optional/problematic)

- ❌ **chromadb** - Complex dependencies, compilation required
  - Use `LONG_TERM_MEMORY_ENABLED=False` if not needed
  - Can be installed manually if needed

## Compatibility Testing

### Pydantic 2.12.2 Compatibility
Our code uses:
- `BaseModel` from pydantic
- Field validators
- Model serialization

All features are compatible with pydantic 2.10+ (including 2.12.2)

### Python Version
- Minimum: Python 3.11
- Tested: Python 3.13
- Home Assistant 2024.1+

## Troubleshooting

### "No solution found when resolving dependencies"
**Cause**: Requesting specific version that conflicts with HA Core

**Fix**: Use flexible versions (`>=`) instead of pinned (`==`)

### "Requirements not found"
**Cause**: Package already in HA Core but listed in requirements

**Fix**: Remove from requirements and use HA Core version

### "Module not found"
**Cause**: Package not in requirements and not in HA Core

**Fix**: Add to requirements with flexible version

---

**Last Updated**: 2026-01-12
**HA Core Tested**: 2024.1+
