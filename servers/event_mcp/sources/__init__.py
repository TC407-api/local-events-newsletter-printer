"""
Event source adapters.

Each source implements:
- fetch_events(location, date_from, date_to) -> list[Event]
- Source-specific rate limiting and error handling
"""

from .serpapi import fetch_serpapi_events
from .instagram import fetch_instagram_events
from .web_scraper import scrape_event_page
from .firecrawl import fetch_firecrawl_events, crawl_venue_site

__all__ = [
    "fetch_serpapi_events",
    "fetch_instagram_events",
    "scrape_event_page",
    "fetch_firecrawl_events",
    "crawl_venue_site",
]
