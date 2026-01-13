"""Service for managing dynamic options (built-in + custom)."""
from models import CustomOption
from constants import BUILTIN_CHOICES, OPTION_TYPE_LABELS


def get_choices_for_type(option_type: str) -> list[tuple[str, str]]:
    """Get built-in defaults + user-defined custom options for a given type.

    Args:
        option_type: One of the keys in BUILTIN_CHOICES (e.g., 'inventory_category')

    Returns:
        List of (value, label) tuples for use in form dropdowns.
    """
    # Get built-in defaults
    defaults = BUILTIN_CHOICES.get(option_type, [])

    # Get custom options from database
    custom = CustomOption.query.filter_by(option_type=option_type).order_by(CustomOption.label).all()
    custom_choices = [(opt.value, opt.label) for opt in custom]

    return defaults + custom_choices


def get_all_custom_options() -> dict[str, list[CustomOption]]:
    """Get all custom options grouped by type.

    Returns:
        Dict mapping option_type to list of CustomOption objects.
    """
    options = CustomOption.query.order_by(CustomOption.option_type, CustomOption.label).all()
    grouped = {}
    for opt in options:
        if opt.option_type not in grouped:
            grouped[opt.option_type] = []
        grouped[opt.option_type].append(opt)
    return grouped


def get_option_types() -> list[tuple[str, str]]:
    """Get list of available option types for dropdown.

    Returns:
        List of (value, label) tuples.
    """
    return [(k, v) for k, v in OPTION_TYPE_LABELS.items()]


def get_label_for_value(option_type: str, value: str) -> str:
    """Get display label for a given option value.

    Useful for displaying human-readable labels in list views.

    Args:
        option_type: The option type (e.g., 'inventory_category')
        value: The stored value (e.g., 'mouse')

    Returns:
        The display label, or the value itself if not found.
    """
    # Check built-in choices first
    for v, label in BUILTIN_CHOICES.get(option_type, []):
        if v == value:
            return label

    # Check custom options
    custom = CustomOption.query.filter_by(option_type=option_type, value=value).first()
    if custom:
        return custom.label

    # Fallback to the value itself (titlecased)
    return value.replace('_', ' ').title()


def is_valid_option(option_type: str, value: str) -> bool:
    """Check if a value is valid for a given option type.

    Args:
        option_type: The option type
        value: The value to check

    Returns:
        True if valid (exists in built-in or custom), False otherwise.
    """
    # Check built-in
    for v, _ in BUILTIN_CHOICES.get(option_type, []):
        if v == value:
            return True

    # Check custom
    return CustomOption.query.filter_by(option_type=option_type, value=value).first() is not None


def get_valid_values_for_type(option_type: str) -> list[str]:
    """Get list of valid values (not tuples) for validation.

    Args:
        option_type: One of the keys in BUILTIN_CHOICES

    Returns:
        List of valid value strings for use in form validation.
    """
    choices = get_choices_for_type(option_type)
    return [value for value, _ in choices]
