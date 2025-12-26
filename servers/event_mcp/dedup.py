"""
Fuzzy deduplication algorithm for events.

Uses weighted similarity matching:
- Title: 50% weight
- Venue: 35% weight
- Time: 15% weight

Threshold: 0.75 (75% similarity = duplicate)
"""

from rapidfuzz import fuzz
from datetime import timedelta
from typing import Optional
import re

from .models import Event, DedupeResult, DuplicateMatch


# Configurable weights
WEIGHTS = {
    "title": 0.50,
    "venue": 0.35,
    "time": 0.15
}

# Similarity threshold for duplicate detection
THRESHOLD = 0.75

# Time window for considering events as potential duplicates (2 hours)
TIME_WINDOW_SECONDS = 7200


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    if not text:
        return ""

    # Lowercase
    text = text.lower().strip()

    # Remove common prefixes
    prefixes = ["live:", "live -", "tonight:", "this week:", "event:"]
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    # Remove common suffixes
    suffixes = ["- live", "live!", "tonight!", "@ "]
    for suffix in suffixes:
        if text.endswith(suffix):
            text = text[:-len(suffix)].strip()

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)

    return text


def normalize_venue_name(name: str) -> str:
    """Normalize venue name for comparison."""
    if not name:
        return ""

    name = name.lower().strip()

    # Remove common venue type suffixes
    suffixes = [
        " bar", " pub", " club", " lounge", " theater", " theatre",
        " hall", " venue", " room", " stage", " arena", " center",
        " brewery", " brewing", " taproom", " restaurant", " grill"
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()

    # Remove "the" prefix
    if name.startswith("the "):
        name = name[4:]

    return name


def calculate_title_similarity(e1: Event, e2: Event) -> float:
    """Calculate title similarity (0-1)."""
    t1 = normalize_text(e1.title)
    t2 = normalize_text(e2.title)

    if not t1 or not t2:
        return 0.0

    # Use token_sort_ratio for word order independence
    return fuzz.token_sort_ratio(t1, t2) / 100


def calculate_venue_similarity(e1: Event, e2: Event) -> float:
    """Calculate venue similarity (0-1)."""
    v1 = normalize_venue_name(e1.venue.name)
    v2 = normalize_venue_name(e2.venue.name)

    if not v1 or not v2:
        return 0.0

    # Check for exact Instagram handle match (most reliable)
    if (e1.venue.instagram_handle and e2.venue.instagram_handle and
            e1.venue.instagram_handle.lower() == e2.venue.instagram_handle.lower()):
        return 1.0

    # Check for same city (boost if matching)
    same_city = (
        e1.venue.city.lower() == e2.venue.city.lower() and
        e1.venue.state.lower() == e2.venue.state.lower()
    )

    name_similarity = fuzz.ratio(v1, v2) / 100

    # Boost score if same city
    if same_city:
        name_similarity = min(1.0, name_similarity * 1.1)

    return name_similarity


def calculate_time_similarity(e1: Event, e2: Event) -> float:
    """Calculate time similarity (0-1)."""
    time_diff = abs((e1.start_time - e2.start_time).total_seconds())

    # If same day, high similarity regardless of exact time
    if e1.start_time.date() == e2.start_time.date():
        # Full score if within 30 minutes
        if time_diff <= 1800:
            return 1.0
        # Linear decay up to 4 hours
        elif time_diff <= 14400:
            return 1.0 - (time_diff - 1800) / 12600
        else:
            return 0.5  # Same day bonus

    # Different days - check within time window
    if time_diff <= TIME_WINDOW_SECONDS:
        return 1.0 - (time_diff / TIME_WINDOW_SECONDS)

    return 0.0


def calculate_similarity(e1: Event, e2: Event) -> tuple[float, float, float, float]:
    """
    Calculate weighted similarity between two events.

    Returns: (total_similarity, title_sim, venue_sim, time_sim)
    """
    title_sim = calculate_title_similarity(e1, e2)
    venue_sim = calculate_venue_similarity(e1, e2)
    time_sim = calculate_time_similarity(e1, e2)

    total = (
        WEIGHTS["title"] * title_sim +
        WEIGHTS["venue"] * venue_sim +
        WEIGHTS["time"] * time_sim
    )

    return (total, title_sim, venue_sim, time_sim)


def choose_primary_event(e1: Event, e2: Event) -> tuple[Event, Event]:
    """
    Choose which event to keep as primary.

    Priority:
    1. Events with more complete data
    2. Events from more reliable sources
    3. Earlier fetch time (first seen)

    Returns: (primary_event, secondary_event)
    """
    # Source priority
    source_priority = {
        "predicthq": 4,
        "serpapi": 3,
        "instagram": 2,
        "web": 1
    }

    # Score completeness
    def completeness_score(e: Event) -> int:
        score = 0
        if e.description:
            score += 2
        if e.price:
            score += 1
        if e.ticket_url:
            score += 1
        if e.image_url:
            score += 1
        return score

    e1_source_priority = source_priority.get(e1.source, 0)
    e2_source_priority = source_priority.get(e2.source, 0)

    e1_completeness = completeness_score(e1)
    e2_completeness = completeness_score(e2)

    # Compare: source priority first, then completeness
    if e1_source_priority > e2_source_priority:
        return (e1, e2)
    elif e2_source_priority > e1_source_priority:
        return (e2, e1)
    elif e1_completeness >= e2_completeness:
        return (e1, e2)
    else:
        return (e2, e1)


def _find_duplicates(
    event: Event,
    candidates: list[tuple[int, Event]],
    threshold: float
) -> list[tuple[int, Event, float, float, float, float]]:
    """
    Find all duplicates of an event from candidate list.

    Returns list of (index, event, total_sim, title_sim, venue_sim, time_sim).
    """
    duplicates = []
    for j, other in candidates:
        total_sim, title_sim, venue_sim, time_sim = calculate_similarity(event, other)
        if total_sim >= threshold:
            duplicates.append((j, other, total_sim, title_sim, venue_sim, time_sim))
    return duplicates


def _merge_duplicates(
    primary: Event,
    duplicates: list[tuple[int, Event, float, float, float, float]]
) -> tuple[Event, list[DuplicateMatch]]:
    """
    Merge all duplicates into a single primary event.

    Returns (merged_event, audit_trail_entries).
    """
    audit_trail: list[DuplicateMatch] = []

    for _, dup, total_sim, title_sim, venue_sim, time_sim in duplicates:
        primary, secondary = choose_primary_event(primary, dup)
        primary = primary.merge_with(secondary)

        audit_trail.append(DuplicateMatch(
            kept_event_id=primary.unique_key,
            merged_event_id=secondary.unique_key,
            similarity_score=total_sim,
            title_similarity=title_sim,
            venue_similarity=venue_sim,
            time_similarity=time_sim,
            reason=f"Merged '{secondary.title}' ({secondary.source}) into '{primary.title}' ({primary.source})"
        ))

    return primary, audit_trail


def deduplicate(
    events: list[Event],
    threshold: float = THRESHOLD,
    weights: Optional[dict] = None
) -> DedupeResult:
    """
    Deduplicate a list of events using fuzzy matching.

    Args:
        events: List of events to deduplicate
        threshold: Similarity threshold (0-1)
        weights: Optional custom weights dict

    Returns:
        DedupeResult with deduplicated events and audit trail
    """
    if not events:
        return DedupeResult(events=[], original_count=0, duplicates_removed=0)

    if weights:
        global WEIGHTS
        WEIGHTS = weights

    original_count = len(events)
    merged_indices: set[int] = set()
    result_events: list[Event] = []
    audit_trail: list[DuplicateMatch] = []

    for i, event in enumerate(events):
        if i in merged_indices:
            continue

        # Get candidates (unmerged events after this one)
        candidates = [
            (j, events[j]) for j in range(i + 1, len(events))
            if j not in merged_indices
        ]

        duplicates = _find_duplicates(event, candidates, threshold)

        if not duplicates:
            result_events.append(event)
            continue

        # Mark duplicates as merged
        for j, *_ in duplicates:
            merged_indices.add(j)

        # Merge and record audit trail
        merged_event, trail = _merge_duplicates(event, duplicates)
        result_events.append(merged_event)
        audit_trail.extend(trail)

    return DedupeResult(
        events=result_events,
        original_count=original_count,
        duplicates_removed=original_count - len(result_events),
        audit_trail=audit_trail
    )


def format_audit_summary(result: DedupeResult) -> str:
    """Format audit trail as human-readable summary."""
    if not result.audit_trail:
        return "No duplicates found."

    lines = [
        f"Deduplication Summary:",
        f"  Original events: {result.original_count}",
        f"  Duplicates removed: {result.duplicates_removed}",
        f"  Final events: {len(result.events)}",
        f"  Dedup rate: {result.dedup_rate:.1f}%",
        "",
        "Merged events:"
    ]

    for match in result.audit_trail:
        lines.append(
            f"  - {match.reason} "
            f"(similarity: {match.similarity_score:.0%})"
        )

    return "\n".join(lines)
