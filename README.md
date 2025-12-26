# Local Events Newsletter Printer

A Claude Code plugin for generating curated local event newsletters with hybrid data sources. Built for **RVA Live Music & Vibes** - concerts, reggae, food events in Richmond, VA.

## Features

- **Multi-source aggregation**: Google Events, Instagram venue scraping, web calendars
- **Smart deduplication**: Fuzzy matching with weighted similarity (title 50%, venue 35%, time 15%)
- **Jinja2 templates**: Customizable newsletter formatting
- **Self-healing resilience**: Circuit breaker, retry with backoff, fallback chains, health monitoring
- **Backwards-compatible config migration** (v1 to v2)

## Quick Start

```bash
# Install and setup
cd ~/.claude/plugins
git clone https://github.com/TC407-api/local-events-newsletter-printer.git
cd local-events-newsletter-printer
pip install -e ".[dev]"

# In Claude Code
/newsletter-setup
/newsletter
```

## Commands

| Command | Description |
|---------|-------------|
| `/newsletter` | Generate newsletter for configured location |
| `/newsletter now` | Quick mode - skip confirmations |
| `/newsletter-setup` | Guided setup wizard |
| `/newsletter-sources` | Manage event sources |

## Configuration

Config: `~/.config/local-events-newsletter/config.yaml`

```yaml
version: 2
newsletter:
  name: "RVA Live Music & Vibes"
location:
  city: "Richmond"
  state: "VA"
  radius_miles: 50
categories: [music, reggae, food_drink, arts]
deduplication:
  threshold: 0.75
```

## Environment Variables

- `SERPAPI_KEY` - Google Events (100 free/month)
- `SCRAPECREATORS_KEY` - Instagram scraping (optional)

## Testing

```bash
pytest -v  # 90 passed, 0 failed
```

## Architecture

- `servers/event_mcp/` - MCP server with resilience patterns
- `commands/` - Slash commands
- `agents/` - Specialized agents (Haiku/Sonnet)
- `templates/` - Jinja2 newsletter templates
- `tests/` - 90 unit tests

## License

MIT
