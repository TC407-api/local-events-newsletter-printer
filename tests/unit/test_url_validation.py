"""Tests for URL validation and SSRF protection."""

import pytest
from unittest.mock import patch

from servers.event_mcp.sources.url_validator import (
    validate_url,
    validate_url_for_scraping,
    SSRFError,
    _domain_matches_whitelist,
    _is_blocked_ip,
    _parse_ip_address,
)


class TestValidateUrl:
    """Tests for the validate_url function."""

    # --- HTTPS Enforcement Tests ---

    def test_accepts_https_urls(self):
        """HTTPS URLs should be accepted."""
        url = validate_url("https://example.com/events")
        assert url == "https://example.com/events"

    def test_rejects_http_when_https_required(self):
        """HTTP URLs should be rejected when require_https=True."""
        with pytest.raises(SSRFError) as exc:
            validate_url("http://example.com/events", require_https=True)
        assert "Only HTTPS URLs are allowed" in str(exc.value)
        assert "HTTP connections expose data" in str(exc.value)

    def test_allows_http_when_not_required(self):
        """HTTP URLs should be allowed when require_https=False."""
        url = validate_url("http://example.com/events", require_https=False)
        assert url == "http://example.com/events"

    def test_rejects_ftp_scheme(self):
        """FTP and other non-HTTP schemes should be rejected."""
        with pytest.raises(SSRFError) as exc:
            validate_url("ftp://example.com/file", require_https=False)
        assert "Only HTTP(S) URLs are allowed" in str(exc.value)

    def test_rejects_file_scheme(self):
        """File scheme URLs should be rejected."""
        with pytest.raises(SSRFError) as exc:
            validate_url("file:///etc/passwd", require_https=False)
        assert "Only HTTP(S) URLs are allowed" in str(exc.value)

    # --- Private IP Range Tests ---

    def test_blocks_class_a_private_ip(self):
        """10.x.x.x private range should be blocked."""
        with pytest.raises(SSRFError) as exc:
            validate_url("https://10.0.0.1/admin", resolve_dns=False)
        assert "private/internal IP" in str(exc.value)

    def test_blocks_class_b_private_ip(self):
        """172.16-31.x.x private range should be blocked."""
        with pytest.raises(SSRFError) as exc:
            validate_url("https://172.16.0.1/admin", resolve_dns=False)
        assert "private/internal IP" in str(exc.value)

        with pytest.raises(SSRFError) as exc:
            validate_url("https://172.31.255.255/admin", resolve_dns=False)
        assert "private/internal IP" in str(exc.value)

    def test_blocks_class_c_private_ip(self):
        """192.168.x.x private range should be blocked."""
        with pytest.raises(SSRFError) as exc:
            validate_url("https://192.168.1.1/admin", resolve_dns=False)
        assert "private/internal IP" in str(exc.value)

    def test_blocks_loopback_ip(self):
        """127.x.x.x loopback range should be blocked."""
        # 127.0.0.1 is caught by BLOCKED_HOSTNAMES first
        with pytest.raises(SSRFError) as exc:
            validate_url("https://127.0.0.1/admin", resolve_dns=False)
        assert "blocked" in str(exc.value).lower()

        # Other 127.x.x.x addresses are caught by IP range check
        with pytest.raises(SSRFError) as exc:
            validate_url("https://127.255.255.255/admin", resolve_dns=False)
        assert "private/internal IP" in str(exc.value)

    def test_blocks_link_local_ip(self):
        """169.254.x.x link-local range should be blocked."""
        with pytest.raises(SSRFError) as exc:
            validate_url("https://169.254.1.1/admin", resolve_dns=False)
        assert "private/internal IP" in str(exc.value)

    def test_blocks_zero_network(self):
        """0.0.0.0 and 0.x.x.x should be blocked."""
        with pytest.raises(SSRFError) as exc:
            validate_url("https://0.0.0.0/admin", resolve_dns=False)
        # 0.0.0.0 is also in BLOCKED_HOSTNAMES
        assert "blocked" in str(exc.value).lower()

    # --- Localhost Tests ---

    def test_blocks_localhost(self):
        """localhost should be blocked."""
        with pytest.raises(SSRFError) as exc:
            validate_url("https://localhost/admin", resolve_dns=False)
        assert "localhost" in str(exc.value).lower()

    def test_blocks_localhost_with_port(self):
        """localhost with port should be blocked."""
        with pytest.raises(SSRFError) as exc:
            validate_url("https://localhost:8080/admin", resolve_dns=False)
        assert "localhost" in str(exc.value).lower()

    def test_blocks_localhost_subdomain(self):
        """Subdomains of localhost should be blocked."""
        with pytest.raises(SSRFError) as exc:
            validate_url("https://evil.localhost/admin", resolve_dns=False)
        assert "localhost" in str(exc.value).lower()

    def test_blocks_127_0_0_1_hostname(self):
        """127.0.0.1 as hostname should be blocked."""
        with pytest.raises(SSRFError) as exc:
            validate_url("https://127.0.0.1:3000/admin", resolve_dns=False)
        assert "blocked" in str(exc.value).lower()

    # --- IPv6 Tests ---

    def test_blocks_ipv6_loopback(self):
        """IPv6 loopback (::1) should be blocked."""
        with pytest.raises(SSRFError) as exc:
            validate_url("https://[::1]/admin", resolve_dns=False)
        assert "blocked" in str(exc.value).lower()

    # --- Valid Public URLs ---

    def test_allows_public_domain(self):
        """Public domains should be allowed."""
        url = validate_url("https://thenationalva.com/events", resolve_dns=False)
        assert url == "https://thenationalva.com/events"

    def test_allows_public_ip(self):
        """Public IP addresses should be allowed."""
        # 8.8.8.8 is Google's public DNS
        url = validate_url("https://8.8.8.8/test", resolve_dns=False)
        assert url == "https://8.8.8.8/test"

    # --- Domain Whitelist Tests ---

    def test_whitelist_allows_exact_match(self):
        """Exact domain match in whitelist should be allowed."""
        allowed = {"thenationalva.com", "thebroadberry.com"}
        url = validate_url(
            "https://thenationalva.com/events",
            allowed_domains=allowed,
            resolve_dns=False
        )
        assert url == "https://thenationalva.com/events"

    def test_whitelist_allows_subdomain(self):
        """Subdomain of whitelisted domain should be allowed."""
        allowed = {"example.com"}
        url = validate_url(
            "https://www.example.com/events",
            allowed_domains=allowed,
            resolve_dns=False
        )
        assert url == "https://www.example.com/events"

    def test_whitelist_blocks_non_whitelisted(self):
        """Non-whitelisted domains should be blocked."""
        allowed = {"thenationalva.com"}
        with pytest.raises(SSRFError) as exc:
            validate_url(
                "https://malicious-site.com/events",
                allowed_domains=allowed,
                resolve_dns=False
            )
        assert "not in the allowed domains" in str(exc.value)

    # --- Edge Cases ---

    def test_rejects_empty_url(self):
        """Empty URL should be rejected."""
        with pytest.raises(SSRFError) as exc:
            validate_url("")
        assert "non-empty string" in str(exc.value)

    def test_rejects_none_url(self):
        """None URL should be rejected."""
        with pytest.raises(SSRFError) as exc:
            validate_url(None)
        assert "non-empty string" in str(exc.value)

    def test_rejects_url_without_hostname(self):
        """URL without hostname should be rejected."""
        with pytest.raises(SSRFError) as exc:
            validate_url("https:///path/only")
        assert "must include a hostname" in str(exc.value)

    def test_strips_whitespace(self):
        """URL with surrounding whitespace should be cleaned."""
        url = validate_url("  https://example.com/events  ", resolve_dns=False)
        assert url == "https://example.com/events"


