"""Shared pytest fixtures for newsletter plugin tests."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from servers.event_mcp.models import Event, Venue


@pytest.fixture
def sample_venue() -> Venue:
    """Provide a sample Richmond venue."""
    return Venue(
        name="The Camel",
        address="1621 W Broad St",
        city="Richmond",
        state="VA",
        instagram_handle="@thecamelrva",
    )


@pytest.fixture
def sample_venue_broadberry() -> Venue:
    """Provide The Broadberry venue."""
    return Venue(
        name="The Broadberry",
        address="2729 W Broad St",
        city="Richmond",
        state="VA",
        instagram_handle="@thebroadberry",
    )


@pytest.fixture
def sample_event(sample_venue: Venue) -> Event:
    """Provide a sample event."""
    return Event(
        source="serpapi",
        source_id="test-123",
        title="Reggae Night",
        description="Live reggae music featuring local bands",
        start_time=datetime(2025, 1, 17, 21, 0),
        venue=sample_venue,
        category="music",
        subcategories=["reggae", "live_music"],
        price="$12",
        confidence=0.95,
    )


@pytest.fixture
def sample_events(sample_venue: Venue, sample_venue_broadberry: Venue) -> list[Event]:
    """Provide a list of sample events including duplicates."""
    return [
        Event(
            source="serpapi",
            source_id="1",
            title="Reggae Night at The Camel",
            description="Weekly reggae showcase",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=sample_venue,
            category="music",
            price="$12",
        ),
        Event(
            source="instagram",
            source_id="2",
            title="REGGAE NIGHT @ The Camel",  # Duplicate with different formatting
            description=None,
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=sample_venue,
            category="music",
            price="$12",
        ),
        Event(
            source="serpapi",
            source_id="3",
            title="Jazz Brunch",
            description="Sunday jazz brunch with live quartet",
            start_time=datetime(2025, 1, 19, 11, 0),
            venue=Venue(name="Lemaire", city="Richmond", state="VA"),
            category="music",
            subcategories=["jazz"],
            price="$45",
        ),
        Event(
            source="web",
            source_id="4",
            title="Indie Rock Night",
            description="Local indie bands showcase",
            start_time=datetime(2025, 1, 18, 20, 0),
            venue=sample_venue_broadberry,
            category="music",
            price="$15",
        ),
    ]


@pytest.fixture
def fixtures_path() -> Path:
    """Provide path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def serpapi_response_fixture(fixtures_path: Path) -> dict:
    """Load sample SerpApi response from fixtures."""
    fixture_file = fixtures_path / "serpapi_response.json"
    if fixture_file.exists():
        return json.loads(fixture_file.read_text())
    return {
        "events_results": [
            {
                "title": "Jazz Concert",
                "date": {"start_date": "Jan 15, 2025", "when": "Friday, 8 PM"},
                "address": ["The National", "708 E Broad St", "Richmond, VA"],
                "link": "https://example.com/jazz",
                "description": "Live jazz performance",
            }
        ]
    }


@pytest.fixture
def newsletter_context(sample_events: list[Event]) -> dict:
    """Provide sample context for template rendering."""
    return {
        "newsletter_name": "RVA Live Music & Vibes",
        "date_range": "January 13-19, 2025",
        "intro": "Another week of great music and good vibes in Richmond!",
        "location": "Richmond, VA",
        "highlights": [
            {
                "title": "Reggae Night",
                "venue": {"name": "The Camel"},
                "day": "Friday",
                "date": "Jan 17",
                "time": "9 PM",
                "price": "$12",
                "description": "Weekly reggae showcase with local bands.",
                "ticket_url": "https://thecamel.com/tickets",
            }
        ],
        "music_events_by_day": [
            {
                "day": "Friday 1/17",
                "events": [
                    {
                        "title": "Reggae Night",
                        "time": "9 PM",
                        "price": "$12",
                        "venue": {"name": "The Camel"},
                        "is_reggae": True,
                    }
                ],
            }
        ],
        "food_events": [],
        "arts_events": [],
        "other_events": [],
    }
