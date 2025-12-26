"""Tests for event deduplication logic."""

from datetime import datetime

import pytest

from servers.event_mcp.dedup import (
    THRESHOLD,
    WEIGHTS,
    calculate_similarity,
    deduplicate,
    normalize_text,
)
from servers.event_mcp.models import Event, Venue


class TestNormalization:
    """Tests for text normalization."""

    def test_removes_live_prefix(self):
        """Test removal of 'Live:' prefix."""
        assert "concert tonight" in normalize_text("Live: Concert Tonight").lower()

    def test_removes_tonight_prefix(self):
        """Test removal of 'TONIGHT:' prefix."""
        assert "jazz show" in normalize_text("TONIGHT: Jazz Show").lower()

    def test_collapses_whitespace(self):
        """Test whitespace collapse."""
        result = normalize_text("  Multiple   Spaces  ")
        assert "  " not in result
        assert result.strip() == result

    def test_lowercase(self):
        """Test lowercase conversion."""
        result = normalize_text("UPPERCASE TEXT")
        assert result == result.lower()

    def test_removes_special_characters(self):
        """Test handling of special characters."""
        result = normalize_text("Event @ The Venue!")
        assert result  # Should not be empty

    def test_empty_string(self):
        """Test empty string handling."""
        result = normalize_text("")
        assert result == ""

    def test_none_handling(self):
        """Test None input handling."""
        result = normalize_text(None)
        assert result == ""


class TestWeights:
    """Tests for similarity weights configuration."""

    def test_weights_sum_to_one(self):
        """Weights should sum to 1.0 for proper scoring."""
        assert abs(sum(WEIGHTS.values()) - 1.0) < 0.001

    def test_title_weight_highest(self):
        """Title should have the highest weight."""
        assert WEIGHTS["title"] > WEIGHTS["venue"]
        assert WEIGHTS["title"] > WEIGHTS["time"]

    def test_expected_weight_values(self):
        """Verify expected weight values."""
        assert WEIGHTS["title"] == 0.50
        assert WEIGHTS["venue"] == 0.35
        assert WEIGHTS["time"] == 0.15


class TestSimilarity:
    """Tests for similarity calculation."""

    @pytest.fixture
    def base_venue(self) -> Venue:
        return Venue(name="The Camel", city="Richmond", state="VA")

    def test_identical_events_score_one(self, base_venue: Venue):
        """Identical events should have similarity of 1.0."""
        event = Event(
            source="serpapi",
            source_id="1",
            title="Reggae Night",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=base_venue,
        )
        total, title, venue, time = calculate_similarity(event, event)
        assert total == 1.0

    def test_similar_titles_high_score(self, base_venue: Venue):
        """Similar titles should produce high similarity."""
        event1 = Event(
            source="serpapi",
            source_id="1",
            title="Reggae Night at The Camel",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=base_venue,
        )
        event2 = Event(
            source="instagram",
            source_id="2",
            title="REGGAE NIGHT @ The Camel",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=base_venue,
        )
        total, _, _, _ = calculate_similarity(event1, event2)
        assert total >= THRESHOLD

    def test_different_titles_low_score(self, base_venue: Venue):
        """Different titles should produce low similarity."""
        event1 = Event(
            source="serpapi",
            source_id="1",
            title="Reggae Night",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=base_venue,
        )
        event2 = Event(
            source="serpapi",
            source_id="2",
            title="Jazz Brunch",
            start_time=datetime(2025, 1, 19, 11, 0),
            venue=Venue(name="Lemaire", city="Richmond", state="VA"),
        )
        total, _, _, _ = calculate_similarity(event1, event2)
        assert total < THRESHOLD

    def test_same_venue_boosts_score(self, base_venue: Venue):
        """Same venue should boost similarity score."""
        event1 = Event(
            source="serpapi",
            source_id="1",
            title="Concert A",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=base_venue,
        )
        event2_same_venue = Event(
            source="serpapi",
            source_id="2",
            title="Concert B",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=base_venue,
        )
        event2_diff_venue = Event(
            source="serpapi",
            source_id="3",
            title="Concert B",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=Venue(name="Different Venue", city="Richmond", state="VA"),
        )

        total_same, _, _, _ = calculate_similarity(event1, event2_same_venue)
        total_diff, _, _, _ = calculate_similarity(event1, event2_diff_venue)

        assert total_same > total_diff

    def test_time_proximity_affects_score(self, base_venue: Venue):
        """Events at different times should have lower similarity."""
        event1 = Event(
            source="serpapi",
            source_id="1",
            title="Concert",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=base_venue,
        )
        event2_same_time = Event(
            source="serpapi",
            source_id="2",
            title="Concert",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=base_venue,
        )
        event2_diff_time = Event(
            source="serpapi",
            source_id="3",
            title="Concert",
            start_time=datetime(2025, 1, 18, 21, 0),  # Next day
            venue=base_venue,
        )

        total_same, _, _, _ = calculate_similarity(event1, event2_same_time)
        total_diff, _, _, _ = calculate_similarity(event1, event2_diff_time)

        assert total_same > total_diff


class TestDeduplication:
    """Tests for deduplication function."""

    def test_removes_duplicates(self, sample_events: list[Event]):
        """Should remove duplicate events."""
        result = deduplicate(sample_events)
        assert result.duplicates_removed >= 1
        assert len(result.events) < len(sample_events)

    def test_keeps_unique_events(self, sample_events: list[Event]):
        """Should keep unique events."""
        result = deduplicate(sample_events)
        titles = [e.title.lower() for e in result.events]
        # Jazz Brunch should be kept as it's unique
        assert any("jazz" in t for t in titles)

    def test_audit_trail_recorded(self, sample_events: list[Event]):
        """Should record audit trail of merges."""
        result = deduplicate(sample_events)
        if result.duplicates_removed > 0:
            assert len(result.audit_trail) > 0

    def test_empty_list(self):
        """Should handle empty event list."""
        result = deduplicate([])
        assert len(result.events) == 0
        assert result.duplicates_removed == 0

    def test_single_event(self, sample_venue: Venue):
        """Should handle single event."""
        events = [
            Event(
                source="test",
                source_id="1",
                title="Single Event",
                start_time=datetime.now(),
                venue=sample_venue,
            )
        ]
        result = deduplicate(events)
        assert len(result.events) == 1
        assert result.duplicates_removed == 0

    def test_merges_keep_best_data(self, sample_venue: Venue):
        """Merged events should keep the best data from each."""
        event1 = Event(
            source="serpapi",
            source_id="1",
            title="Reggae Night",
            description="Long detailed description of the event",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=sample_venue,
            price="$12",
        )
        event2 = Event(
            source="instagram",
            source_id="2",
            title="REGGAE NIGHT",
            description=None,
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=sample_venue,
            ticket_url="https://tickets.com",
        )

        result = deduplicate([event1, event2])

        assert len(result.events) == 1
        merged = result.events[0]
        # Should have description from event1
        assert merged.description is not None
        assert len(merged.description) > 10

    def test_configurable_threshold(self, sample_venue: Venue):
        """Should respect configurable threshold."""
        event1 = Event(
            source="serpapi",
            source_id="1",
            title="Concert A",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=sample_venue,
        )
        event2 = Event(
            source="serpapi",
            source_id="2",
            title="Concert B",
            start_time=datetime(2025, 1, 17, 21, 0),
            venue=sample_venue,
        )

        # With low threshold, might merge
        result_low = deduplicate([event1, event2], threshold=0.3)
        # With high threshold, should not merge
        result_high = deduplicate([event1, event2], threshold=0.99)

        assert len(result_high.events) >= len(result_low.events)