class TestDNSResolution:
    """Tests for DNS resolution checks."""

    def test_blocks_hostname_resolving_to_private_ip(self):
        """Hostname that resolves to private IP should be blocked."""
        with patch("servers.event_mcp.sources.url_validator._resolve_hostname") as mock_resolve:
            mock_resolve.return_value = ["192.168.1.1"]

            with pytest.raises(SSRFError) as exc:
                validate_url("https://internal.example.com/admin", resolve_dns=True)

            assert "resolves to private/internal IP" in str(exc.value)

    def test_allows_hostname_resolving_to_public_ip(self):
        """Hostname that resolves to public IP should be allowed."""
        with patch("servers.event_mcp.sources.url_validator._resolve_hostname") as mock_resolve:
            mock_resolve.return_value = ["93.184.216.34"]  # example.com's IP

            url = validate_url("https://example.com/events", resolve_dns=True)
            assert url == "https://example.com/events"


class TestDomainMatchesWhitelist:
    """Tests for the _domain_matches_whitelist helper."""

    def test_exact_match(self):
        """Exact domain match should return True."""
        assert _domain_matches_whitelist("example.com", {"example.com"}) is True

    def test_subdomain_match(self):
        """Subdomain should match parent domain."""
        assert _domain_matches_whitelist("www.example.com", {"example.com"}) is True
        assert _domain_matches_whitelist("api.example.com", {"example.com"}) is True
        assert _domain_matches_whitelist("deep.sub.example.com", {"example.com"}) is True

    def test_no_match(self):
        """Non-matching domain should return False."""
        assert _domain_matches_whitelist("other.com", {"example.com"}) is False

    def test_partial_match_not_allowed(self):
        """Partial string match (not subdomain) should return False."""
        # "notexample.com" should NOT match "example.com"
        assert _domain_matches_whitelist("notexample.com", {"example.com"}) is False

    def test_case_insensitive(self):
        """Matching should be case insensitive."""
        assert _domain_matches_whitelist("EXAMPLE.COM", {"example.com"}) is True
        assert _domain_matches_whitelist("example.com", {"EXAMPLE.COM"}) is True


