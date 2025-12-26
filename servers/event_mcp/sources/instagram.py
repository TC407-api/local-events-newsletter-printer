"""
Instagram venue scraping via ScrapeCreators API.

Cost: ~$20/month for small usage
Use Case: Venue-specific events, flyers, local happenings

This captures events that only appear on Instagram (competitors miss these).
"""

import os
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import re

from ..models import Event, Venue, FetchStats


SCRAPECREATORS_BASE = "https://api.scrapecreators.com/v1"
RATE_LIMIT_DELAY = 0.5  # 2 requests per second


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, calls_per_second: float = 2.0):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0.0

    async def wait(self):
        """Wait if needed to respect rate limit."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self.last_call
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_call = asyncio.get_event_loop().time()


rate_limiter = RateLimiter(calls_per_second=2.0)


async def fetch_instagram_events(
    handles: list[str],
    days: int = 7,
    default_city: str = "Richmond",
    default_state: str = "VA"
) -> tuple[list[Event], FetchStats]:
    """
    Fetch events from Instagram venue handles.

    Args:
        handles: List of Instagram handles (with or without @)
        days: Look back this many days for posts
        default_city: Default city for venues
        default_state: Default state for venues

    Returns:
        Tuple of (events, fetch_stats)
    """
    api_key = os.environ.get("SCRAPECREATORS_KEY")

    if not api_key:
        return [], FetchStats(
            source="instagram",
            count=0,
            status="skipped",
            error_message="SCRAPECREATORS_KEY not configured"
        )

    if not handles:
        return [], FetchStats(
            source="instagram",
            count=0,
            status="skipped",
            error_message="No Instagram handles provided"
        )

    start_time = datetime.now()
    all_events: list[Event] = []
    errors: list[str] = []

    for handle in handles:
        # Normalize handle (remove @)
        handle = handle.lstrip("@").strip()

        try:
            await rate_limiter.wait()
            posts = await _fetch_profile_posts(api_key, handle, days)

            for post in posts:
                event = _parse_instagram_post(
                    post, handle, default_city, default_state
                )
                if event:
                    all_events.append(event)

        except Exception as e:
            errors.append(f"@{handle}: {str(e)}")

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    status = "success" if not errors else "partial"
    error_msg = "; ".join(errors) if errors else None

    return all_events, FetchStats(
        source="instagram",
        count=len(all_events),
        status=status,
        duration_ms=duration_ms,
        error_message=error_msg
    )


async def _fetch_profile_posts(
    api_key: str,
    handle: str,
    days: int
) -> list[dict]:
    """Fetch recent posts from an Instagram profile."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{SCRAPECREATORS_BASE}/instagram/profile/{handle}/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"limit": 20}  # Get recent 20 posts
        )
        response.raise_for_status()
        data = response.json()

    posts = data.get("posts", [])

    # Filter to posts within the date range
    cutoff = datetime.now() - timedelta(days=days)
    filtered = []

    for post in posts:
        posted_at = post.get("taken_at") or post.get("timestamp")
        if posted_at:
            try:
                if isinstance(posted_at, str):
                    from dateutil import parser
                    post_date = parser.parse(posted_at)
                elif isinstance(posted_at, (int, float)):
                    post_date = datetime.fromtimestamp(posted_at)
                else:
                    post_date = datetime.now()

                if post_date >= cutoff:
                    filtered.append(post)
            except (ValueError, TypeError, OverflowError):
                # Include if we can't parse date
                filtered.append(post)

    return filtered


def _parse_instagram_post(
    post: dict,
    handle: str,
    default_city: str,
    default_state: str
) -> Optional[Event]:
    """
    Parse an Instagram post into an Event if it looks like an event.

    Uses heuristics to detect event posts:
    - Contains dates (Jan 15, 1/15, etc.)
    - Contains times (8pm, 8:00 PM, etc.)
    - Contains event keywords (tonight, live, tickets, etc.)
    """
    caption = post.get("caption") or post.get("text") or ""

    if not caption:
        return None

    # Check if this looks like an event post
    if not _is_event_post(caption):
        return None

    # Extract event details from caption
    title = _extract_title(caption, handle)
    event_date = _extract_date(caption)
    event_time = _extract_time(caption)
    price = _extract_price(caption)

    if not event_date:
        # No date found, skip this post
        return None

    # Combine date and time
    if event_time:
        start_time = datetime.combine(event_date.date(), event_time)
    else:
        # Default to 8 PM for evening events
        start_time = datetime.combine(event_date.date(), datetime.strptime("20:00", "%H:%M").time())

    # Build venue from handle
    venue = Venue(
        name=handle.replace("_", " ").title(),
        city=default_city,
        state=default_state,
        instagram_handle=f"@{handle}"
    )

    # Get image
    image_url = (
        post.get("display_url") or
        post.get("image_url") or
        post.get("thumbnail_url")
    )

    return Event(
        source="instagram",
        source_id=post.get("id") or f"ig_{handle}_{hash(caption)}"[:16],
        source_url=post.get("permalink") or f"https://instagram.com/{handle}",
        title=title,
        description=caption[:500],  # Truncate long captions
        start_time=start_time,
        venue=venue,
        price=price,
        image_url=image_url,
        confidence=0.7  # Lower confidence for scraped events
    )


