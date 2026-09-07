from datetime import UTC, datetime
from email.utils import parsedate_to_datetime


def retry_delay(value: str | None, attempt: int) -> float:
    """Honor Retry-After without retrying early; caller defers waits above one minute."""
    try:
        seconds = float(value or "")
    except ValueError:
        try:
            seconds = (parsedate_to_datetime(value or "") - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            seconds = 2**attempt
    return max(1.0, seconds)
