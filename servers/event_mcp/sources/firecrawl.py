"""
Firecrawl-powered web scraper for venue calendars.

Cost: Firecrawl API (500 free credits/month)
Use Case: Venue calendars with JavaScript rendering, complex layouts

Firecrawl provides better scraping than raw BeautifulSoup:
- JavaScript rendering
- Automatic content extraction
- Structured markdown output
"""

import os
import httpx
from datetime import datetime
from typing import Optional
import re

from ..models import Event, Venue, FetchStats
from .url_validator import validate_url_for_scraping, SSRFError


FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"


async def fetch_firecrawl_events(
    url: str,
    venue_name: Optional[str] = None,
    default_city: str = "Richmond",
    default_state: str = "VA",
) -> tuple[list[Event], FetchStats]:
    """
    Scrape events from a venue calendar using Firecrawl API.

    Args:
        url: URL of the event calendar page
        venue_name: Name of the venue (extracted from content if not provided)
        default_city: Default city for events
        default_state: Default state for events

    Returns:
        Tuple of (events, fetch_stats)
    """
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return [], FetchStats(
            source="firecrawl",
            count=0,
            status="error",
            error_message="FIRECRAWL_API_KEY not set"
        )

    # Validate URL for SSRF protection before making request
    try:
        url = validate_url_for_scraping(url)
    except SSRFError as e:
        return [], FetchStats(
            source="firecrawl",
            count=0,
            status="error",
            error_message=f"URL validation failed: {e}"
        )

    start_time = datetime.now()

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{FIRECRAWL_API_URL}/scrape",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "url": url,
                    "formats": ["markdown", "html"],
                    "onlyMainContent": True
                }
            )
            response.raise_for_status()
            data = response.json()

        if not data.get("success"):
            return [], FetchStats(
                source="firecrawl",
                count=0,
                status="error",
                error_message=data.get("error", "Unknown error")
            )

        # Extract content
        content = data.get("data", {})
        markdown = content.get("markdown", "")
        metadata = content.get("metadata", {})

        # Get venue name from metadata if not provided
        if not venue_name:
            venue_name = metadata.get("title", "").split(" | ")[0]
            venue_name = venue_name.split(" - ")[0].strip()
            if not venue_name:
                venue_name = _extract_domain_name(url)

        # Parse events from markdown content
        events = _parse_events_from_markdown(
            markdown, venue_name, default_city, default_state, url
        )

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return events, FetchStats(
            source="firecrawl",
            count=len(events),
            status="success",
            duration_ms=duration_ms
        )

    except httpx.HTTPStatusError as e:
        return [], FetchStats(
            source="firecrawl",
            count=0,
            status="error",
            error_message=f"HTTP {e.response.status_code}"
        )
    except httpx.RequestError as e:
        return [], FetchStats(
            source="firecrawl",
            count=0,
            status="error",
            error_message=f"Request failed: {str(e)}"
        )
    except Exception as e:
        return [], FetchStats(
            source="firecrawl",
            count=0,
            status="error",
            error_message=str(e)
        )


async def crawl_venue_site(
    url: str,
    max_pages: int = 10,
    default_city: str = "Richmond",
    default_state: str = "VA",
) -> tuple[list[Event], FetchStats]:
    """
    Crawl a venue website to find all event pages.

    Uses Firecrawl's crawl endpoint to discover and scrape
    multiple pages from a venue's website.

    Args:
        url: Base URL of the venue website
        max_pages: Maximum number of pages to crawl
        default_city: Default city for events
        default_state: Default state for events

    Returns:
        Tuple of (events, fetch_stats)
    """
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return [], FetchStats(
            source="firecrawl",
            count=0,
            status="error",
            error_message="FIRECRAWL_API_KEY not set"
        )

    # Validate URL for SSRF protection before making request
    try:
        url = validate_url_for_scraping(url)
    except SSRFError as e:
        return [], FetchStats(
            source="firecrawl",
            count=0,
            status="error",
            error_message=f"URL validation failed: {e}"
        )

    start_time = datetime.now()

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Start crawl job
            response = await client.post(
                f"{FIRECRAWL_API_URL}/crawl",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "url": url,
                    "limit": max_pages,
                    "scrapeOptions": {
                        "formats": ["markdown"],
                        "onlyMainContent": True
                    },
                    "includePaths": ["/events", "/calendar", "/shows", "/schedule"]
                }
            )
            response.raise_for_status()
            data = response.json()

        if not data.get("success"):
            return [], FetchStats(
                source="firecrawl",
                count=0,
                status="error",
                error_message=data.get("error", "Crawl failed")
            )

        # Extract venue name from base URL
        venue_name = _extract_domain_name(url)

        # Parse events from all crawled pages
        all_events: list[Event] = []
        pages = data.get("data", [])

        for page in pages:
            markdown = page.get("markdown", "")
            page_url = page.get("url", url)
            events = _parse_events_from_markdown(
                markdown, venue_name, default_city, default_state, page_url
            )
            all_events.extend(events)

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return all_events, FetchStats(
            source="firecrawl",
            count=len(all_events),
            status="success",
            duration_ms=duration_ms,
            pages_crawled=len(pages)
        )

    except httpx.HTTPStatusError as e:
        return [], FetchStats(
            source="firecrawl",
            count=0,
            status="error",
            error_message=f"HTTP {e.response.status_code}"
        )
    except Exception as e:
        return [], FetchStats(
            source="firecrawl",
            count=0,
            status="error",
            error_message=str(e)
        )


