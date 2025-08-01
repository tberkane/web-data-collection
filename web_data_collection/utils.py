import signal
from typing import Any, Callable, Dict, Optional, Union

from litellm import completion

from .configs import LLMConfig


def perform_completion(
    prompt: str,
    llm_config: LLMConfig,
) -> Any:
    """
    Perform LLM completion.

    Args:
        prompt: The prompt to send to the LLM
        llm_config: Configuration for the LLM provider

    Returns:
        LLM response
    """

    response = completion(
        model=llm_config.model,
        api_key=llm_config.api_key,
        temperature=llm_config.temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return response


class TimeoutException(Exception):
    """Exception raised when a function call times out."""

    pass


def timeout_handler(signum: int, frame: Any) -> None:
    """Signal handler for timeout."""
    raise TimeoutException("Function call timed out")


def timeout_function(
    func: Callable,
    args: tuple = (),
    kwargs: Optional[Dict[str, Any]] = None,
    timeout: int = 5,
    default_value: Any = None,
) -> Any:
    """
    Wrap a function with a timeout.

    Args:
        func: Function to execute
        args: Positional arguments for the function
        kwargs: Keyword arguments for the function
        timeout: Timeout in seconds
        default_value: Value to return if timeout occurs

    Returns:
        Function result or default_value if timeout occurs

    Note:
        This function uses signal.SIGALRM which is Unix-specific.
        On Windows, this will not work as expected.
    """
    if kwargs is None:
        kwargs = {}

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)

    try:
        result = func(*args, **kwargs)
        signal.alarm(0)
        return result
    except TimeoutException:
        return default_value
