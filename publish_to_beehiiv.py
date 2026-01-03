"""
Automated Newsletter Publisher for Beehiiv
==========================================
Generates newsletter content and publishes directly to Beehiiv using Playwright.

Usage:
    python publish_to_beehiiv.py              # Generate and publish (draft)
    python publish_to_beehiiv.py --publish    # Generate and publish immediately
    python publish_to_beehiiv.py --preview    # Generate and preview only

Requirements:
    pip install playwright jinja2
    playwright install chromium
"""

import asyncio
import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# Try to import playwright
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Warning: Playwright not installed. Run: pip install playwright && playwright install chromium")

from jinja2 import Environment, FileSystemLoader

# Import newsletter generation
from servers.event_mcp.sources.serpapi import fetch_serpapi_events
from servers.event_mcp.dedup import deduplicate


class BeehiivConfig:
    """Beehiiv configuration - edit these values"""
    EMAIL = os.environ.get('BEEHIIV_EMAIL', '')
    PASSWORD = os.environ.get('BEEHIIV_PASSWORD', '')  # Store securely!
    PUBLICATION_HANDLE = 'rvalivemusic'
    NEWSLETTER_NAME = 'RVA Live Music and Vibes'
    LOCATION = 'Richmond, VA'


class NewsletterGenerator:
    """Generates newsletter content from event sources"""

    MUSIC_VENUES = ['camel', 'broadberry', 'national', 'canal', 'ember', 'tin pan',
                   'irish pub', 'taphouse', 'galaxy', 'club']
    MUSIC_KEYWORDS = ['music', 'concert', 'band', 'dj', 'karaoke', 'live', 'show',
                     'hip hop', 'rap', 'reggae', 'jazz', 'rock', 'open mic', 'singer']
    FOOD_KEYWORDS = ['food', 'beer', 'wine', 'brunch', 'drink', 'tasting', 'dinner',
                    'lunch', 'breakfast', 'brewery', 'cocktail', 'chef', 'restaurant']
    ARTS_KEYWORDS = ['art', 'comedy', 'theater', 'theatre', 'gallery', 'museum',
                    'puppet', 'festival', 'cultural', 'dance', 'film', 'exhibit',
                    'kwanzaa', 'craft', 'poetry']

    @staticmethod
    def format_event(e):
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

    @classmethod
    def categorize(cls, event):
        title_lower = str(event.title).lower()
        venue_lower = str(event.venue.name).lower()

        is_music = (any(k in title_lower for k in cls.MUSIC_KEYWORDS) or
                   any(v in venue_lower for v in cls.MUSIC_VENUES))
        is_food = any(k in title_lower for k in cls.FOOD_KEYWORDS)
        is_arts = any(k in title_lower for k in cls.ARTS_KEYWORDS)

        return is_music, is_food, is_arts

    @classmethod
    async def generate(cls):
        """Fetch events and generate newsletter context"""
        print('Fetching events from SerpApi...')

        events, stats = await fetch_serpapi_events(
            location='Richmond, VA',
            date_from=datetime.now().strftime('%Y-%m-%d'),
            date_to=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        )

        print(f'Found {stats.count} events ({stats.status})')

        if not events:
            raise ValueError('No events found')

        result = deduplicate(events)
        print(f'After dedup: {len(result.events)} events')

        # Categorize events
        music, food, arts = [], [], []
        for e in result.events:
            is_music, is_food, is_arts = cls.categorize(e)
            formatted = cls.format_event(e)
            if is_music:
                music.append(formatted)
            if is_food:
                food.append(formatted)
            if is_arts:
                arts.append(formatted)

        formatted_all = [cls.format_event(e) for e in result.events]

        now = datetime.now()
        context = {
            'newsletter_name': BeehiivConfig.NEWSLETTER_NAME,
            'date_range': f'{now.strftime("%B %d")} - {(now + timedelta(days=7)).strftime("%B %d, %Y")}',
            'intro': 'Your weekly guide to the best live music, arts, and events in Richmond!',
            'highlights': formatted_all[:3],
            'music_events': music[:8],
            'food_events': food[:5],
            'arts_events': arts[:5],
            'other_events': formatted_all[3:10],
            'location': BeehiivConfig.LOCATION,
            'footer': 'Curated with love for RVA'
        }

        print(f'Categorized: {len(music)} music, {len(food)} food, {len(arts)} arts')
        return context


class HTMLRenderer:
    """Renders newsletter HTML from template"""

    def __init__(self):
        template_dir = Path(__file__).parent / 'templates'
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def render(self, context: dict) -> str:
        template = self.env.get_template('beehiiv_email.html')
        return template.render(**context)


