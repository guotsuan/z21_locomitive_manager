"""Validation rules for editable locomotive fields."""

from dataclasses import dataclass
import ipaddress
import re
from typing import Iterable, Mapping, Optional

from .data_models import Locomotive


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str


class LocomotiveValidationError(ValueError):
    """Raised when a locomotive form cannot be safely persisted."""

    def __init__(self, issues: Iterable[ValidationIssue]):
        self.issues = tuple(issues)
        super().__init__("\n".join(f"• {issue.message}" for issue in self.issues))


def validate_locomotive_form(
    values: Mapping[str, str],
    locomotives: Iterable[Locomotive],
    current: Optional[Locomotive] = None,
) -> None:
    """Validate required fields, numeric formats, ranges, and DCC conflicts."""
    issues = []
    name = values.get("name", "").strip()
    address_text = values.get("address", "").strip()
    speed_text = values.get("speed", "").strip()

    if not name:
        issues.append(ValidationIssue("name", "Name is required."))

    address = None
    if not address_text:
        issues.append(ValidationIssue("address", "Address is required."))
    elif not re.fullmatch(r"\d+", address_text):
        issues.append(ValidationIssue("address", "Address must be a whole number."))
    else:
        address = int(address_text)
        if not 1 <= address <= 9999:
            issues.append(ValidationIssue(
                "address", "Address must be between 1 and 9999."))

    if address is not None:
        for locomotive in locomotives:
            if locomotive is current:
                continue
            if (current is not None and current.vehicle_id is not None and
                    locomotive.vehicle_id == current.vehicle_id):
                continue
            if locomotive.address == address:
                issues.append(ValidationIssue(
                    "address",
                    f"Address {address} is already used by “{locomotive.name}”.",
                ))
                break

    if not speed_text:
        issues.append(ValidationIssue("speed", "Max Speed is required."))
    elif not re.fullmatch(r"\d+", speed_text):
        issues.append(ValidationIssue(
            "speed", "Max Speed must be a whole number."))
    elif not 0 <= int(speed_text) <= 999:
        issues.append(ValidationIssue(
            "speed", "Max Speed must be between 0 and 999."))

    build_year = values.get("build_year", "").strip()
    if build_year:
        if not re.fullmatch(r"\d{4}", build_year):
            issues.append(ValidationIssue(
                "build_year", "Build Year must use four digits."))
        elif not 1800 <= int(build_year) <= 2100:
            issues.append(ValidationIssue(
                "build_year", "Build Year must be between 1800 and 2100."))

    ip_value = values.get("ip", "").strip()
    if ip_value:
        try:
            ipaddress.ip_address(ip_value)
        except ValueError:
            issues.append(ValidationIssue(
                "ip", "IP Address must be a valid IPv4 or IPv6 address."))

    stock_since = values.get("in_stock_since", "").strip()
    if stock_since and not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", stock_since):
        issues.append(ValidationIssue(
            "in_stock_since",
            "In Stock Since must use YYYY, YYYY-MM, or YYYY-MM-DD.",
        ))

    if issues:
        raise LocomotiveValidationError(issues)
