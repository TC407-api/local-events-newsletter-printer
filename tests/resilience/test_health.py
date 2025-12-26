"""Tests for health monitoring."""

import pytest

from servers.event_mcp.resilience.health import HealthMonitor


class TestHealthMonitor:
    """Tests for HealthMonitor class."""

    @pytest.fixture
    def monitor(self) -> HealthMonitor:
        """Create a fresh health monitor."""
        return HealthMonitor()

    def test_record_success(self, monitor: HealthMonitor):
        """Should record successful source fetch."""
        monitor.record_success("serpapi", event_count=25)

        status = monitor.get_source_status("serpapi")
        assert status is not None
        assert status["healthy"] is True
        assert status["event_count"] == 25
        assert status["consecutive_failures"] == 0

    def test_record_failure(self, monitor: HealthMonitor):
        """Should record failed source fetch."""
        monitor.record_failure("instagram", error="Rate limited")

        status = monitor.get_source_status("instagram")
        assert status is not None
        assert status["healthy"] is False
        assert status["last_error"] == "Rate limited"
        assert status["consecutive_failures"] == 1

    def test_consecutive_failures_increment(self, monitor: HealthMonitor):
        """Should increment consecutive failures."""
        monitor.record_failure("serpapi", error="Error 1")
        monitor.record_failure("serpapi", error="Error 2")
        monitor.record_failure("serpapi", error="Error 3")

        status = monitor.get_source_status("serpapi")
        assert status["consecutive_failures"] == 3

    def test_success_resets_failures(self, monitor: HealthMonitor):
        """Success should reset consecutive failures."""
        monitor.record_failure("serpapi", error="Error")
        monitor.record_failure("serpapi", error="Error")
        monitor.record_success("serpapi", event_count=10)

        status = monitor.get_source_status("serpapi")
        assert status["consecutive_failures"] == 0
        assert status["healthy"] is True

    def test_is_healthy_unknown_source(self, monitor: HealthMonitor):
        """Unknown source should be considered healthy."""
        assert monitor.is_healthy("unknown_source") is True

    def test_is_healthy_after_failure(self, monitor: HealthMonitor):
        """Should report unhealthy after failure."""
        monitor.record_failure("serpapi", error="Error")
        assert monitor.is_healthy("serpapi") is False

    def test_get_healthy_sources(self, monitor: HealthMonitor):
        """Should return list of healthy sources."""
        monitor.record_success("serpapi", event_count=20)
        monitor.record_success("web", event_count=15)
        monitor.record_failure("instagram", error="Error")

        healthy = monitor.get_healthy_sources()
        assert "serpapi" in healthy
        assert "web" in healthy
        assert "instagram" not in healthy

    def test_get_unhealthy_sources(self, monitor: HealthMonitor):
        """Should return list of unhealthy sources."""
        monitor.record_success("serpapi", event_count=20)
        monitor.record_failure("instagram", error="Error")
        monitor.record_failure("web", error="Timeout")

        unhealthy = monitor.get_unhealthy_sources()
        assert "instagram" in unhealthy
        assert "web" in unhealthy
        assert "serpapi" not in unhealthy

    def test_get_status_summary(self, monitor: HealthMonitor):
        """Should return complete status summary."""
        monitor.record_success("serpapi", event_count=20)
        monitor.record_failure("instagram", error="Error")

        status = monitor.get_status()

        assert "timestamp" in status
        assert status["summary"]["healthy"] == 1
        assert status["summary"]["unhealthy"] == 1
        assert status["summary"]["total"] == 2
        assert "sources" in status

    def test_reset_specific_source(self, monitor: HealthMonitor):
        """Should reset specific source status."""
        monitor.record_success("serpapi", event_count=20)
        monitor.record_failure("instagram", error="Error")

        monitor.reset("instagram")

        assert monitor.get_source_status("instagram") is None
        assert monitor.get_source_status("serpapi") is not None

    def test_reset_all_sources(self, monitor: HealthMonitor):
        """Should reset all source statuses."""
        monitor.record_success("serpapi", event_count=20)
        monitor.record_failure("instagram", error="Error")

        monitor.reset()

        assert len(monitor.status) == 0
        assert monitor.get_source_status("serpapi") is None
        assert monitor.get_source_status("instagram") is None

    def test_status_includes_timestamp(self, monitor: HealthMonitor):
        """Status should include ISO format timestamp."""
        monitor.record_success("serpapi", event_count=10)

        status = monitor.get_source_status("serpapi")
        assert "last_check" in status
        # Should be ISO format
        assert "T" in status["last_check"]
