"""
Pydantic models for event data structures.

These models define the core data types used throughout the plugin:
- Venue: Location information for events
- Event: Individual event with all metadata
- DedupeResult: Result of deduplication with audit trail
"""

from pydantic import BaseModel, Field, computed_field
from datetime import datetime
from typing import Optional
import hashlib


class Venue(BaseModel):
    """Represents a venue/location for events."""

    name: str
    address: Optional[str] = None
    city: str
    state: str
    zip_code: Optional[str] = None
    instagram_handle: Optional[str] = None
    website: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    venue_type: Optional[str] = None  # music_venue, bar, restaurant, etc.


class Event(BaseModel):
    """Represents a single event with all metadata."""

    # Source tracking
    source: str  # serpapi, predicthq, instagram, web
    source_id: str  # Original ID from source
    source_url: Optional[str] = None  # Link to original listing

    # Core event info
    title: str
    description: Optional[str] = None

    # Timing
    start_time: datetime
    end_time: Optional[datetime] = None
    all_day: bool = False

    # Location
    venue: Venue

    # Classification
    category: Optional[str] = None  # music, food_drink, arts, etc.
    subcategories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    # Details
    price: Optional[str] = None  # "Free", "$10-20", "TBD"
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    ticket_url: Optional[str] = None

    # Media
    image_url: Optional[str] = None
    images: list[str] = Field(default_factory=list)

    # Quality metrics
    confidence: float = 1.0  # Classification confidence (0-1)
    is_verified: bool = False  # Manually verified

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.now)

    @computed_field
    @property
    def unique_key(self) -> str:
        """Generate unique key for deduplication."""
        # Normalize title
        normalized_title = self.title.lower().strip()
        # Remove common prefixes/suffixes
        for prefix in ["live:", "live -", "tonight:"]:
            if normalized_title.startswith(prefix):
                normalized_title = normalized_title[len(prefix):].strip()

        # Normalize venue
        normalized_venue = self.venue.name.lower().strip()

        # Create key from title + date + venue
        date_str = self.start_time.strftime("%Y-%m-%d")
        key_string = f"{normalized_title}|{date_str}|{normalized_venue}"

        return hashlib.md5(key_string.encode()).hexdigest()

    def merge_with(self, other: "Event") -> "Event":
        """Merge another event into this one, keeping best data."""
        # Prefer longer descriptions
        if other.description and (not self.description or len(other.description) > len(self.description)):
            self.description = other.description

        # Prefer non-null values
        if not self.price and other.price:
            self.price = other.price
        if not self.ticket_url and other.ticket_url:
            self.ticket_url = other.ticket_url
        if not self.image_url and other.image_url:
            self.image_url = other.image_url

        # Merge images
        self.images = list(set(self.images + other.images))

        # Merge tags
        self.tags = list(set(self.tags + other.tags))

        return self


class DuplicateMatch(BaseModel):
    """Records a duplicate match for audit trail."""

    kept_event_id: str
    merged_event_id: str
    similarity_score: float
    title_similarity: float
    venue_similarity: float
    time_similarity: float
    reason: str


class DedupeResult(BaseModel):
    """Result of deduplication with audit trail."""

    events: list[Event]
    original_count: int
    duplicates_removed: int
    audit_trail: list[DuplicateMatch] = Field(default_factory=list)

    @computed_field
    @property
    def dedup_rate(self) -> float:
        """Percentage of events that were duplicates."""
        if self.original_count == 0:
            return 0.0
        return self.duplicates_removed / self.original_count * 100


class FetchStats(BaseModel):
    """Statistics from a fetch operation."""

    source: str
    count: int
    status: str  # success, error, skipped
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None


class FetchResult(BaseModel):
    """Result of fetching events from all sources."""

    events: list[Event]
    stats: list[FetchStats]
    total: int
    failed_sources: list[str] = Field(default_factory=list)


# Category taxonomy for Richmond music/food scene
CATEGORIES = {
    "music": {
        "name": "Music & Concerts",
        "subcategories": [
            "live_music",
            "concerts",
            "dj_sets",
            "open_mic",
            "reggae",
            "jazz",
            "rock",
            "hip_hop",
            "country",
            "classical"
        ]
    },
    "food_drink": {
        "name": "Food & Drink",
        "subcategories": [
            "tastings",
            "pop_ups",
            "food_trucks",
            "brewery_events",
            "wine_events",
            "restaurant_events",
            "cooking_classes"
        ]
    },
    "arts": {
        "name": "Arts & Culture",
        "subcategories": [
            "gallery_openings",
            "theater",
            "film",
            "museums",
            "comedy",
            "poetry"
        ]
    },
    "nightlife": {
        "name": "Nightlife",
        "subcategories": [
            "club_nights",
            "bar_events",
            "karaoke",
            "trivia",
            "dance_parties"
        ]
    },
    "community": {
        "name": "Community",
        "subcategories": [
            "festivals",
            "markets",
            "fundraisers",
            "meetups",
            "networking"
        ]
    },
    "sports": {
        "name": "Sports & Fitness",
        "subcategories": [
            "games",
            "races",
            "fitness_classes",
            "outdoor"
        ]
    },
    "family": {
        "name": "Family & Kids",
        "subcategories": [
            "kid_friendly",
            "educational",
            "outdoor_family"
        ]
    }
}