class TestParseIpAddress:
    """Tests for the _parse_ip_address helper."""

    def test_parses_ipv4(self):
        """Valid IPv4 should be parsed."""
        ip = _parse_ip_address("192.168.1.1")
        assert ip is not None
        assert str(ip) == "192.168.1.1"

    def test_parses_ipv6(self):
        """Valid IPv6 should be parsed."""
        ip = _parse_ip_address("::1")
        assert ip is not None
        assert str(ip) == "::1"

    def test_returns_none_for_hostname(self):
        """Hostname should return None."""
        ip = _parse_ip_address("example.com")
        assert ip is None


class TestIsBlockedIp:
    """Tests for the _is_blocked_ip helper."""

    def test_blocks_private_ranges(self):
        """Private IP ranges should be blocked."""
        # Class A private
        assert _is_blocked_ip(_parse_ip_address("10.0.0.1")) is True
        assert _is_blocked_ip(_parse_ip_address("10.255.255.255")) is True

        # Class B private
        assert _is_blocked_ip(_parse_ip_address("172.16.0.1")) is True
        assert _is_blocked_ip(_parse_ip_address("172.31.255.255")) is True

        # Class C private
        assert _is_blocked_ip(_parse_ip_address("192.168.0.1")) is True
        assert _is_blocked_ip(_parse_ip_address("192.168.255.255")) is True

        # Loopback
        assert _is_blocked_ip(_parse_ip_address("127.0.0.1")) is True

        # Link-local
        assert _is_blocked_ip(_parse_ip_address("169.254.1.1")) is True

    def test_allows_public_ips(self):
        """Public IPs should not be blocked."""
        assert _is_blocked_ip(_parse_ip_address("8.8.8.8")) is False
        assert _is_blocked_ip(_parse_ip_address("93.184.216.34")) is False
        assert _is_blocked_ip(_parse_ip_address("1.1.1.1")) is False

    def test_class_b_boundary(self):
        """Test boundary of Class B private range (172.16-31.x.x)."""
        # Just below range - should be allowed
        assert _is_blocked_ip(_parse_ip_address("172.15.255.255")) is False

        # In range - should be blocked
        assert _is_blocked_ip(_parse_ip_address("172.16.0.0")) is True
        assert _is_blocked_ip(_parse_ip_address("172.31.255.255")) is True

        # Just above range - should be allowed
        assert _is_blocked_ip(_parse_ip_address("172.32.0.0")) is False


