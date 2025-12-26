"""Tests for Firecrawl event scraping."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from servers.event_mcp.sources.firecrawl import (
    fetch_firecrawl_events,
    crawl_venue_site,
    _parse_events_from_markdown,
    _extract_domain_name,
    _create_event_from_match,
)
from servers.event_mcp.models import Venue


class TestExtractDomainName:
    """Tests for domain name extraction."""

    def test_simple_domain(self):
        assert _extract_domain_name("https://thenationalva.com/events") == "Thenationalva"

    def test_www_domain(self):
        assert _extract_domain_name("https://www.broadberry.com") == "Broadberry"

    def test_hyphenated_domain(self):
        assert _extract_domain_name("https://canal-club.com") == "Canal Club"


class TestParseEventsFromMarkdown:
    """Tests for markdown event parsing."""

    @pytest.fixture
    def sample_venue(self) -> Venue:
        return Venue(name="Test Venue", city="Richmond", state="VA")

    def test_header_pattern(self, sample_venue: Venue):
        """Test parsing events with header format."""
        markdown = """
## Live Jazz Night
**Date**: January 15, 2025
**Time**: 8:00 PM
"""
        events = _parse_events_from_markdown(
            markdown, "Test Venue", "Richmond", "VA", "https://test.com"
        )
        assert len(events) >= 1
        assert any("Jazz" in e.title for e in events)

    def test_list_pattern(self, sample_venue: Venue):
        """Test parsing events with list format."""
        markdown = """
- **Reggae Friday** - January 17
- **Rock Saturday** - January 18
- **Blues Sunday** - January 19
"""
        events = _parse_events_from_markdown(
            markdown, "Test Venue", "Richmond", "VA", "https://test.com"
        )
        assert len(events) >= 1

    def test_date_first_pattern(self, sample_venue: Venue):
        """Test parsing events with date-first format."""
        markdown = """
January 20 - Comedy Night
January 21 - Open Mic
"""
        events = _parse_events_from_markdown(
            markdown, "Test Venue", "Richmond", "VA", "https://test.com"
        )
        assert len(events) >= 1

    def test_empty_markdown(self, sample_venue: Venue):
        """Test handling of empty markdown."""
        events = _parse_events_from_markdown(
            "", "Test Venue", "Richmond", "VA", "https://test.com"
        )
        assert events == []

    def test_no_events_in_markdown(self, sample_venue: Venue):
        """Test markdown with no event patterns."""
        markdown = "Just some regular text without any events."
        events = _parse_events_from_markdown(
            markdown, "Test Venue", "Richmond", "VA", "https://test.com"
        )
        assert events == []


class TestCreateEventFromMatch:
    """Tests for event creation from regex matches."""

    def test_valid_event(self):
        """Test creating a valid event."""
        venue = Venue(name="The Camel", city="Richmond", state="VA")
        seen = set()

        event = _create_event_from_match(
            "Reggae Night",
            "January 20, 2025",
            venue,
            "https://thecamel.com",
            seen
        )

        assert event is not None
        assert event.title == "Reggae Night"
        assert event.source == "firecrawl"
        assert event.venue.name == "The Camel"

    def test_duplicate_prevention(self):
        """Test that duplicates are prevented."""
        venue = Venue(name="The Camel", city="Richmond", state="VA")
        seen = set()

        event1 = _create_event_from_match("Reggae Night", "Jan 20", venue, "https://test.com", seen)
        event2 = _create_event_from_match("Reggae Night", "Jan 20", venue, "https://test.com", seen)

        assert event1 is not None
        assert event2 is None  # Duplicate should return None

    def test_short_title_rejected(self):
        """Test that very short titles are rejected."""
        venue = Venue(name="The Camel", city="Richmond", state="VA")
        seen = set()

        event = _create_event_from_match("Hi", "Jan 20", venue, "https://test.com", seen)
        assert event is None

    def test_title_cleaning(self):
        """Test that titles are cleaned properly."""
        venue = Venue(name="The Camel", city="Richmond", state="VA")
        seen = set()

        event = _create_event_from_match(
            "**  Reggae Night  **",
            "January 20, 2025",
            venue,
            "https://test.com",
            seen
        )

        assert event is not None
        assert event.title == "Reggae Night"


class TestFetchFirecrawlEvents:
    """Tests for the main fetch function."""

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        """Test behavior when API key is not set."""
        with patch.dict("os.environ", {}, clear=True):
            events, stats = await fetch_firecrawl_events(
                "https://test.com/events"
            )

        assert events == []
        assert stats.status == "error"
        assert "FIRECRAWL_API_KEY" in stats.error_message

    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        """Test successful event fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "data": {
                "markdown": "## Concert Tonight\n**Date**: January 15, 2025",
                "metadata": {"title": "Test Venue | Events"}
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value.post = AsyncMock(return_value=mock_response)

                events, stats = await fetch_firecrawl_events(
                    "https://test.com/events",
                    venue_name="Test Venue"
                )

        assert stats.status == "success"

    @pytest.mark.asyncio
    async def test_api_error(self):
        """Test handling of API errors."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error": "Rate limited"
        }
        mock_response.raise_for_status = MagicMock()

        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value.post = AsyncMock(return_value=mock_response)

                events, stats = await fetch_firecrawl_events(
                    "https://test.com/events"
                )

        assert events == []
        assert stats.status == "error"
        assert "Rate limited" in stats.error_message


class TestCrawlVenueSite:
    """Tests for the crawl function."""

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        """Test behavior when API key is not set."""
        with patch.dict("os.environ", {}, clear=True):
            events, stats = await crawl_venue_site("https://test.com")

        assert events == []
        assert stats.status == "error"
        assert "FIRECRAWL_API_KEY" in stats.error_message
