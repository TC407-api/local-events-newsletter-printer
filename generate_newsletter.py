import asyncio
import os
from datetime import datetime, timedelta
from servers.event_mcp.sources.serpapi import fetch_serpapi_events
from servers.event_mcp.sources.firecrawl import fetch_firecrawl_events, FIRECRAWL_VENUE_URLS
from servers.event_mcp.dedup import deduplicate
from servers.event_mcp.template_engine import TemplateEngine


async def fetch_all_sources():
    """Fetch events from all available sources in parallel."""
    all_events = []

    # SerpApi (primary source)
    print('Fetching from SerpApi (Google Events)...')
    serpapi_events, serpapi_stats = await fetch_serpapi_events(
        location='Richmond, VA',
        date_from=datetime.now().strftime('%Y-%m-%d'),
        date_to=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    )
    print(f'  SerpApi: {serpapi_stats.count} events ({serpapi_stats.status})')
    all_events.extend(serpapi_events)

    # Firecrawl (venue calendars - if API key is set)
    if os.environ.get('FIRECRAWL_API_KEY'):
        print('Fetching from Firecrawl (venue calendars)...')
        for venue_name, url in FIRECRAWL_VENUE_URLS[:3]:  # Limit to 3 venues for now
            try:
                fc_events, fc_stats = await fetch_firecrawl_events(
                    url=url,
                    venue_name=venue_name,
                    default_city='Richmond',
                    default_state='VA'
                )
                print(f'  {venue_name}: {fc_stats.count} events ({fc_stats.status})')
                all_events.extend(fc_events)
            except Exception as e:
                print(f'  {venue_name}: Error - {str(e)}')
    else:
        print('Skipping Firecrawl (FIRECRAWL_API_KEY not set)')

    return all_events


async def main():
    print('Fetching events for Richmond, VA...')
    print('=' * 50)

    events = await fetch_all_sources()

    print('=' * 50)
    print(f'Total events before dedup: {len(events)}')

    if not events:
        print('No events found from any source')
        return
    
    result = deduplicate(events)
    print(f'After dedup: {len(result.events)} events')
    
    def fmt(e):
        return {
            'title': e.title,
            'venue': {'name': e.venue.name},
            'day': e.start_time.strftime('%A'),
            'date': e.start_time.strftime('%B %d'),
            'time': e.start_time.strftime('%I:%M %p'),
            'price': e.price or 'TBD',
            'description': e.description or '',
            'ticket_url': e.ticket_url
        }
    
    formatted = [fmt(e) for e in result.events]
    music = [fmt(e) for e in result.events if 'music' in str(e.title).lower() or 'concert' in str(e.title).lower()]
    food = [fmt(e) for e in result.events if any(w in str(e.title).lower() for w in ['food','beer','wine','brunch','drink'])]
    arts = [fmt(e) for e in result.events if any(w in str(e.title).lower() for w in ['art','comedy','theater','gallery','museum'])]
    
    engine = TemplateEngine()
    now = datetime.now()
    ctx = {
        'newsletter_name': 'RVA Live Music and Vibes',
        'date_range': f'{now.strftime("%B %d")} - {(now + timedelta(days=7)).strftime("%B %d, %Y")}',
        'intro': 'Your weekly guide to the best events in Richmond!',
        'highlights': formatted[:3],
        'music_events': music[:8],
        'food_events': food[:5],
        'arts_events': arts[:5],
        'other_events': formatted[3:10],
        'footer': 'Generated with Local Events Newsletter Printer'
    }
    
    output = engine.render('default.md', ctx)
    fname = f'newsletter_{now.strftime("%Y-%m-%d")}_REAL.md'
    with open(fname, 'w', encoding='utf-8') as f:
        f.write(output)
    print(f'Saved to: {fname}')
    print('Events found:')
    for e in result.events[:5]:
        print(f'  - {e.title} @ {e.venue.name}')

if __name__ == '__main__':
    asyncio.run(main())
