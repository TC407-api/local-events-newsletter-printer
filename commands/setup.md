---
description: Set up your local event newsletter configuration
allowed-tools:
  - Read
  - Write
  - mcp__plugin_local-events-newsletter-printer_event-aggregator__get_location
  - AskUserQuestion
---

# /newsletter-setup

Interactive setup wizard for first-time configuration.

## Overview

This creates your newsletter configuration at:
`~/.config/local-events-newsletter/config.yaml`

## Step 1: Location

Ask the user:

```
What area should your newsletter cover?

Examples:
  - "Richmond, VA"
  - "Richmond, VA (100 mile radius)"
  - "Virginia Beach, VA"

Enter location:
```

Use the `get_location` MCP tool to auto-detect if user just presses Enter.

Validate the location is in the Richmond/Virginia area (or accept any US location).

## Step 2: Newsletter Focus

Ask using AskUserQuestion:

```
What types of events should your newsletter focus on?
```

Options (multi-select):

- Music & Concerts (live music, DJ sets, concerts)
- Reggae & Roots (reggae, dub, world music)
- Food & Drink (tastings, pop-ups, food trucks)
- Arts & Culture (galleries, theater, comedy)
- Nightlife (clubs, bar events, late night)
- Community (festivals, markets, meetups)

Default: Music & Concerts, Reggae & Roots, Food & Drink

## Step 3: Newsletter Name

Ask:

```
What should your newsletter be called?

Examples:
  - "RVA Live Music & Vibes"
  - "Richmond Weekend Events"
  - "The RVA Scene"

Enter name (or press Enter for "RVA Live Music & Vibes"):
```

## Step 4: Local Sources (Optional)

Ask:

```
Add Instagram handles for venues you want to track?

This captures events that only appear on Instagram.
Enter handles separated by commas, or 'skip':

Examples: @thecamelrva, @thebroadberry, @thenationalva
```

Provide Richmond music venue suggestions:

- @thecamelrva (The Camel)
- @thebroadberry (The Broadberry)
- @thenationalva (The National)
- @canalhallrva (Canal Hall)

## Step 5: API Keys

Check if API keys exist in environment or `~/.config/local-events-newsletter/credentials.yaml`.

If missing, explain:

```
To fetch events, you'll need at least one API key:

Required (choose one):
  - SERPAPI_KEY: Google Events ($0 for 100/month, $50/month for 5000)
    Get it: https://serpapi.com/

Optional:
  - SCRAPECREATORS_KEY: Instagram scraping (~$20/month)
    Get it: https://scrapecreators.com/

Add keys to your environment or I'll create a credentials file.
```

## Step 6: Save Configuration

Create the config directory and files:

```yaml
# ~/.config/local-events-newsletter/config.yaml
version: 2

newsletter:
  name: "RVA Live Music & Vibes"

location:
  city: "Richmond"
  state: "VA"
  radius_miles: 50

categories:
  - music
  - reggae
  - food_drink

sources:
  instagram:
    - handle: "@thecamelrva"
      name: "The Camel"
    - handle: "@thebroadberry"
      name: "The Broadberry"

  web: []

deduplication:
  threshold: 0.75

output:
  format: markdown
  template: default
```

## Step 7: Test Fetch

Ask: "Would you like me to fetch some events now to test the setup? (y/n)"

If yes:

- Run a quick fetch (SerpApi only, limit 10)
- Show results
- Confirm working

## Completion

```
Setup complete!

Your newsletter "RVA Live Music & Vibes" is configured for:
  📍 Richmond, VA (50 mile radius)
  🎵 Music, Reggae, Food events
  📱 Tracking 2 Instagram venues

Run /newsletter to generate your first newsletter!
```