def _is_event_post(caption: str) -> bool:
    """Check if a post looks like an event announcement."""
    caption_lower = caption.lower()

    # Event keywords
    event_keywords = [
        "tonight", "tomorrow", "this friday", "this saturday",
        "this sunday", "live music", "live band", "concert",
        "show", "tickets", "doors open", "doors @", "cover",
        "admission", "free entry", "no cover", "rsvp",
        "dj", "performing", "featuring", "presents"
    ]

    # Check for keywords
    has_keyword = any(kw in caption_lower for kw in event_keywords)

    # Check for date patterns
    date_patterns = [
        r'\d{1,2}/\d{1,2}',  # 1/15, 01/15
        r'\d{1,2}\.\d{1,2}',  # 1.15
        r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}',
        r'\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
    ]
    has_date = any(re.search(p, caption_lower) for p in date_patterns)

    # Check for time patterns
    time_patterns = [
        r'\d{1,2}\s*(am|pm)',  # 8pm, 8 pm
        r'\d{1,2}:\d{2}',  # 8:00
        r'doors\s*@?\s*\d',  # doors @ 7
    ]
    has_time = any(re.search(p, caption_lower) for p in time_patterns)

    # Must have either keyword or both date and time
    return has_keyword or (has_date and has_time)


def _extract_title(caption: str, handle: str) -> str:
    """Extract event title from caption."""
    # Try first line
    first_line = caption.split("\n")[0].strip()

    # Remove emojis and clean up
    first_line = re.sub(r'[^\w\s\-\'\"@#]', '', first_line)
    first_line = first_line.strip()

    if len(first_line) > 10 and len(first_line) < 100:
        return first_line

    # Fall back to venue name + "Event"
    return f"Event at {handle.replace('_', ' ').title()}"


def _extract_date(caption: str) -> Optional[datetime]:
    """Extract event date from caption."""
    from dateutil import parser

    caption_lower = caption.lower()

    # Try common date patterns
    patterns = [
        r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?',  # 1/15 or 1/15/25
        r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{1,2})(?:\w{0,2})?,?\s*(\d{4})?',
        r'(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*,?\s*(\d{4})?',
    ]

    for pattern in patterns:
        match = re.search(pattern, caption_lower)
        if match:
            try:
                date_str = match.group(0)
                parsed = parser.parse(date_str, fuzzy=True)

                # If year not specified, assume this year or next
                if parsed.year < 2020:
                    now = datetime.now()
                    parsed = parsed.replace(year=now.year)
                    if parsed < now - timedelta(days=30):
                        parsed = parsed.replace(year=now.year + 1)

                return parsed
            except (ValueError, TypeError, OverflowError):
                continue

    # Check for relative dates
    now = datetime.now()
    if "tonight" in caption_lower or "today" in caption_lower:
        return now
    if "tomorrow" in caption_lower:
        return now + timedelta(days=1)
    if "this friday" in caption_lower:
        days_until = (4 - now.weekday()) % 7
        return now + timedelta(days=days_until)
    if "this saturday" in caption_lower:
        days_until = (5 - now.weekday()) % 7
        return now + timedelta(days=days_until)
    if "this sunday" in caption_lower:
        days_until = (6 - now.weekday()) % 7
        return now + timedelta(days=days_until)

    return None


def _extract_time(caption: str) -> Optional[datetime]:
    """Extract event time from caption."""
    caption_lower = caption.lower()

    # Time patterns
    patterns = [
        r'(\d{1,2}):(\d{2})\s*(am|pm)?',  # 8:00 pm
        r'(\d{1,2})\s*(am|pm)',  # 8pm
        r'doors\s*@?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?',  # doors @ 7
    ]

    for pattern in patterns:
        match = re.search(pattern, caption_lower)
        if match:
            groups = match.groups()
            try:
                hour = int(groups[0])
                minute = int(groups[1]) if groups[1] and groups[1].isdigit() else 0

                # Handle AM/PM
                period = None
                for g in groups:
                    if g and g in ('am', 'pm'):
                        period = g
                        break

                if period == 'pm' and hour < 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0

                return datetime.strptime(f"{hour}:{minute:02d}", "%H:%M")
            except (ValueError, TypeError, IndexError):
                continue

    return None


def _extract_price(caption: str) -> Optional[str]:
    """Extract price from caption."""
    caption_lower = caption.lower()

    # Check for free
    if any(kw in caption_lower for kw in ["free", "no cover", "free entry"]):
        return "Free"

    # Price patterns
    patterns = [
        r'\$(\d+)',  # $10
        r'(\d+)\s*dollars',  # 10 dollars
        r'cover:?\s*\$?(\d+)',  # cover: $10
        r'admission:?\s*\$?(\d+)',  # admission: 10
    ]

    for pattern in patterns:
        match = re.search(pattern, caption_lower)
        if match:
            return f"${match.group(1)}"

    return None


# Richmond area music venue handles (defaults)
RICHMOND_MUSIC_VENUES = [
    "thecamelrva",
    "thebroadberry",
    "thenationalva",
    "themomentumrva",
    "canalhallrva",
    "thehotfuncrva",
    "richmondjazzva",
    "brownsissland",
    "thebyrdrva"
]
