"""
Generic web scraper for venue calendars and event pages.

Cost: Free (uses httpx + BeautifulSoup)
Use Case: Theater calendars, community centers, local aggregators

This captures events from venue websites that don't have API access.
"""

import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional
import re

from ..models import Event, Venue, FetchStats
from .url_validator import validate_url_for_scraping, SSRFError


# Common selectors for event listing pages
DEFAULT_SELECTORS = {
    "event_container": [
        ".event", ".event-item", ".event-card",
        "[class*='event']", "[data-event]",
        ".show", ".performance", ".listing"
    ],
    "title": [
        "h2", "h3", ".event-title", ".title",
        "[class*='title']", ".name", "a"
    ],
    "date": [
        ".date", ".event-date", "[class*='date']",
        "time", "[datetime]", ".when"
    ],
    "venue": [
        ".venue", ".location", "[class*='venue']",
        "[class*='location']", ".place"
    ],
    "price": [
        ".price", "[class*='price']", ".cost",
        ".admission", ".ticket-price"
    ],
    "link": [
        "a[href]"
    ]
}


async def scrape_event_page(
    url: str,
    venue_name: Optional[str] = None,
    default_city: str = "Richmond",
    default_state: str = "VA",
    custom_selectors: Optional[dict] = None
) -> tuple[list[Event], FetchStats]:
    """
    Scrape events from a venue's calendar page.

    Args:
        url: URL of the event calendar page
        venue_name: Name of the venue (extracted from page if not provided)
        default_city: Default city for events
        default_state: Default state for events
        custom_selectors: Optional custom CSS selectors

    Returns:
        Tuple of (events, fetch_stats)
    """
    start_time = datetime.now()
    selectors = custom_selectors or DEFAULT_SELECTORS

    # Validate URL for SSRF protection before making request
    try:
        url = validate_url_for_scraping(url)
    except SSRFError as e:
        return [], FetchStats(
            source="web",
            count=0,
            status="error",
            error_message=f"URL validation failed: {e}"
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                follow_redirects=True
            )
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, "html.parser")

        # Extract venue name from page if not provided
        if not venue_name:
            venue_name = _extract_venue_name(soup, url)

        # Find event containers
        events: list[Event] = []
        event_elements = _find_event_elements(soup, selectors["event_container"])

        for element in event_elements:
            event = _parse_event_element(
                element, selectors, venue_name,
                default_city, default_state, url
            )
            if event:
                events.append(event)

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return events, FetchStats(
            source="web",
            count=len(events),
            status="success",
            duration_ms=duration_ms
        )

    except httpx.HTTPStatusError as e:
        return [], FetchStats(
            source="web",
            count=0,
            status="error",
            error_message=f"HTTP {e.response.status_code}"
        )
    except Exception as e:
        return [], FetchStats(
            source="web",
            count=0,
            status="error",
            error_message=str(e)
        )


def _extract_venue_name(soup: BeautifulSoup, url: str) -> str:
    """Extract venue name from page."""
    # Try common title elements
    for selector in ["h1", ".venue-name", ".site-title", "title"]:
        element = soup.select_one(selector)
        if element:
            text = element.get_text(strip=True)
            # Clean up title tags
            if " | " in text:
                text = text.split(" | ")[0]
            if " - " in text:
                text = text.split(" - ")[0]
            if len(text) > 3 and len(text) < 100:
                return text

    # Fall back to domain name
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    domain = domain.replace("www.", "")
    return domain.split(".")[0].title()


def _find_event_elements(soup: BeautifulSoup, selectors: list[str]) -> list:
    """Find event container elements using multiple selectors."""
    for selector in selectors:
        try:
            elements = soup.select(selector)
            if elements:
                return elements
        except (ValueError, TypeError):
            continue
    return []


def _parse_event_element(
    element,
    selectors: dict,
    venue_name: str,
    default_city: str,
    default_state: str,
    base_url: str
) -> Optional[Event]:
    """Parse a single event element into an Event object."""
    try:
        # Extract title
        title = _extract_text(element, selectors["title"])
        if not title or len(title) < 3:
            return None

        # Extract date
        date_text = _extract_text(element, selectors["date"])
        event_date = _parse_date_text(date_text)
        if not event_date:
            return None

        # Extract price
        price_text = _extract_text(element, selectors["price"])
        price = _parse_price_text(price_text)

        # Extract link
        link = None
        for sel in selectors["link"]:
            link_el = element.select_one(sel)
            if link_el and link_el.get("href"):
                href = link_el.get("href")
                if not href.startswith("http"):
                    from urllib.parse import urljoin
                    href = urljoin(base_url, href)
                link = href
                break

        venue = Venue(
            name=venue_name,
            city=default_city,
            state=default_state,
            website=base_url
        )

        return Event(
            source="web",
            source_id=f"web_{hash(title + str(event_date))}"[:16],
            source_url=link or base_url,
            title=title,
            start_time=event_date,
            venue=venue,
            price=price,
            confidence=0.6  # Lower confidence for web scraped events
        )

    except (ValueError, TypeError, AttributeError, KeyError):
        return None


def _extract_text(element, selectors: list[str]) -> Optional[str]:
    """Extract text from element using multiple selectors."""
    for selector in selectors:
        try:
            sub_el = element.select_one(selector)
            if sub_el:
                text = sub_el.get_text(strip=True)
                if text:
                    return text
        except (ValueError, TypeError, AttributeError):
            continue

    # Try direct text content
    text = element.get_text(strip=True)
    return text[:200] if text else None


def _parse_date_text(text: Optional[str]) -> Optional[datetime]:
    """Parse various date formats from scraped text."""
    if not text:
        return None

    from dateutil import parser

    try:
        # Try direct parse
        parsed = parser.parse(text, fuzzy=True)

        # Sanity check - should be in the future or recent past
        now = datetime.now()
        if parsed.year < 2020:
            parsed = parsed.replace(year=now.year)
        if parsed < now - datetime.timedelta(days=7):
            # If in past, assume next occurrence
            parsed = parsed.replace(year=now.year + 1)

        return parsed
    except (ValueError, TypeError, OverflowError):
        return None


def _parse_price_text(text: Optional[str]) -> Optional[str]:
    """Parse price from text."""
    if not text:
        return None

    text_lower = text.lower()

    if "free" in text_lower:
        return "Free"

    # Find dollar amounts
    match = re.search(r'\$?\d+(?:\.\d{2})?', text)
    if match:
        amount = match.group()
        if not amount.startswith("$"):
            amount = f"${amount}"
        return amount

    return None


# Richmond-area venue calendar URLs (defaults)
RICHMOND_VENUE_URLS = [
    ("The National", "https://www.thenationalva.com/events"),
    ("The Broadberry", "https://www.thebroadberry.com/events"),
    ("Canal Club", "https://www.canalclub.com/events"),
    ("Richmond CultureWorks", "https://calendar.richmondcultureworks.org/"),
]
