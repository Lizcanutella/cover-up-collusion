"""Phone numbers: normalising to E.164, and masking for logs (SECURITY.md, "Logging")."""

import re

DEFAULT_COUNTRY_CODE = "44"  # most of our travellers book from the UK; FIXME: take it from the booking's locale
_DIGITS = re.compile(r"\d+")


class InvalidNumber(ValueError):
    pass


def normalise(raw: str, default_country_code: str = DEFAULT_COUNTRY_CODE) -> str:
    text = raw.strip()
    digits = "".join(_DIGITS.findall(text))
    if text.startswith("+"):
        number = digits
    elif text.startswith("00"):
        number = digits[2:]
    elif digits.startswith("0"):
        number = default_country_code + digits[1:]
    else:
        number = digits
    if not 8 <= len(number) <= 15:
        raise InvalidNumber(f"not a phone number: {mask(raw)}")
    return "+" + number


def mask(number: str) -> str:
    digits = "".join(_DIGITS.findall(number))
    if len(digits) <= 4:
        return "*" * len(digits)
    return "+" + digits[:2] + "*" * (len(digits) - 4) + digits[-2:]
