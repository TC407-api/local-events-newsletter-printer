"""Circuit breaker pattern for protecting external API calls."""

from datetime import datetime
from enum import Enum
from typing import Any, Coroutine, TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class CircuitState(Enum):
    """States for the circuit breaker."""

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and blocking requests."""

    def __init__(self, circuit_name: str):
        super().__init__(f"Circuit breaker '{circuit_name}' is open")
        self.circuit_name = circuit_name


class CircuitBreaker:
    """Circuit breaker for protecting external API calls.

    Prevents cascading failures by stopping requests to failing services.
    After a recovery timeout, allows test requests through (half-open state).
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str = "default",
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            name: Name for logging and identification
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time: datetime | None = None
        self.success_count_in_half_open = 0

    async def call(self, coro: Coroutine[Any, Any, T]) -> T:
        """Execute coroutine with circuit breaker protection.

        Args:
            coro: Async coroutine to execute

        Returns:
            Result of the coroutine

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: If coroutine fails (after recording failure)
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                raise CircuitBreakerOpenError(self.name)

        try:
            result = await coro
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try recovering."""
        if not self.last_failure_time:
            return True
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def _transition_to_half_open(self) -> None:
        """Move to half-open state to test recovery."""
        self.state = CircuitState.HALF_OPEN
        self.success_count_in_half_open = 0
        logger.info(
            "circuit_half_open",
            circuit=self.name,
            message="Testing if service has recovered",
        )

    def _on_success(self) -> None:
        """Handle successful request."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count_in_half_open += 1
            if self.success_count_in_half_open >= 2:
                self._close_circuit()
        else:
            self.failure_count = 0

    def _close_circuit(self) -> None:
        """Close circuit, return to normal operation."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        logger.info(
            "circuit_closed",
            circuit=self.name,
            message="Service recovered, resuming normal operation",
        )

    def _on_failure(self, error: Exception) -> None:
        """Handle failed request."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitState.HALF_OPEN:
            self._open_circuit(error)
        elif self.failure_count >= self.failure_threshold:
            self._open_circuit(error)

    def _open_circuit(self, error: Exception) -> None:
        """Open circuit, block future requests."""
        self.state = CircuitState.OPEN
        logger.warning(
            "circuit_opened",
            circuit=self.name,
            failure_count=self.failure_count,
            recovery_timeout=self.recovery_timeout,
            error=str(error),
        )

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = None
        self.success_count_in_half_open = 0

    @property
    def is_open(self) -> bool:
        """Check if circuit is currently open."""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is currently closed."""
        return self.state == CircuitState.CLOSED

    def get_status(self) -> dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
        }
