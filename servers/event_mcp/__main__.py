"""
MCP Server entry point for Local Events Newsletter.

This server provides tools for:
- Fetching events from multiple sources
- Deduplicating events
- Classifying events by category
- Generating newsletter content

Run with: python -m servers.event_mcp
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from typing import Optional

# MCP server implementation
# Note: In a full implementation, you would use the official MCP SDK
# For now, this provides a JSON-RPC style interface


class EventAggregatorServer:
    """MCP Server for event aggregation."""

    def __init__(self):
        self.tools = {
            "fetch_events": self.fetch_events,
            "fetch_serpapi": self.fetch_serpapi,
            "fetch_instagram": self.fetch_instagram,
            "fetch_web": self.fetch_web,
            "deduplicate": self.deduplicate,
            "classify": self.classify,
            "get_location": self.get_location,
        }

    async def fetch_events(
        self,
        location: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        sources: Optional[list[str]] = None,
        instagram_handles: Optional[list[str]] = None,
        web_urls: Optional[list[str]] = None
    ) -> dict:
        """
        Fetch events from all configured sources.

        Args:
            location: City/area to search
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            sources: List of sources to use (serpapi, instagram, web)
            instagram_handles: Instagram handles to scrape
            web_urls: Website URLs to scrape
        """
        from .models import FetchResult

        sources = sources or ["serpapi"]
        date_from, date_to = self._normalize_dates(date_from, date_to)

        all_events, all_stats, failed = await self._fetch_all_sources(
            location, date_from, date_to, sources, instagram_handles, web_urls
        )

        result = FetchResult(
            events=all_events,
            stats=all_stats,
            total=len(all_events),
            failed_sources=failed
        )
        return result.model_dump()

    def _normalize_dates(
        self, date_from: Optional[str], date_to: Optional[str]
    ) -> tuple[str, str]:
        """Set default date range if not provided."""
        if not date_from:
            date_from = datetime.now().strftime("%Y-%m-%d")
        if not date_to:
            date_to = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        return date_from, date_to

    async def _fetch_all_sources(
        self,
        location: str,
        date_from: str,
        date_to: str,
        sources: list[str],
        instagram_handles: Optional[list[str]],
        web_urls: Optional[list[str]]
    ) -> tuple[list, list, list[str]]:
        """Fetch from all configured sources and aggregate results."""
        from .sources import fetch_serpapi_events, fetch_instagram_events, scrape_event_page

        all_events, all_stats, failed = [], [], []

        if "serpapi" in sources:
            events, stats, err = await self._fetch_serpapi(
                location, date_from, date_to
            )
            all_events.extend(events)
            all_stats.append(stats)
            if err:
                failed.append(err)

        if "instagram" in sources and instagram_handles:
            events, stats, err = await self._fetch_instagram(location, instagram_handles)
            all_events.extend(events)
            all_stats.append(stats)
            if err:
                failed.append(err)

        if "web" in sources and web_urls:
            for url in web_urls:
                events, stats, err = await self._fetch_web(location, url)
                all_events.extend(events)
                all_stats.append(stats)
                if err:
                    failed.append(err)

        return all_events, all_stats, failed

    async def _fetch_serpapi(
        self, location: str, date_from: str, date_to: str
    ) -> tuple[list, object, Optional[str]]:
        """Fetch events from SerpApi."""
        from .sources import fetch_serpapi_events

        events, stats = await fetch_serpapi_events(
            location=location, date_from=date_from, date_to=date_to
        )
        error = "serpapi" if stats.status == "error" else None
        return events, stats, error

    async def _fetch_instagram(
        self, location: str, handles: list[str]
    ) -> tuple[list, object, Optional[str]]:
        """Fetch events from Instagram."""
        from .sources import fetch_instagram_events

        city, state = self._parse_location(location)
        events, stats = await fetch_instagram_events(
            handles=handles, default_city=city, default_state=state
        )
        error = "instagram" if stats.status == "error" else None
        return events, stats, error

    async def _fetch_web(
        self, location: str, url: str
    ) -> tuple[list, object, Optional[str]]:
        """Fetch events from a web URL."""
        from .sources import scrape_event_page

        city, state = self._parse_location(location)
        events, stats = await scrape_event_page(
            url=url, default_city=city, default_state=state
        )
        error = f"web:{url}" if stats.status == "error" else None
        return events, stats, error

    async def fetch_serpapi(
        self,
        location: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        categories: Optional[list[str]] = None
    ) -> dict:
        """Fetch events from Google Events via SerpApi."""
        from .sources import fetch_serpapi_events

        events, stats = await fetch_serpapi_events(
            location=location,
            date_from=date_from,
            date_to=date_to,
            categories=categories
        )

        return {
            "events": [e.model_dump() for e in events],
            "stats": stats.model_dump()
        }

    async def fetch_instagram(
        self,
        handles: list[str],
        days: int = 7,
        city: str = "Richmond",
        state: str = "VA"
    ) -> dict:
        """Fetch events from Instagram venue handles."""
        from .sources import fetch_instagram_events

        events, stats = await fetch_instagram_events(
            handles=handles,
            days=days,
            default_city=city,
            default_state=state
        )

        return {
            "events": [e.model_dump() for e in events],
            "stats": stats.model_dump()
        }

    async def fetch_web(
        self,
        url: str,
        venue_name: Optional[str] = None,
        city: str = "Richmond",
        state: str = "VA"
    ) -> dict:
        """Scrape events from a venue calendar page."""
        from .sources import scrape_event_page

        events, stats = await scrape_event_page(
            url=url,
            venue_name=venue_name,
            default_city=city,
            default_state=state
        )

        return {
            "events": [e.model_dump() for e in events],
            "stats": stats.model_dump()
        }

    async def deduplicate(
        self,
        events: list[dict],
        threshold: float = 0.75
    ) -> dict:
        """Deduplicate a list of events."""
        from .models import Event
        from .dedup import deduplicate as dedup_func

        # Convert dicts to Event objects
        event_objects = [Event(**e) for e in events]

        result = dedup_func(event_objects, threshold=threshold)

        return result.model_dump()

    async def classify(
        self,
        event: dict,
        categories: Optional[list[str]] = None
    ) -> dict:
        """
        Classify an event into categories.

        Returns the event with category and subcategories filled in,
        plus a confidence score.
        """
        from .models import Event, CATEGORIES

        event_obj = Event(**event)
        title_lower = event_obj.title.lower()
        desc_lower = (event_obj.description or "").lower()
        combined = f"{title_lower} {desc_lower}"

        # Simple keyword-based classification
        scores = {}

        # Music keywords
        music_keywords = [
            "concert", "live music", "band", "dj", "jazz", "reggae",
            "rock", "hip hop", "acoustic", "symphony", "orchestra"
        ]
        scores["music"] = sum(1 for kw in music_keywords if kw in combined)

        # Food keywords
        food_keywords = [
            "food", "tasting", "brunch", "dinner", "chef", "brewery",
            "wine", "beer", "cocktail", "restaurant", "pop-up"
        ]
        scores["food_drink"] = sum(1 for kw in food_keywords if kw in combined)

        # Arts keywords
        arts_keywords = [
            "art", "gallery", "exhibition", "theater", "theatre", "play",
            "film", "movie", "comedy", "improv", "poetry"
        ]
        scores["arts"] = sum(1 for kw in arts_keywords if kw in combined)

        # Find best match
        if scores:
            best_category = max(scores, key=scores.get)
            best_score = scores[best_category]

            if best_score > 0:
                event_obj.category = best_category
                event_obj.confidence = min(1.0, 0.5 + (best_score * 0.1))

                # Add subcategories
                if best_category == "music":
                    if "reggae" in combined:
                        event_obj.subcategories.append("reggae")
                    if "jazz" in combined:
                        event_obj.subcategories.append("jazz")
                    if "live" in combined or "band" in combined:
                        event_obj.subcategories.append("live_music")

        return event_obj.model_dump()

    async def get_location(self) -> dict:
        """Auto-detect user location from IP."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("https://ipapi.co/json/")
                data = response.json()

            return {
                "city": data.get("city", "Richmond"),
                "state": data.get("region_code", "VA"),
                "country": data.get("country_code", "US"),
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "detected": True
            }
        except (httpx.RequestError, httpx.TimeoutException, KeyError, ValueError):
            return {
                "city": "Richmond",
                "state": "VA",
                "country": "US",
                "detected": False
            }

    def _parse_location(self, location: str) -> tuple[str, str]:
        """Parse location string into city and state."""
        parts = location.split(",")
        city = parts[0].strip()
        state = parts[1].strip() if len(parts) > 1 else "VA"
        return city, state


async def main():
    """Main entry point for MCP server."""
    server = EventAggregatorServer()

    # Simple JSON-RPC style interface for testing
    # In production, use the official MCP SDK

    print("Local Events Newsletter MCP Server")
    print("Available tools:", list(server.tools.keys()))
    print("\nServer ready. Use /newsletter commands in Claude Code.")

    # For testing: run a sample fetch
    if "--test" in sys.argv:
        print("\n--- Running test fetch ---")
        result = await server.fetch_events(
            location="Richmond, VA",
            sources=["serpapi"]
        )
        print(f"Found {result['total']} events")
        for stat in result['stats']:
            print(f"  {stat['source']}: {stat['count']} events ({stat['status']})")


if __name__ == "__main__":
    asyncio.run(main())
