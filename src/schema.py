"""Schema mappings shared by Z21 SQLite read and write operations."""

from typing import Any, Dict, Iterable, Optional

from .data_models import Locomotive


VEHICLE_READ_COLUMNS = (
    "id", "name", "address", "max_speed", "active",
    "traction_direction", "image_name", "drivers_cab", "description",
    "full_name", "railway", "article_number", "decoder_type",
    "build_year", "buffer_lenght", "model_buffer_lenght",
    "service_weight", "model_weight", "rmin", "ip", "speed_display",
    "type", "crane",
)

IN_STOCK_SINCE_COLUMNS = (
    "in_stock_since",
    "inStockSince",
    "in_stock_since_date",
)


def first_available(candidates: Iterable[str],
                    available_columns: set) -> Optional[str]:
    return next((name for name in candidates if name in available_columns),
                None)


def locomotive_to_vehicle_values(locomotive: Locomotive,
                                 position: Optional[int] = None
                                 ) -> Dict[str, Any]:
    """Map a domain locomotive to known Z21 vehicle columns."""
    values: Dict[str, Any] = {
        "type": locomotive.rail_vehicle_type,
        "name": locomotive.name,
        "address": locomotive.address,
        "max_speed": locomotive.speed,
        "active": 1 if locomotive.active else 0,
        "traction_direction": 1 if locomotive.direction else 0,
        "image_name": locomotive.image_name or None,
        "drivers_cab": locomotive.drivers_cab or None,
        "description": locomotive.description or None,
        "full_name": locomotive.full_name or None,
        "railway": locomotive.railway or None,
        "article_number": locomotive.article_number or None,
        "decoder_type": locomotive.decoder_type or None,
        "build_year": locomotive.build_year or None,
        "buffer_lenght": locomotive.buffer_length or None,
        "model_buffer_lenght": locomotive.model_buffer_length or None,
        "service_weight": locomotive.service_weight or None,
        "model_weight": locomotive.model_weight or None,
        "rmin": locomotive.rmin or None,
        "ip": locomotive.ip or None,
        "speed_display": locomotive.speed_display,
        "crane": 1 if locomotive.crane else 0,
    }
    if position is not None:
        values["position"] = position
    return values


def values_for_columns(values: Dict[str, Any],
                       available_columns: set) -> Dict[str, Any]:
    return {
        column: value
        for column, value in values.items()
        if column in available_columns
    }
