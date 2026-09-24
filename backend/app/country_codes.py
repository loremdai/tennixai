"""ISO country-name and alpha-code normalization."""

import pycountry


def iso_alpha3_from_name(value: str | None) -> str | None:
    """Resolve a provider country name or ISO code to lowercase alpha-3."""
    normalized = " ".join((value or "").strip().split())
    if not normalized:
        return None
    try:
        return pycountry.countries.lookup(normalized).alpha_3.lower()
    except LookupError:
        return None


def iso_alpha2_from_code(value: str | None) -> str | None:
    """Resolve a canonical ISO alpha-3 code to uppercase alpha-2."""
    normalized = (value or "").strip()
    if not normalized or normalized.casefold() == "world":
        return None
    try:
        return pycountry.countries.lookup(normalized).alpha_2
    except LookupError:
        return None