def _extract_domain_name(url: str) -> str:
    """Extract venue name from domain."""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    domain = domain.replace("www.", "")
    name = domain.split(".")[0]
    return name.replace("-", " ").title()


def _parse_events_from_markdown(
    markdown: str,
    venue_name: str,
    default_city: str,
    default_state: str,
    source_url: str
) -> list[Event]:
    """
    Parse events from markdown content.

    Looks for patterns like:
    - ## Event Title
    - **Date**: January 15, 2025
    - **Time**: 8:00 PM
    - **Price**: $15

    Or structured lists with dates and event names.
    """
    events: list[Event] = []

    # Pattern 1: Headers followed by dates
    header_pattern = re.compile(
        r'#{1,3}\s+(.+?)\n.*?(?:date|when|time).*?(\w+\s+\d{1,2},?\s*\d{4}|\d{1,2}/\d{1,2}/\d{4})',
        re.IGNORECASE | re.DOTALL
    )

    # Pattern 2: List items with dates and titles
    list_pattern = re.compile(
        r'[-*]\s*\*?\*?([^*\n]+?)\*?\*?\s*[-–]\s*(\w+\s+\d{1,2}|\d{1,2}/\d{1,2})',
        re.IGNORECASE
    )

    # Pattern 3: Date followed by event name
    date_first_pattern = re.compile(
        r'(?:^|\n)(\w{3,9}\s+\d{1,2}(?:,?\s*\d{4})?)\s*[-–:]\s*(.+?)(?:\n|$)',
        re.IGNORECASE
    )

    from dateutil import parser as date_parser

    venue = Venue(
        name=venue_name,
        city=default_city,
        state=default_state,
        website=source_url
    )

    seen_titles = set()

    # Try each pattern
    for match in header_pattern.finditer(markdown):
        title, date_str = match.groups()
        event = _create_event_from_match(
            title, date_str, venue, source_url, seen_titles
        )
        if event:
            events.append(event)

    for match in list_pattern.finditer(markdown):
        title, date_str = match.groups()
        event = _create_event_from_match(
            title, date_str, venue, source_url, seen_titles
        )
        if event:
            events.append(event)

    for match in date_first_pattern.finditer(markdown):
        date_str, title = match.groups()
        event = _create_event_from_match(
            title, date_str, venue, source_url, seen_titles
        )
        if event:
            events.append(event)

    return events


def _create_event_from_match(
    title: str,
    date_str: str,
    venue: Venue,
    source_url: str,
    seen_titles: set
) -> Optional[Event]:
    """Create an Event from a regex match."""
    from dateutil import parser as date_parser

    # Clean title
    title = title.strip()
    title = re.sub(r'\s+', ' ', title)
    title = title.strip('*#-_ ')

    if not title or len(title) < 3:
        return None

    # Skip duplicates
    title_key = title.lower()[:50]
    if title_key in seen_titles:
        return None
    seen_titles.add(title_key)

    # Parse date
    try:
        parsed_date = date_parser.parse(date_str, fuzzy=True)
        now = datetime.now()

        # Ensure year is set correctly
        if parsed_date.year < 2020:
            parsed_date = parsed_date.replace(year=now.year)

        # If date is in past, assume next year
        if parsed_date < now:
            parsed_date = parsed_date.replace(year=now.year + 1)

    except (ValueError, TypeError):
        return None

    return Event(
        source="firecrawl",
        source_id=f"fc_{hash(title + str(parsed_date))}"[:16],
        source_url=source_url,
        title=title,
        start_time=parsed_date,
        venue=venue,
        confidence=0.7  # Higher confidence than basic web scraper
    )


# Richmond venue URLs optimized for Firecrawl
FIRECRAWL_VENUE_URLS = [
    ("The National", "https://www.thenationalva.com/events"),
    ("The Broadberry", "https://www.thebroadberry.com/events"),
    ("Canal Club", "https://www.canalclub.com/events"),
    ("Richmond Folk Festival", "https://richmondfolkfestival.org/"),
    ("Style Weekly Events", "https://www.styleweekly.com/richmond/EventSearch"),
]
