"""
TripMate AI - Validators
Input validation helpers.
"""

from datetime import date, datetime


def validate_trip_form(origin, destination, start_date, end_date, budget, travelers):
    """
    Validate all trip planning form fields.
    Returns (is_valid: bool, errors: list[str])
    """
    errors = []

    if not origin or not origin.strip():
        errors.append("Please enter a starting location.")

    if not destination or not destination.strip():
        errors.append("Please enter a destination.")

    if origin and destination and origin.strip().lower() == destination.strip().lower():
        errors.append("Starting location and destination cannot be the same.")

    if start_date is None:
        errors.append("Please select a start date.")

    if end_date is None:
        errors.append("Please select an end date.")

    if start_date and end_date:
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        if end_date < start_date:
            errors.append("End date must be after the start date.")
        if start_date < date.today():
            errors.append("Start date cannot be in the past.")
        duration = (end_date - start_date).days + 1
        if duration > 30:
            errors.append("Trip duration cannot exceed 30 days.")

    if budget is None or budget <= 0:
        errors.append("Please enter a valid total budget (greater than ₹0).")

    if travelers is None or travelers < 1:
        errors.append("Number of travelers must be at least 1.")

    if travelers and travelers > 20:
        errors.append("Number of travelers cannot exceed 20.")

    return len(errors) == 0, errors


def validate_budget_inputs(transport, accommodation, food, activities, misc):
    """Validate budget planner inputs."""
    errors = []
    for name, val in [
        ("Transportation", transport),
        ("Accommodation", accommodation),
        ("Food", food),
        ("Activities", activities),
        ("Miscellaneous", misc),
    ]:
        if val is None or val < 0:
            errors.append(f"{name} cost cannot be negative.")
    return len(errors) == 0, errors


def sanitize_text(text: str, max_length: int = 100) -> str:
    """Strip and truncate user text input."""
    if not text:
        return ""
    return text.strip()[:max_length]
