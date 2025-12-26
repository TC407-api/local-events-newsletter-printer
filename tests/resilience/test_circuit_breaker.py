"""Tests for circuit breaker pattern."""

import asyncio
from datetime import datetime, timedelta

import pytest

from servers.event_mcp.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_starts_closed(self):
        """Circuit breaker should start in closed state."""
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed
        assert not cb.is_open

    @pytest.mark.asyncio
    async def test_stays_closed_on_success(self):
        """Circuit should stay closed on successful calls."""
        cb = CircuitBreaker(failure_threshold=3)

        async def success():
            return "ok"

        result = await cb.call(success())
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        """Circuit should open after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)

        async def fail():
            raise ValueError("test error")

        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call(fail())

        assert cb.state == CircuitState.OPEN
        assert cb.is_open

    @pytest.mark.asyncio
    async def test_rejects_calls_when_open(self):
        """Open circuit should reject calls with CircuitBreakerOpenError."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)

        async def fail():
            raise ValueError("test error")

        async def success():
            return "ok"

        # Trigger failure to open circuit
        with pytest.raises(ValueError):
            await cb.call(fail())

        assert cb.is_open

        # Should reject next call
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await cb.call(success())

        assert cb.name in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_resets_failure_count_on_success(self):
        """Successful call should reset failure count."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.failure_count = 2

        async def success():
            return "ok"

        await cb.call(success())

        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED

    def test_reset_method(self):
        """Manual reset should restore initial state."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.failure_count = 5
        cb.state = CircuitState.OPEN
        cb.last_failure_time = datetime.now()

        cb.reset()

        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED
        assert cb.last_failure_time is None

    def test_get_status(self):
        """Status should include all relevant information."""
        cb = CircuitBreaker(failure_threshold=5, name="test_circuit")

        status = cb.get_status()

        assert status["name"] == "test_circuit"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["failure_threshold"] == 5


class TestCircuitBreakerRecovery:
    """Tests for circuit breaker recovery behavior."""

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self):
        """Circuit should transition to half-open after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)  # Immediate recovery

        async def fail():
            raise ValueError("error")

        async def success():
            return "ok"

        # Open the circuit
        with pytest.raises(ValueError):
            await cb.call(fail())

        assert cb.is_open

        # Wait a tiny bit for the timeout
        await asyncio.sleep(0.01)

        # Next call should go through (half-open)
        result = await cb.call(success())
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_closes_after_successful_half_open_calls(self):
        """Circuit should close after successful calls in half-open state."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)

        async def fail():
            raise ValueError("error")

        async def success():
            return "ok"

        # Open the circuit
        with pytest.raises(ValueError):
            await cb.call(fail())

        await asyncio.sleep(0.01)

        # Make successful calls to close
        await cb.call(success())
        await cb.call(success())

        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reopens_on_failure_in_half_open(self):
        """Circuit should reopen on failure during half-open state."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)

        async def fail():
            raise ValueError("error")

        # Open the circuit
        with pytest.raises(ValueError):
            await cb.call(fail())

        await asyncio.sleep(0.01)

        # Fail during half-open
        with pytest.raises(ValueError):
            await cb.call(fail())

        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerOpenError:
    """Tests for CircuitBreakerOpenError exception."""

    def test_error_includes_circuit_name(self):
        """Error message should include circuit name."""
        error = CircuitBreakerOpenError("api_circuit")
        assert "api_circuit" in str(error)
        assert error.circuit_name == "api_circuit"
