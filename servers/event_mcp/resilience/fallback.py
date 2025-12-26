"""Fallback chain pattern for graceful degradation."""

from typing import Any, Callable, Coroutine, TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class FallbackChain:
    """Execute async functions in order until one succeeds.

    Useful for trying multiple data sources with graceful degradation.
    """

    def __init__(self, *functions: Callable[..., Coroutine[Any, Any, T]]):
        """Initialize fallback chain with ordered functions.

        Args:
            *functions: Async functions to try in order
        """
        self.functions = functions

    async def execute(self, *args: Any, **kwargs: Any) -> T:
        """Execute functions in order until one succeeds.

        Args:
            *args: Positional arguments passed to each function
            **kwargs: Keyword arguments passed to each function

        Returns:
            Result from first successful function

        Raises:
            Last exception if all functions fail
        """
        last_error: Exception | None = None

        for i, func in enumerate(self.functions):
            try:
                result = await func(*args, **kwargs)
                if i > 0:
                    logger.info(
                        "fallback_used",
                        function=func.__name__,
                        attempt=i + 1,
                        total_functions=len(self.functions),
                    )
                return result
            except Exception as e:
                last_error = e
                logger.warning(
                    "fallback_attempt_failed",
                    function=func.__name__,
                    attempt=i + 1,
                    total_functions=len(self.functions),
                    error=str(e),
                )

        logger.error(
            "fallback_chain_exhausted",
            functions=[f.__name__ for f in self.functions],
            final_error=str(last_error),
        )
        raise last_error  # type: ignore


async def with_fallback(
    primary: Callable[..., Coroutine[Any, Any, T]],
    fallback: Callable[..., Coroutine[Any, Any, T]],
    *args: Any,
    **kwargs: Any,
) -> T:
    """Execute primary function with a single fallback.

    Args:
        primary: Primary async function to try first
        fallback: Fallback async function if primary fails
        *args: Positional arguments for functions
        **kwargs: Keyword arguments for functions

    Returns:
        Result from whichever function succeeds
    """
    chain = FallbackChain(primary, fallback)
    return await chain.execute(*args, **kwargs)


async def with_default(
    func: Callable[..., Coroutine[Any, Any, T]],
    default: T,
    *args: Any,
    **kwargs: Any,
) -> T:
    """Execute function and return default value on failure.

    Args:
        func: Async function to execute
        default: Value to return if function fails
        *args: Positional arguments for function
        **kwargs: Keyword arguments for function

    Returns:
        Function result or default value
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.warning(
            "using_default_value",
            function=func.__name__,
            error=str(e),
        )
        return default