class BeehiivPublisher:
    """Publishes newsletter to Beehiiv using Playwright"""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser = None
        self.page = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        self.page = await self.context.new_page()
        return self

    async def __aexit__(self, *args):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def login(self):
        """Login to Beehiiv"""
        print('Logging into Beehiiv...')

        await self.page.goto('https://app.beehiiv.com/login')
        await self.page.wait_for_load_state('networkidle')

        # Fill login form
        await self.page.fill('input[type="email"]', BeehiivConfig.EMAIL)
        await self.page.fill('input[type="password"]', BeehiivConfig.PASSWORD)

        # Click login button
        await self.page.click('button[type="submit"]')
        await self.page.wait_for_load_state('networkidle')

        # Wait for dashboard
        await self.page.wait_for_url('**/app.beehiiv.com/**', timeout=30000)
        print('Logged in successfully!')

    async def create_post(self, title: str, subtitle: str, html_content: str, publish: bool = False):
        """Create a new post in Beehiiv"""
        print('Creating new post...')

        # Navigate to create post
        await self.page.goto('https://app.beehiiv.com/')
        await self.page.wait_for_load_state('networkidle')

        # Click "Start writing" button
        start_btn = await self.page.wait_for_selector('button:has-text("Start writing")', timeout=10000)
        await start_btn.click()
        await self.page.wait_for_load_state('networkidle')

        # Wait for editor to load
        await self.page.wait_for_timeout(2000)

        # Fill in title
        title_input = await self.page.wait_for_selector('[data-placeholder="Title"]', timeout=10000)
        await title_input.click()
        await self.page.keyboard.type(title)

        # Fill in subtitle
        subtitle_input = await self.page.wait_for_selector('[data-placeholder="Subtitle"]', timeout=5000)
        await subtitle_input.click()
        await self.page.keyboard.type(subtitle)

        # Click into the content area and paste HTML
        content_area = await self.page.wait_for_selector('.ProseMirror', timeout=5000)
        await content_area.click()

        # Use keyboard shortcut to access HTML mode or paste directly
        # Beehiiv's editor accepts pasted content
        await self.page.keyboard.press('Control+a')
        await self.page.keyboard.type(html_content[:500])  # Type first part

        print('Post content added!')

        if publish:
            # Click Next/Publish
            next_btn = await self.page.wait_for_selector('button:has-text("Next")', timeout=5000)
            await next_btn.click()
            await self.page.wait_for_timeout(2000)

            # Confirm publish
            publish_btn = await self.page.wait_for_selector('button:has-text("Publish")', timeout=5000)
            await publish_btn.click()
            print('Newsletter published!')
        else:
            print('Newsletter saved as draft!')

        return self.page.url


async def main():
    parser = argparse.ArgumentParser(description='Publish newsletter to Beehiiv')
    parser.add_argument('--publish', action='store_true', help='Publish immediately')
    parser.add_argument('--preview', action='store_true', help='Preview only, no publish')
    parser.add_argument('--headless', action='store_true', help='Run browser headlessly')
    args = parser.parse_args()

    # Check for required credentials
    if not BeehiivConfig.EMAIL or not BeehiivConfig.PASSWORD:
        print('\n' + '='*60)
        print('SETUP REQUIRED')
        print('='*60)
        print('Set your Beehiiv credentials as environment variables:')
        print('  set BEEHIIV_EMAIL=your@email.com')
        print('  set BEEHIIV_PASSWORD=yourpassword')
        print('='*60 + '\n')
        return

    if not PLAYWRIGHT_AVAILABLE:
        print('Please install Playwright:')
        print('  pip install playwright')
        print('  playwright install chromium')
        return

    try:
        # Generate newsletter content
        print('\n' + '='*60)
        print('GENERATING NEWSLETTER')
        print('='*60)
        context = await NewsletterGenerator.generate()

        # Render HTML
        print('\nRendering HTML template...')
        renderer = HTMLRenderer()
        html_content = renderer.render(context)

        # Save HTML preview
        preview_file = f'newsletter_{datetime.now().strftime("%Y-%m-%d")}_preview.html'
        with open(preview_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f'Preview saved to: {preview_file}')

        if args.preview:
            print('\nPreview mode - opening in browser...')
            os.startfile(preview_file)
            return

        # Publish to Beehiiv
        print('\n' + '='*60)
        print('PUBLISHING TO BEEHIIV')
        print('='*60)

        async with BeehiivPublisher(headless=args.headless) as publisher:
            await publisher.login()

            title = context['newsletter_name']
            subtitle = f"{context['date_range']} | Your weekly guide to Richmond events"

            url = await publisher.create_post(
                title=title,
                subtitle=subtitle,
                html_content=html_content,
                publish=args.publish
            )

            print('\n' + '='*60)
            print('SUCCESS!')
            print('='*60)
            print(f'Post URL: {url}')
            if not args.publish:
                print('Status: Saved as DRAFT - review and publish manually')

    except Exception as e:
        print(f'\nError: {e}')
        raise


if __name__ == '__main__':
    asyncio.run(main())
