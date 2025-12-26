"""Tests for retry with backoff pattern."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from servers.event_mcp.resilience.retry import retry_once, retry_with_backoff


class TestRetryWithBackoff:
    """Tests for retry_with_backoff decorator."""

    @pytest.mark.asyncio
    async def test_returns_on_success(self):
        """Should return result on successful call."""

        @retry_with_backoff(max_attempts=3)
        async def success():
            return "ok"

        result = await success()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        """Should retry on failure."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("retry me")
            return "ok"

        result = await fail_then_succeed()
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self):
        """Should raise after max attempts exhausted."""

        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        async def always_fail():
            raise ValueError("always fails")

        with pytest.raises(ValueError) as exc_info:
            await always_fail()

        assert "always fails" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_respects_retryable_exceptions(self):
        """Should only retry specified exception types."""

        @retry_with_backoff(
            max_attempts=3, base_delay=0.01, retryable_exceptions=(ValueError,)
        )
        async def raise_type_error():
            raise TypeError("not retryable")

        # Should raise immediately, not retry
        with pytest.raises(TypeError):
            await raise_type_error()

    @pytest.mark.asyncio
    async def test_exponential_delay(self):
        """Should use exponential backoff."""
        delays = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            delays.append(delay)
            await original_sleep(0.001)  # Actually sleep briefly

        call_count = 0

        @retry_with_backoff(
            max_attempts=4, base_delay=0.1, exponential_base=2.0, jitter=False
        )
        async def fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with patch("asyncio.sleep", mock_sleep):
            with pytest.raises(ValueError):
                await fail()

        # Should have 3 delays (attempts 1-3, no delay after final failure)
        assert len(delays) == 3
        # Delays should increase exponentially: 0.1, 0.2, 0.4
        assert delays[1] > delays[0]
        assert delays[2] > delays[1]

    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Should cap delay at max_delay."""

        @retry_with_backoff(
            max_attempts=5,
            base_delay=10.0,
            max_delay=1.0,
            exponential_base=2.0,
            jitter=False,
        )
        async def fail():
            raise ValueError("fail")

        delays = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            delays.append(delay)

        with patch("asyncio.sleep", mock_sleep):
            with pytest.raises(ValueError):
                await fail()

        # All delays should be capped at 1.0
        for delay in delays:
            assert delay <= 1.0


class TestRetryOnce:
    """Tests for retry_once function."""

    @pytest.mark.asyncio
    async def test_returns_on_success(self):
        """Should return result on success."""

        async def success():
            return "ok"

        result = await retry_once(success)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retries_and_succeeds(self):
        """Should retry and return on eventual success."""
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("retry")
            return "ok"

        result = await retry_once(fail_then_succeed, max_attempts=3, base_delay=0.01)
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_exhaustion(self):
        """Should raise last exception after exhausting retries."""

        async def always_fail():
            raise ValueError("always fails")

        with pytest.raises(ValueError):
            await retry_once(always_fail, max_attempts=2, base_delay=0.01)

    @pytest.mark.asyncio
    async def test_passes_args_and_kwargs(self):
        """Should pass arguments to function."""

        async def add(a, b, multiplier=1):
            return (a + b) * multiplier

        result = await retry_once(add, 2, 3, multiplier=2)
        assert result == 10
