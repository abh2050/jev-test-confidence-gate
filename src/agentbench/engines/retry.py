"""Rate-limit retry for engines whose SDK does not do it for us.

The TypeSafe and OpenAI clients retry internally; the Gemini client does not, and
a free-tier key hits 429 within a few dozen requests. A sweep that silently drops
those tickets produces a column that is not comparable with the others, so it is
worth waiting them out.
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")

DEFAULT_ATTEMPTS = 5
DEFAULT_BASE_DELAY = 2.0
MAX_DELAY = 60.0


def _is_rate_limit(error: Exception) -> bool:
    code = getattr(error, "code", None) or getattr(error, "status_code", None)
    if code == 429:
        return True
    text = str(error)
    return "429" in text or "RESOURCE_EXHAUSTED" in text


def with_rate_limit_retry(
    call: Callable[[], T],
    attempts: int = DEFAULT_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    sleep: Callable[[float], Any] = time.sleep,
) -> T:
    """Run `call`, backing off on 429s. Other errors propagate immediately."""
    for attempt in range(attempts):
        try:
            return call()
        except Exception as error:
            last = attempt == attempts - 1
            if last or not _is_rate_limit(error):
                raise
            # Full jitter, so parallel sweeps do not retry in lockstep.
            delay = min(MAX_DELAY, base_delay * (2**attempt))
            sleep(delay * (0.5 + random.random() * 0.5))
    raise AssertionError("unreachable")
