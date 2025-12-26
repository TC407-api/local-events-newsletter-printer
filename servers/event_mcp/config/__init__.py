"""Configuration management for the event newsletter plugin."""

from .migrator import migrate_config, CURRENT_VERSION

__all__ = ["migrate_config", "CURRENT_VERSION"]
