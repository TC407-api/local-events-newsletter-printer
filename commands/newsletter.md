---
description: Generate a local event newsletter for Richmond, VA
argument-hint: "[location]" or empty for Richmond, VA
allowed-tools:
  - mcp__plugin_local-events-newsletter-printer_event-aggregator__*
  - Read
  - Write
  - Task
  - Glob
  - Grep
---

# /newsletter $ARGUMENTS

Generate a curated local event newsletter focused on live music, reggae, and food events.

## Default Location

Richmond, VA (50-100 mile radius) - covering:

- Richmond metro area
- Charlottesville
- Virginia Beach / Hampton Roads
- Fredericksburg

## Workflow

### Step 1: Check Configuration

First, check if configuration exists at `~/.config/local-events-newsletter/config.yaml`.

If NOT found:

- Tell the user: "No configuration found. Run `/newsletter-setup` first to configure your location and preferences."
- Stop here.

If found, load the config and proceed.

### Step 2: Fetch Events

Use the Task tool to spawn the `source-fetcher` agent with these parameters:

- Location from config (default: "Richmond, VA")
- Date range: Today through next 7 days
- Sources: As configured (serpapi, instagram handles, web URLs)

Show progress as sources complete:

```
Fetching events...
  ✓ Google Events: 23 events
  ✓ Instagram: 8 events
  ✓ Venue calendars: 15 events
```

### Step 3: Deduplicate & Classify

Use the Task tool to spawn the `event-curator` agent with:

- The fetched events
- Deduplication threshold: 0.75

Display summary:

```
Processing...
  Found 46 events total
  Removed 8 duplicates
  Final: 38 unique events

Categories:
  Music & Concerts: 15
  Food & Drink: 12
  Arts & Culture: 8
  Other: 3
```

Offer audit option: "View duplicate merge details? (y/n)"

### Step 4: Review Low-Confidence Events

Show events with confidence < 0.7:

```
These events need your review:

1. "Mystery Show at The Camel" - Category: Unknown
   Keep? (y/n/edit)

2. "Friday Night Special" - Category: Music?
   Keep? (y/n/edit)
```

### Step 5: Generate Newsletter

Use the Task tool to spawn the `newsletter-writer` agent with:

- The curated events
- Template from config (default: "default")
- Newsletter name from config

### Step 6: Preview & Save

Show preview of the newsletter (first 50 lines).

Ask: "Save newsletter? (y/n)"

If yes, save to:

- `./newsletter_YYYY-MM-DD.md`

Offer:

- "Copy to clipboard? (y/n)"
- "Open in browser? (y/n)"

## Quick Mode

If user runs `/newsletter now`:

- Skip review steps
- Use all events with confidence >= 0.5
- Generate and save immediately

## Example Output

```markdown
# RVA Live Music & Vibes

## January 15-22, 2025

### This Week's Highlights

🎵 **Live Reggae Night at The Camel** (Fri)
Weekly reggae showcase with local and touring artists.
8pm | $10 | The Camel

🍺 **Food Truck Friday** (Fri)
Richmond's best food trucks gather with live music.
5pm | Free | Brown's Island

...
```
