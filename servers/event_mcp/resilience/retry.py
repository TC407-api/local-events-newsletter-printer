"""Retry with exponential backoff for resilient API calls."""

import asyncio
import random
from functools import wraps
from typing import Any, Callable, TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for async retry with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Add randomness to delay to prevent thundering herd
        retryable_exceptions: Tuple of exception types to retry on

    Returns:
        Decorated async function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        delay = min(
                            base_delay * (exponential_base**attempt),
                            max_delay,
                        )
                        if jitter:
                            delay *= 0.5 + random.random()

                        logger.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_attempts=max_attempts,
                            delay=round(delay, 2),
                            error=str(e),
                        )
                        await asyncio.sleep(delay)

            logger.error(
                "retry_exhausted",
                function=func.__name__,
                max_attempts=max_attempts,
                error=str(last_exception),
            )
            raise last_exception  # type: ignore

        return wrapper  # type: ignore

    return decorator


async def retry_once(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs: Any,
) -> T:
    """Execute a function with retry logic (non-decorator version).

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        max_attempts: Maximum retry attempts
        base_delay: Initial delay between retries
        retryable_exceptions: Exception types to retry on
        **kwargs: Keyword arguments for func

    Returns:
        Result of successful function call

    Raises:
        Last exception if all retries fail
    """
    last_exception: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e
            if attempt < max_attempts - 1:
                delay = base_delay * (2**attempt) * (0.5 + random.random())
                await asyncio.sleep(delay)

    raise last_exception  # type: ignore
