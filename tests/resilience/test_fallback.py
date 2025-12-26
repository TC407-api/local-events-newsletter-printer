"""Tests for fallback chain pattern."""

import pytest

from servers.event_mcp.resilience.fallback import FallbackChain, with_default, with_fallback


class TestFallbackChain:
    """Tests for FallbackChain class."""

    @pytest.mark.asyncio
    async def test_returns_first_success(self):
        """Should return result from first successful function."""

        async def first():
            return "first"

        async def second():
            return "second"

        chain = FallbackChain(first, second)
        result = await chain.execute()

        assert result == "first"

    @pytest.mark.asyncio
    async def test_falls_back_on_failure(self):
        """Should fall back to next function on failure."""

        async def fail():
            raise ValueError("fail")

        async def success():
            return "fallback"

        chain = FallbackChain(fail, success)
        result = await chain.execute()

        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_tries_all_functions(self):
        """Should try all functions before giving up."""
        call_order = []

        async def first():
            call_order.append("first")
            raise ValueError("first failed")

        async def second():
            call_order.append("second")
            raise ValueError("second failed")

        async def third():
            call_order.append("third")
            return "success"

        chain = FallbackChain(first, second, third)
        result = await chain.execute()

        assert result == "success"
        assert call_order == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_raises_last_error_when_all_fail(self):
        """Should raise last error when all functions fail."""

        async def first():
            raise ValueError("first error")

        async def second():
            raise TypeError("second error")

        chain = FallbackChain(first, second)

        with pytest.raises(TypeError) as exc_info:
            await chain.execute()

        assert "second error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_passes_arguments(self):
        """Should pass arguments to all functions."""

        async def fail(x, y):
            raise ValueError("fail")

        async def add(x, y):
            return x + y

        chain = FallbackChain(fail, add)
        result = await chain.execute(2, 3)

        assert result == 5


class TestWithFallback:
    """Tests for with_fallback helper function."""

    @pytest.mark.asyncio
    async def test_returns_primary_on_success(self):
        """Should return primary result on success."""

        async def primary():
            return "primary"

        async def fallback():
            return "fallback"

        result = await with_fallback(primary, fallback)
        assert result == "primary"

    @pytest.mark.asyncio
    async def test_returns_fallback_on_failure(self):
        """Should return fallback result when primary fails."""

        async def primary():
            raise ValueError("failed")

        async def fallback():
            return "fallback"

        result = await with_fallback(primary, fallback)
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_passes_arguments(self):
        """Should pass arguments to both functions."""

        async def primary(x):
            raise ValueError("failed")

        async def fallback(x):
            return x * 2

        result = await with_fallback(primary, fallback, 5)
        assert result == 10


class TestWithDefault:
    """Tests for with_default helper function."""

    @pytest.mark.asyncio
    async def test_returns_function_result_on_success(self):
        """Should return function result on success."""

        async def get_value():
            return 42

        result = await with_default(get_value, default=0)
        assert result == 42

    @pytest.mark.asyncio
    async def test_returns_default_on_failure(self):
        """Should return default value on failure."""

        async def fail():
            raise ValueError("failed")

        result = await with_default(fail, default="default_value")
        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_passes_arguments(self):
        """Should pass arguments to function."""

        async def multiply(x, y):
            return x * y

        result = await with_default(multiply, default=0, x=3, y=4)
        # Note: x and y are passed as kwargs
        assert result == 12

    @pytest.mark.asyncio
    async def test_default_can_be_none(self):
        """Should allow None as default value."""

        async def fail():
            raise ValueError("failed")

        result = await with_default(fail, default=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_default_can_be_empty_list(self):
        """Should allow empty collections as default."""

        async def fail():
            raise ValueError("failed")

        result = await with_default(fail, default=[])
        assert result == []
