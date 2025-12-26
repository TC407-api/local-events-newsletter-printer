"""
Configuration migrator for backwards compatibility.

Handles version migrations:
- v1 -> v2: Restructured sources format, added deduplication weights
"""

from typing import Any
import structlog

log = structlog.get_logger(__name__)

CURRENT_VERSION = 2


def migrate_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Migrate config from any version to current.

    Args:
        config: Raw config dict (may be any version)

    Returns:
        Config dict at CURRENT_VERSION
    """
    version = config.get("version", 1)

    if version == CURRENT_VERSION:
        return config

    log.info("migrating_config", from_version=version, to_version=CURRENT_VERSION)

    if version == 1:
        config = _migrate_v1_to_v2(config)

    config["version"] = CURRENT_VERSION
    return config


def _migrate_v1_to_v2(config: dict[str, Any]) -> dict[str, Any]:
    """
    Migrate v1 config to v2 format.

    Changes:
    - instagram_handles (list[str]) -> sources.instagram (list[dict])
    - web_urls (list[str]) -> sources.web (list[dict])
    - Added deduplication.weights
    - Added classification settings
    """
    migrated = config.copy()

    # Migrate flat instagram handles to structured format
    old_handles = config.get("instagram_handles", [])
    if old_handles and "sources" not in migrated:
        migrated["sources"] = {}

    if old_handles:
        migrated["sources"]["instagram"] = [
            {"handle": h, "name": _handle_to_name(h), "type": "venue"}
            for h in old_handles
        ]
        migrated.pop("instagram_handles", None)
        log.info("migrated_instagram_handles", count=len(old_handles))

    # Migrate flat web urls to structured format
    old_urls = config.get("web_urls", [])
    if old_urls:
        migrated["sources"]["web"] = [
            {"url": url, "name": _url_to_name(url)}
            for url in old_urls
        ]
        migrated.pop("web_urls", None)
        log.info("migrated_web_urls", count=len(old_urls))

    # Add default deduplication weights if missing
    if "deduplication" not in migrated:
        migrated["deduplication"] = {}

    if "weights" not in migrated["deduplication"]:
        migrated["deduplication"]["weights"] = {
            "title": 0.50,
            "venue": 0.35,
            "time": 0.15,
        }
        log.info("added_default_dedup_weights")

    # Add default threshold if missing
    if "threshold" not in migrated["deduplication"]:
        migrated["deduplication"]["threshold"] = 0.75

    # Add classification settings if missing
    if "classification" not in migrated:
        migrated["classification"] = {
            "review_threshold": 0.7,
            "reggae_boost": True,
        }
        log.info("added_default_classification")

    # Ensure newsletter section exists
    if "newsletter" not in migrated:
        migrated["newsletter"] = {
            "name": "Local Events Newsletter",
            "tagline": "Your weekly guide to local events",
        }

    return migrated


def _handle_to_name(handle: str) -> str:
    """Convert Instagram handle to display name."""
    name = handle.lstrip("@")
    name = name.replace("_", " ").replace("rva", "").replace("va", "")
    return name.strip().title()


def _url_to_name(url: str) -> str:
    """Extract venue name from URL."""
    from urllib.parse import urlparse

    domain = urlparse(url).netloc
    domain = domain.replace("www.", "")
    name = domain.split(".")[0]
    return name.replace("-", " ").replace("_", " ").title()


def validate_config(config: dict[str, Any]) -> list[str]:
    """
    Validate config and return list of errors.

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    # Check required fields
    if "location" not in config:
        errors.append("Missing required field: location")
    elif "city" not in config.get("location", {}):
        errors.append("Missing required field: location.city")

    # Check version
    version = config.get("version", 1)
    if version > CURRENT_VERSION:
        errors.append(
            f"Config version {version} is newer than supported version {CURRENT_VERSION}"
        )

    # Check deduplication threshold range
    threshold = config.get("deduplication", {}).get("threshold", 0.75)
    if not 0 < threshold <= 1:
        errors.append(f"Invalid deduplication threshold: {threshold} (must be 0-1)")

    # Check weights sum to 1
    weights = config.get("deduplication", {}).get("weights", {})
    if weights:
        total = sum(weights.values())
        if abs(total - 1.0) > 0.01:
            errors.append(f"Deduplication weights must sum to 1.0, got {total}")

    return errors


def get_default_config() -> dict[str, Any]:
    """Return default config for new installations."""
    return {
        "version": CURRENT_VERSION,
        "newsletter": {
            "name": "Local Events Newsletter",
            "tagline": "Your weekly guide to local events",
        },
        "location": {
            "city": "Richmond",
            "state": "VA",
            "radius_miles": 50,
        },
        "categories": ["music", "food_drink", "arts"],
        "sources": {
            "instagram": [],
            "web": [],
        },
        "deduplication": {
            "threshold": 0.75,
            "weights": {
                "title": 0.50,
                "venue": 0.35,
                "time": 0.15,
            },
        },
        "output": {
            "format": "markdown",
            "template": "default",
            "include_images": False,
            "max_events_per_category": 15,
            "highlight_count": 3,
        },
        "classification": {
            "review_threshold": 0.7,
            "reggae_boost": True,
        },
    }
