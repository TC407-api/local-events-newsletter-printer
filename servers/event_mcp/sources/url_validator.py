"""
URL validation for SSRF (Server-Side Request Forgery) protection.

Validates URLs before making HTTP requests to prevent:
- Requests to internal/private networks
- Requests to localhost/loopback addresses
- Non-HTTPS connections (data exposure risk)
"""

import ipaddress
import re
import socket
from typing import Optional
from urllib.parse import urlparse


class SSRFError(Exception):
    """Raised when a URL fails SSRF validation."""
    pass


# Private/reserved IP ranges that should be blocked
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),        # Class A private
    ipaddress.ip_network("172.16.0.0/12"),     # Class B private
    ipaddress.ip_network("192.168.0.0/16"),    # Class C private
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local
    ipaddress.ip_network("0.0.0.0/8"),         # "This" network
    ipaddress.ip_network("224.0.0.0/4"),       # Multicast
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved
    ipaddress.ip_network("100.64.0.0/10"),     # Carrier-grade NAT
    ipaddress.ip_network("192.0.0.0/24"),      # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),      # TEST-NET-1
    ipaddress.ip_network("198.51.100.0/24"),   # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),    # TEST-NET-3
    ipaddress.ip_network("fc00::/7"),          # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
]

# Hostnames that should always be blocked
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
}

# Pattern for numeric IPv4 addresses
IPV4_PATTERN = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


def validate_url(
    url: str,
    require_https: bool = True,
    allowed_domains: Optional[set[str]] = None,
    resolve_dns: bool = True,
) -> str:
    """
    Validate a URL for SSRF protection.

    Args:
        url: The URL to validate
        require_https: If True, reject http:// URLs (default: True)
        allowed_domains: Optional whitelist of allowed domains. If provided,
                        only URLs matching these domains are allowed.
        resolve_dns: If True, resolve hostname to IP and check against
                    blocked ranges. This prevents DNS rebinding attacks
                    but requires network access. (default: True)

    Returns:
        The validated URL (normalized)

    Raises:
        SSRFError: If the URL fails validation with a descriptive message
    """
    if not url or not isinstance(url, str):
        raise SSRFError("URL must be a non-empty string")

    url = url.strip()

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise SSRFError(f"Invalid URL format: {e}")

    # Validate scheme
    scheme = parsed.scheme.lower()
    if require_https:
        if scheme != "https":
            raise SSRFError(
                f"Only HTTPS URLs are allowed (got {scheme}://). "
                "HTTP connections expose data in transit."
            )
    else:
        if scheme not in ("http", "https"):
            raise SSRFError(
                f"Only HTTP(S) URLs are allowed (got {scheme}://)"
            )

    # Validate hostname exists
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL must include a hostname")

    hostname_lower = hostname.lower()

    # Check against blocked hostnames
    if hostname_lower in BLOCKED_HOSTNAMES:
        raise SSRFError(
            f"Access to {hostname} is blocked (localhost/loopback addresses are not allowed)"
        )

    # Check for localhost variants
    if hostname_lower.startswith("localhost") or hostname_lower.endswith(".localhost"):
        raise SSRFError(
            f"Access to {hostname} is blocked (localhost addresses are not allowed)"
        )

    # Check allowed domains whitelist if provided
    if allowed_domains is not None:
        if not _domain_matches_whitelist(hostname_lower, allowed_domains):
            raise SSRFError(
                f"Domain {hostname} is not in the allowed domains list"
            )

    # Check if hostname is a raw IP address
    ip_addr = _parse_ip_address(hostname)
    if ip_addr:
        if _is_blocked_ip(ip_addr):
            raise SSRFError(
                f"Access to {hostname} is blocked (private/internal IP addresses are not allowed)"
            )
    elif resolve_dns:
        # Resolve hostname to IP and check
        try:
            resolved_ips = _resolve_hostname(hostname)
            for ip_str in resolved_ips:
                ip_addr = _parse_ip_address(ip_str)
                if ip_addr and _is_blocked_ip(ip_addr):
                    raise SSRFError(
                        f"Access to {hostname} is blocked (resolves to private/internal IP {ip_str})"
                    )
        except socket.gaierror:
            # DNS resolution failed - could be temporary, allow the request
            # The HTTP client will fail anyway if hostname is invalid
            pass

    return url


def _domain_matches_whitelist(hostname: str, allowed_domains: set[str]) -> bool:
    """Check if hostname matches any allowed domain (supports wildcards)."""
    hostname = hostname.lower()

    for domain in allowed_domains:
        domain = domain.lower()

        # Exact match
        if hostname == domain:
            return True

        # Subdomain match (e.g., "www.example.com" matches "example.com")
        if hostname.endswith("." + domain):
            return True

    return False


def _parse_ip_address(hostname: str) -> Optional[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Try to parse hostname as an IP address."""
    try:
        return ipaddress.ip_address(hostname)
    except ValueError:
        return None


def _is_blocked_ip(ip_addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address is in a blocked range."""
    for network in BLOCKED_IP_RANGES:
        try:
            if ip_addr in network:
                return True
        except TypeError:
            # IPv4 address in IPv6 network or vice versa
            continue
    return False


def _resolve_hostname(hostname: str) -> list[str]:
    """Resolve hostname to IP addresses."""
    try:
        # getaddrinfo returns list of (family, type, proto, canonname, sockaddr)
        # sockaddr is (ip, port) for IPv4 or (ip, port, flow, scope) for IPv6
        results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC)
        return list(set(result[4][0] for result in results))
    except socket.gaierror:
        raise


def validate_url_for_scraping(
    url: str,
    allowed_domains: Optional[set[str]] = None,
) -> str:
    """
    Convenience function for validating URLs used in web scraping.

    Enforces HTTPS and blocks private IPs with DNS resolution check.

    Args:
        url: The URL to validate
        allowed_domains: Optional whitelist of allowed domains

    Returns:
        The validated URL

    Raises:
        SSRFError: If the URL fails validation
    """
    return validate_url(
        url,
        require_https=True,
        allowed_domains=allowed_domains,
        resolve_dns=True,
    )
