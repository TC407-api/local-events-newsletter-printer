import asyncio
import os
from datetime import datetime, timedelta
from servers.event_mcp.sources.serpapi import fetch_serpapi_events
from servers.event_mcp.dedup import deduplicate
from servers.event_mcp.template_engine import TemplateEngine

async def main():
    print('Fetching REAL events for Richmond, VA...')
    events, stats = await fetch_serpapi_events(
        location='Richmond, VA',
        date_from=datetime.now().strftime('%Y-%m-%d'),
        date_to=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    )
    print(f'Found {stats.count} events ({stats.status})')
    if stats.error_message:
        print(f'Error: {stats.error_message}')
        return
    if not events:
        print('No events returned')
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
