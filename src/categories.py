"""Canonical locomotive category rules shared by UI and AI extraction."""

import re
from typing import Iterable, Tuple


DEFAULT_LOCOMOTIVE_CATEGORIES = (
    "Electrical",
    "Steam",
    "Diesel",
    "Train Bus",
)

_CANONICAL = {value.casefold(): value
              for value in DEFAULT_LOCOMOTIVE_CATEGORIES}
_CUSTOM_FORMAT = re.compile(
    r"[A-Z][A-Za-z0-9]*(?:[ -][A-Z0-9][A-Za-z0-9]*){0,3}")


class CategoryValidationError(ValueError):
    """Raised when a custom category does not follow the category format."""


def normalize_category(value: str) -> str:
    """Canonicalize a standard category or validate a custom Title Case one."""
    category = " ".join(str(value or "").split())
    if not category:
        return ""
    canonical = _CANONICAL.get(category.casefold())
    if canonical:
        return canonical
    if len(category) > 40 or not _CUSTOM_FORMAT.fullmatch(category):
        raise CategoryValidationError(
            f"Invalid category '{category}'. Choose Electrical, Steam, Diesel, "
            "or Train Bus; custom categories must be short English Title Case.")
    return category


def normalize_categories(values: Iterable[str]) -> Tuple[str, ...]:
    """Normalize and de-duplicate categories while preserving input order."""
    normalized = []
    seen = set()
    for value in values:
        category = normalize_category(value)
        key = category.casefold()
        if category and key not in seen:
            normalized.append(category)
            seen.add(key)
    return tuple(normalized)


def parse_categories(value: str) -> Tuple[str, ...]:
    return normalize_categories(value.split(","))


def is_default_category(value: str) -> bool:
    try:
        return normalize_category(value) in DEFAULT_LOCOMOTIVE_CATEGORIES
    except CategoryValidationError:
        return False
