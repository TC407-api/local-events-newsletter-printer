"""Health monitoring for event sources."""

from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger()


class HealthMonitor:
    """Monitor and report health status of event sources.

    Tracks success/failure rates and provides health status for
    circuit breaker decisions and user feedback.
    """

    def __init__(self):
        """Initialize health monitor with empty status."""
        self.status: dict[str, dict[str, Any]] = {}

    def record_success(self, source: str, event_count: int) -> None:
        """Record a successful fetch from a source.

        Args:
            source: Name of the event source
            event_count: Number of events fetched
        """
        self.status[source] = {
            "healthy": True,
            "last_check": datetime.now().isoformat(),
            "event_count": event_count,
            "consecutive_failures": 0,
            "last_error": None,
        }
        logger.debug(
            "source_healthy",
            source=source,
            event_count=event_count,
        )

    def record_failure(self, source: str, error: str) -> None:
        """Record a failed fetch from a source.

        Args:
            source: Name of the event source
            error: Error message describing the failure
        """
        current = self.status.get(source, {"consecutive_failures": 0})
        consecutive = current.get("consecutive_failures", 0) + 1

        self.status[source] = {
            "healthy": False,
            "last_check": datetime.now().isoformat(),
            "event_count": 0,
            "consecutive_failures": consecutive,
            "last_error": error,
        }
        logger.warning(
            "source_unhealthy",
            source=source,
            consecutive_failures=consecutive,
            error=error,
        )

    def is_healthy(self, source: str) -> bool:
        """Check if a source is currently healthy.

        Args:
            source: Name of the event source

        Returns:
            True if source is healthy or unknown
        """
        return self.status.get(source, {}).get("healthy", True)

    def get_source_status(self, source: str) -> dict[str, Any] | None:
        """Get detailed status for a specific source.

        Args:
            source: Name of the event source

        Returns:
            Status dict or None if source not tracked
        """
        return self.status.get(source)

    def get_status(self) -> dict[str, Any]:
        """Get full health status report.

        Returns:
            Dict with timestamp and all source statuses
        """
        healthy_count = sum(1 for s in self.status.values() if s.get("healthy", False))
        total_count = len(self.status)

        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "healthy": healthy_count,
                "unhealthy": total_count - healthy_count,
                "total": total_count,
            },
            "sources": self.status,
        }

    def get_healthy_sources(self) -> list[str]:
        """Get list of currently healthy sources.

        Returns:
            List of healthy source names
        """
        return [name for name, status in self.status.items() if status.get("healthy", False)]

    def get_unhealthy_sources(self) -> list[str]:
        """Get list of currently unhealthy sources.

        Returns:
            List of unhealthy source names
        """
        return [
            name for name, status in self.status.items() if not status.get("healthy", True)
        ]

    def reset(self, source: str | None = None) -> None:
        """Reset health status.

        Args:
            source: Specific source to reset, or None to reset all
        """
        if source:
            if source in self.status:
                del self.status[source]
        else:
            self.status.clear()