class TestValidateUrlForScraping:
    """Tests for the convenience function validate_url_for_scraping."""

    def test_enforces_https(self):
        """Should enforce HTTPS by default."""
        with pytest.raises(SSRFError):
            validate_url_for_scraping("http://example.com/events")

    def test_allows_valid_https_url(self):
        """Should allow valid HTTPS URLs."""
        url = validate_url_for_scraping(
            "https://thenationalva.com/events"
        )
        assert "https://" in url

    def test_blocks_private_ip(self):
        """Should block private IPs."""
        with pytest.raises(SSRFError):
            validate_url_for_scraping("https://192.168.1.1/admin")

    def test_accepts_whitelist(self):
        """Should accept allowed_domains parameter."""
        allowed = {"thenationalva.com"}
        url = validate_url_for_scraping(
            "https://thenationalva.com/events",
            allowed_domains=allowed
        )
        assert url == "https://thenationalva.com/events"


class TestIntegrationWithScrapers:
    """Integration tests for URL validation with scraper functions."""

    @pytest.mark.asyncio
    async def test_web_scraper_rejects_http(self):
        """Web scraper should reject HTTP URLs."""
        from servers.event_mcp.sources.web_scraper import scrape_event_page

        events, stats = await scrape_event_page("http://example.com/events")

        assert events == []
        assert stats.status == "error"
        assert "URL validation failed" in stats.error_message
        assert "HTTPS" in stats.error_message

    @pytest.mark.asyncio
    async def test_web_scraper_rejects_private_ip(self):
        """Web scraper should reject private IP URLs."""
        from servers.event_mcp.sources.web_scraper import scrape_event_page

        events, stats = await scrape_event_page("https://192.168.1.1/events")

        assert events == []
        assert stats.status == "error"
        assert "URL validation failed" in stats.error_message
        assert "private" in stats.error_message.lower()

    @pytest.mark.asyncio
    async def test_web_scraper_rejects_localhost(self):
        """Web scraper should reject localhost URLs."""
        from servers.event_mcp.sources.web_scraper import scrape_event_page

        events, stats = await scrape_event_page("https://localhost/events")

        assert events == []
        assert stats.status == "error"
        assert "URL validation failed" in stats.error_message
        assert "localhost" in stats.error_message.lower()

    @pytest.mark.asyncio
    async def test_firecrawl_rejects_http(self):
        """Firecrawl should reject HTTP URLs before checking API key."""
        from servers.event_mcp.sources.firecrawl import fetch_firecrawl_events

        # Note: URL validation happens after API key check in current implementation
        # If API key is set, we test URL validation
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "test-key"}):
            events, stats = await fetch_firecrawl_events("http://example.com/events")

            assert events == []
            assert stats.status == "error"
            assert "URL validation failed" in stats.error_message

    @pytest.mark.asyncio
    async def test_firecrawl_rejects_private_ip(self):
        """Firecrawl should reject private IP URLs."""
        from servers.event_mcp.sources.firecrawl import fetch_firecrawl_events

        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "test-key"}):
            events, stats = await fetch_firecrawl_events("https://10.0.0.1/events")

            assert events == []
            assert stats.status == "error"
            assert "URL validation failed" in stats.error_message
