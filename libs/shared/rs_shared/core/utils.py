"""Shared utility helpers used across core and service layers."""


def mask_email(email: str | list[str]) -> str:
    """Mask an email address (or list of addresses) for safe logging.

    Returns ``ab***@domain.com`` for a single address, or a comma-separated
    masked list when given multiple addresses.
    """
    if isinstance(email, list):
        return ", ".join(mask_email(e) for e in email)
    parts = email.split("@", 1)
    if len(parts) != 2:
        return "***"
    local, domain = parts
    return f"{local[:2]}***@{domain}"
