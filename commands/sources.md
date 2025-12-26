---
description: Manage event sources for your newsletter
argument-hint: "[list|add|remove|test]"
allowed-tools:
  - Read
  - Write
  - Edit
  - mcp__plugin_local-events-newsletter-printer_event-aggregator__fetch_instagram
  - mcp__plugin_local-events-newsletter-printer_event-aggregator__fetch_web
  - AskUserQuestion
---

# /newsletter-sources $ARGUMENTS

Manage the event sources for your newsletter.

## Commands

### /newsletter-sources list

Show all configured sources with their status:

```
EVENT SOURCES
═══════════════════════════════════════════════════════

API Sources (always enabled)
  ✓ Google Events (SerpApi)     Status: Active

Instagram Handles (3)
  ✓ @thecamelrva                Last: 2 events found
  ✓ @thebroadberry              Last: 3 events found
  ! @defunctbar                 Error: Not found

Venue Calendars (2)
  ✓ thenationalva.com           Last: 8 events found
  ✓ thebroadberry.com           Last: 5 events found

To add a source:  /newsletter-sources add
To remove:        /newsletter-sources remove <name>
To test:          /newsletter-sources test <name>
```

### /newsletter-sources add

Interactive flow to add a new source:

```
What type of source do you want to add?

1. Instagram - Venue/promoter Instagram account
2. Website - Venue calendar page
3. Calendar - iCal/Google Calendar feed (coming soon)

Enter choice (1-3):
```

**For Instagram:**

```
Enter the Instagram handle (with or without @):
> @thecamelrva

What type of venue is this?
1. Music venue
2. Bar/restaurant
3. Art gallery
4. Event promoter
5. Other

Testing @thecamelrva...
  ✓ Account found: "The Camel"
  ✓ Found 2 potential events in recent posts

Add this source? (y/n)
```

**For Website:**

```
Enter the venue calendar URL:
> https://thenationalva.com/events

Testing...
  ✓ Page loaded
  ✓ Found 12 events

What's the venue name? (or Enter to use "The National VA")
>

Add this source? (y/n)
```

### /newsletter-sources remove <name>

```
Remove source "@thecamelrva"? (y/n)

✓ Source removed from config.
```

### /newsletter-sources test <name>

Test a specific source:

```
Testing @thecamelrva...

Results:
  Account: The Camel (@thecamelrva)
  Posts checked: 20
  Events found: 2

  1. "Live Reggae Night" - Fri Jan 17
  2. "Open Mic Monday" - Mon Jan 20

Source is working correctly.
```

## Richmond Venue Suggestions

When user runs `/newsletter-sources add`, suggest these Richmond venues:

**Music Venues:**

- @thecamelrva - The Camel (indie, reggae)
- @thebroadberry - The Broadberry (concerts)
- @thenationalva - The National (large concerts)
- @canalhallrva - Canal Hall
- @richmondjazzva - Richmond Jazz

**Bars/Restaurants with Events:**

- @legendbrewing - Legend Brewing
- @thevaborva - The Veil Brewing
- @brennersrva - Brenner Pass

**Promoters:**

- @rvashows - RVA Shows (concert listings)

## Config File Location

Sources are stored in:
`~/.config/local-events-newsletter/config.yaml`

Under the `sources:` section:

```yaml
sources:
  instagram:
    - handle: "@thecamelrva"
      name: "The Camel"
      type: "music_venue"

  web:
    - url: "https://thenationalva.com/events"
      name: "The National"
```
