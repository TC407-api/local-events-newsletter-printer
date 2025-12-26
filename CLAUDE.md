# Local Events Newsletter Printer

Generate curated local event newsletters with hybrid API + scraping. Designed for **RVA Live Music & Vibes** - concerts, reggae, food events in Richmond, VA.

## Quick Start

```bash
# 1. First-time setup (guided wizard)
/newsletter-setup

# 2. Generate your newsletter
/newsletter

# 3. Quick generation (skip confirmations)
/newsletter now
```

## Commands

| Command                    | Description                                   |
| -------------------------- | --------------------------------------------- |
| `/newsletter`              | Generate a newsletter for configured location |
| `/newsletter now`          | Quick mode - skip confirmations               |
| `/newsletter-setup`        | Guided setup wizard                           |
| `/newsletter-sources`      | Manage event sources                          |
| `/newsletter-sources add`  | Add Instagram handle or venue URL             |
| `/newsletter-sources test` | Test all configured sources                   |

## Configuration

Config location: `~/.config/local-events-newsletter/config.yaml`

### Required Settings

- **Location**: City, state, and radius (e.g., Richmond, VA, 50 miles)
- **Categories**: Event types to include (music, food_drink, arts, etc.)

### Optional Settings

- **Instagram handles**: Venue accounts for niche events (@thecamelrva, @thebroadberry)
- **Web sources**: Venue calendar URLs
- **Deduplication threshold**: Default 0.75 (75% similarity = duplicate)

## Data Sources

### Primary: Google Events (SerpApi)

- Broad coverage of concerts, festivals, community events
- 100 free searches/month
- Set `SERPAPI_KEY` environment variable

### Secondary: Instagram Scraping

- Captures venue-specific events competitors miss
- Great for music venues, galleries, local bars
- Set `SCRAPECREATORS_KEY` environment variable (optional)

### Tertiary: Web Scraping

- Venue calendars and local aggregators
- Free, no API key required
- Configure URLs in settings

## Event Categories

| Category     | Examples                                                        |
| ------------ | --------------------------------------------------------------- |
| `music`      | Concerts, live bands, DJ sets, open mics                        |
| `reggae`     | Reggae, roots, dub, world music (priority for this newsletter!) |
| `food_drink` | Food trucks, tastings, brewery events                           |
| `arts`       | Gallery openings, theater, film                                 |
| `nightlife`  | Club nights, comedy, bar events                                 |
| `community`  | Festivals, markets, fundraisers                                 |

## Agents

This plugin uses specialized agents:

- **source-fetcher** (Haiku): Fast parallel fetching from all sources
- **event-curator** (Sonnet): Classification, deduplication, quality review
- **newsletter-writer** (Sonnet): Creative newsletter content generation

## Environment Variables

Set these in your shell profile or `.env` file:

| Variable             | Required | Purpose                      |
| -------------------- | -------- | ---------------------------- |
| `SERPAPI_KEY`        | Yes      | Google Events API access     |
| `SCRAPECREATORS_KEY` | No       | Instagram scraping           |
| `PREDICTHQ_KEY`      | No       | Premium event API (optional) |

## Deduplication

The plugin uses fuzzy matching to remove duplicate events:

- **Title similarity**: 50% weight
- **Venue match**: 35% weight
- **Time proximity**: 15% weight (2-hour window)
- **Threshold**: 75% combined similarity = duplicate

Events are merged, keeping the richest data from each source.

## Output

Newsletters are saved to: `./newsletter_YYYY-MM-DD.md`

Default template includes:

- 🔥 Don't Miss This Week (top 3 highlights)
- 🎵 Live Music & Concerts (by day)
- 🍺 Food & Drink
- 🎨 Arts & Culture
- 📅 Quick Hits

## Richmond Venue Reference

Music venues tracked by default:

- The Camel - indie, reggae, live music
- The Broadberry - concerts, touring acts
- The National - large concerts
- Canal Hall - variety

## Troubleshooting

### No events found

- Check your API key is set correctly
- Verify location in config.yaml
- Try `/newsletter-sources test`

### Too many duplicates

- Lower the dedup threshold (e.g., 0.65)
- Check if same venue has multiple names

### Missing niche events

- Add venue Instagram handles with `/newsletter-sources add`
- Add venue calendar URLs

## Cost Estimates

| Usage Level             | Monthly Cost   |
| ----------------------- | -------------- |
| Minimal (4 newsletters) | $0 (free tier) |
| Regular (weekly)        | $20-50         |
| Heavy (daily)           | $50-100        |

## File Structure

```
local-events-newsletter-printer/
├── .claude-plugin/plugin.json    # Plugin manifest
├── .mcp.json                     # MCP server config
├── CLAUDE.md                     # This file
├── commands/                     # Slash commands
├── agents/                       # Specialized agents
├── servers/event_mcp/            # MCP server (Python)
├── templates/                    # Newsletter templates
└── config/                       # Example configs
```
