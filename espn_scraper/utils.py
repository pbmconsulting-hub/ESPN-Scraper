"""
utils.py — Shared utility helpers for the ESPN NBA Scraper.
"""


def normalize_date(date_str: str) -> str:
    """
    Normalize a date string to the ``YYYYMMDD`` format expected by ESPN APIs.

    Accepts common separators (slashes and dashes) and strips them so that
    ``2026/03/29`` and ``2026-03-29`` are both treated the same as ``20260329``.

    Args:
        date_str: A date string in ``YYYYMMDD``, ``YYYY/MM/DD``, or
                  ``YYYY-MM-DD`` format.

    Returns:
        An 8-digit string in ``YYYYMMDD`` format.

    Raises:
        ValueError: If the cleaned string is not exactly 8 digits.
    """
    cleaned = date_str.replace("/", "").replace("-", "")
    if not cleaned.isdigit() or len(cleaned) != 8:
        raise ValueError(
            f"Invalid date format '{date_str}'. "
            "Expected YYYYMMDD (e.g. 20260329, 2026/03/29, or 2026-03-29)."
        )
    return cleaned
