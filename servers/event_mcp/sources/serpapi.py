"""
SerpApi Google Events integration.

Free tier: 100 searches/month
Paid: $50/month for 5000 searches

This is the primary data source for broad event coverage.
"""

import os
import httpx
from datetime import datetime, timedelta
from typing import Optional
import asyncio

from ..models import Event, Venue, FetchStats


SERPAPI_BASE = "https://serpapi.com/search"
RATE_LIMIT_DELAY = 1.0  # 1 request per second


async def fetch_serpapi_events(
    location: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    categories: Optional[list[str]] = None,
    limit: int = 100
) -> tuple[list[Event], FetchStats]:
    """
    Fetch events from Google Events via SerpApi.

    Args:
        location: City/area to search (e.g., "Richmond, VA")
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        categories: Filter by categories (music, food, etc.)
        limit: Max events to return

    Returns:
        Tuple of (events, fetch_stats)
    """
    api_key = os.environ.get("SERPAPI_KEY")

    if not api_key:
        return [], FetchStats(
            source="serpapi",
            count=0,
            status="skipped",
            error_message="SERPAPI_KEY not configured"
        )

    start_time = datetime.now()

    # Build search query
    query_parts = ["events"]

    if categories:
        # Map our categories to search terms
        category_terms = {
            "music": "live music concerts",
            "food_drink": "food drink tastings",
            "arts": "art gallery theater",
            "nightlife": "nightlife clubs bars",
            "community": "community festivals markets",
            "reggae": "reggae music"  # Special for Richmond focus
        }
        for cat in categories:
            if cat in category_terms:
                query_parts.append(category_terms[cat])

    query = f"{' '.join(query_parts)} in {location}"

    params = {
        "engine": "google_events",
        "q": query,
        "hl": "en",
        "api_key": api_key
    }

    # Add date filters if provided
    if date_from:
        params["date"] = date_from

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(SERPAPI_BASE, params=params)
            response.raise_for_status()
            data = response.json()

        events = []
        events_data = data.get("events_results", [])

        for item in events_data[:limit]:
            event = _parse_serpapi_event(item, location)
            if event:
                # Filter by date range if specified
                if date_from:
                    from_dt = datetime.strptime(date_from, "%Y-%m-%d")
                    if event.start_time.date() < from_dt.date():
                        continue
                if date_to:
                    to_dt = datetime.strptime(date_to, "%Y-%m-%d")
                    if event.start_time.date() > to_dt.date():
                        continue

                events.append(event)

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return events, FetchStats(
            source="serpapi",
            count=len(events),
            status="success",
            duration_ms=duration_ms
        )

    except httpx.HTTPStatusError as e:
        return [], FetchStats(
            source="serpapi",
            count=0,
            status="error",
            error_message=f"HTTP {e.response.status_code}: {str(e)}"
        )
    except Exception as e:
        return [], FetchStats(
            source="serpapi",
            count=0,
            status="error",
            error_message=str(e)
        )


def _parse_serpapi_event(item: dict, default_location: str) -> Optional[Event]:
    """Parse a SerpApi event result into our Event model."""
    try:
        title = item.get("title", "")
        if not title:
            return None

        # Parse date/time
        date_info = item.get("date", {})
        when = date_info.get("when", "")
        start_date = date_info.get("start_date", "")

        # Try to parse the date
        start_time = _parse_event_datetime(start_date, when)
        if not start_time:
            # Default to tomorrow if no date
            start_time = datetime.now() + timedelta(days=1)

        # Parse venue
        address_info = item.get("address", [])
        venue_name = address_info[0] if address_info else "TBD"
        venue_address = ", ".join(address_info[1:]) if len(address_info) > 1 else None

        # Try to extract city/state from address or use default
        city, state = _extract_city_state(venue_address, default_location)

        venue = Venue(
            name=venue_name,
            address=venue_address,
            city=city,
            state=state
        )

        # Get other fields
        description = item.get("description", "")
        link = item.get("link", "")
        thumbnail = item.get("thumbnail", "")

        # Extract ticket info if available
        ticket_info = item.get("ticket_info", [])
        ticket_url = None
        price = None
        if ticket_info:
            for ticket in ticket_info:
                if "link" in ticket:
                    ticket_url = ticket["link"]
                if "price" in ticket:
                    price = ticket["price"]
                break

        return Event(
            source="serpapi",
            source_id=item.get("event_id", f"serpapi_{hash(title)}"),
            source_url=link,
            title=title,
            description=description,
            start_time=start_time,
            venue=venue,
            price=price,
            ticket_url=ticket_url,
            image_url=thumbnail
        )

    except Exception as e:
        # Skip malformed events
        return None


def _parse_event_datetime(start_date: str, when: str) -> Optional[datetime]:
    """Parse various date/time formats from SerpApi."""
    import re
    from dateutil import parser

    try:
        if start_date:
            # Try direct parse
            return parser.parse(start_date)
    except (ValueError, TypeError, OverflowError):
        pass

    try:
        if when:
            # Try parsing the "when" field
            return parser.parse(when, fuzzy=True)
    except (ValueError, TypeError, OverflowError):
        pass

    return None


def _extract_city_state(address: Optional[str], default_location: str) -> tuple[str, str]:
    """Extract city and state from address string."""
    # Default to Richmond, VA for this plugin
    default_city = "Richmond"
    default_state = "VA"

    if default_location:
        parts = default_location.split(",")
        if len(parts) >= 2:
            default_city = parts[0].strip()
            default_state = parts[1].strip()

    if not address:
        return default_city, default_state

    # Try to extract from address
    import re
    # Pattern for "City, ST" or "City, State"
    pattern = r'([A-Za-z\s]+),\s*([A-Z]{2}|[A-Za-z]+)\s*(\d{5})?'
    match = re.search(pattern, address)

    if match:
        city = match.group(1).strip()
        state = match.group(2).strip()
        return city, state

    return default_city, default_state


# For testing without API key
async def fetch_mock_events(location: str = "Richmond, VA") -> list[Event]:
    """Return mock events for testing."""
    now = datetime.now()

    return [
        Event(
            source="mock",
            source_id="mock_1",
            title="Live Reggae Night at The Camel",
            description="Weekly reggae and roots music showcase featuring local and touring artists.",
            start_time=now + timedelta(days=2, hours=20),
            venue=Venue(
                name="The Camel",
                address="1621 W Broad St",
                city="Richmond",
                state="VA",
                venue_type="music_venue"
            ),
            category="music",
            subcategories=["reggae", "live_music"],
            price="$10"
        ),
        Event(
            source="mock",
            source_id="mock_2",
            title="Food Truck Friday at Brown's Island",
            description="Weekly gathering of Richmond's best food trucks with live music.",
            start_time=now + timedelta(days=3, hours=17),
            venue=Venue(
                name="Brown's Island",
                address="5th & Tredegar St",
                city="Richmond",
                state="VA",
                venue_type="outdoor"
            ),
            category="food_drink",
            subcategories=["food_trucks"],
            price="Free entry"
        ),
        Event(
            source="mock",
            source_id="mock_3",
            title="Jazz Brunch at Lemaire",
            description="Sunday brunch featuring live jazz quartet.",
            start_time=now + timedelta(days=4, hours=11),
            venue=Venue(
                name="Lemaire at The Jefferson Hotel",
                address="101 W Franklin St",
                city="Richmond",
                state="VA",
                venue_type="restaurant"
            ),
            category="music",
            subcategories=["jazz", "brunch"],
            price="$45"
        )
    ]
