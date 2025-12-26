"""Tests for event data models."""

from datetime import datetime

import pytest

from servers.event_mcp.models import Event, Venue


class TestVenue:
    """Tests for Venue model."""

    def test_venue_creation(self):
        """Test basic venue creation."""
        venue = Venue(
            name="The Camel",
            city="Richmond",
            state="VA",
        )
        assert venue.name == "The Camel"
        assert venue.city == "Richmond"
        assert venue.state == "VA"
        assert venue.address is None
        assert venue.instagram_handle is None

    def test_venue_with_all_fields(self):
        """Test venue with all optional fields."""
        venue = Venue(
            name="The Camel",
            address="1621 W Broad St",
            city="Richmond",
            state="VA",
            instagram_handle="@thecamelrva",
        )
        assert venue.address == "1621 W Broad St"
        assert venue.instagram_handle == "@thecamelrva"


class TestEvent:
    """Tests for Event model."""

    def test_event_creation(self, sample_venue: Venue):
        """Test basic event creation."""
        event = Event(
            source="serpapi",
            source_id="test-123",
            title="Reggae Night",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=sample_venue,
        )
        assert event.source == "serpapi"
        assert event.title == "Reggae Night"
        assert event.venue.name == "The Camel"

    def test_event_unique_key_generation(self, sample_venue: Venue):
        """Test that unique_key is generated consistently."""
        event1 = Event(
            source="serpapi",
            source_id="123",
            title="Reggae Night",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=sample_venue,
        )
        event2 = Event(
            source="serpapi",
            source_id="123",
            title="Reggae Night",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=sample_venue,
        )
        # Same inputs should generate same key
        assert event1.unique_key == event2.unique_key

    def test_event_unique_key_differs_for_different_events(self, sample_venue: Venue):
        """Test that different events have different unique keys."""
        event1 = Event(
            source="serpapi",
            source_id="123",
            title="Reggae Night",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=sample_venue,
        )
        event2 = Event(
            source="serpapi",
            source_id="456",
            title="Jazz Night",
            start_time=datetime(2025, 1, 18, 20, 0),
            venue=sample_venue,
        )
        assert event1.unique_key != event2.unique_key

    def test_event_default_values(self, sample_venue: Venue):
        """Test event default values."""
        event = Event(
            source="serpapi",
            source_id="test",
            title="Test Event",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=sample_venue,
        )
        assert event.description is None
        assert event.end_time is None
        assert event.category is None
        assert event.subcategories == []
        assert event.price is None
        assert event.confidence == 1.0
        assert event.all_day is False

    def test_event_with_all_fields(self, sample_venue: Venue):
        """Test event with all optional fields."""
        event = Event(
            source="serpapi",
            source_id="test",
            title="Reggae Night",
            description="Weekly reggae showcase",
            start_time=datetime(2025, 1, 17, 21, 0),
            end_time=datetime(2025, 1, 18, 2, 0),
            venue=sample_venue,
            category="music",
            subcategories=["reggae", "live_music"],
            price="$12",
            price_min=12.0,
            price_max=12.0,
            ticket_url="https://example.com/tickets",
            image_url="https://example.com/image.jpg",
            confidence=0.95,
            is_verified=True,
        )
        assert event.description == "Weekly reggae showcase"
        assert event.end_time is not None
        assert event.category == "music"
        assert "reggae" in event.subcategories
        assert event.confidence == 0.95

    def test_event_merge_with(self, sample_venue: Venue):
        """Test merging two events."""
        event1 = Event(
            source="serpapi",
            source_id="123",
            title="Reggae Night",
            description="Weekly reggae showcase",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=sample_venue,
            price="$12",
        )
        event2 = Event(
            source="instagram",
            source_id="456",
            title="REGGAE NIGHT",
            description=None,  # Missing description
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=sample_venue,
            ticket_url="https://tickets.com",  # Has ticket URL
        )

        merged = event1.merge_with(event2)

        # Should keep longer description from event1
        assert merged.description == "Weekly reggae showcase"
        # Should get ticket_url from event2
        assert merged.ticket_url == "https://tickets.com"
        # Should keep price from event1
        assert merged.price == "$12"


class TestEventCategories:
    """Tests for event category handling."""

    def test_valid_categories(self, sample_venue: Venue):
        """Test that valid categories are accepted."""
        for category in ["music", "food_drink", "arts", "nightlife", "community"]:
            event = Event(
                source="test",
                source_id="1",
                title="Test",
                start_time=datetime.now(),
                venue=sample_venue,
                category=category,
            )
            assert event.category == category

    def test_subcategories(self, sample_venue: Venue):
        """Test subcategory handling."""
        event = Event(
            source="test",
            source_id="1",
            title="Reggae Night",
            start_time=datetime.now(),
            venue=sample_venue,
            category="music",
            subcategories=["reggae", "live_music", "dub"],
        )
        assert len(event.subcategories) == 3
        assert "reggae" in event.subcategories
