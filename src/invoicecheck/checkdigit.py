"""Corporate-number (法人番号) check digit and registration-number (登録番号) parsing.

A qualified-invoice registration number is "T" + 13 digits. For a corporation the 13 digits are the corporate number,
whose first digit is a check digit over the other 12 (NTA specification):

    check = 9 - (sum_{n=1..12} P_n * Q_n) mod 9

where P_n is the n-th digit counted from the right of the 12 digits that follow the check digit, and Q_n is 1 for odd n
and 2 for even n. Sole proprietors' numbers are not corporate numbers and have no public check-digit rule in this form,
so they can only be checked by registry lookup (see registry.py).
"""
import re
import unicodedata

_REG = re.compile(r"^T(\d{13})$")


def normalize_registration_number(text):
    """Return 'T' + 13 ASCII digits from messy input ('Ｔ-１２３４ ...', 't1234...'), or None if it cannot be parsed."""
    if text is None:
        return None
    s = unicodedata.normalize("NFKC", str(text)).upper()
    s = re.sub(r"[\s\-‐‑–—ー－・.,]", "", s)
    return s if _REG.match(s) else None


def check_digit(twelve_digits):
    """Check digit for the 12 digits that follow it in a corporate number."""
    if not re.fullmatch(r"\d{12}", twelve_digits):
        raise ValueError("expected exactly 12 digits")
    total = 0
    for n, ch in enumerate(reversed(twelve_digits), start=1):
        total += int(ch) * (1 if n % 2 == 1 else 2)
    return 9 - (total % 9)


def is_valid_corporate_number(thirteen_digits):
    """True if the 13-digit corporate number has a correct check digit."""
    if not re.fullmatch(r"\d{13}", str(thirteen_digits)):
        return False
    return int(thirteen_digits[0]) == check_digit(thirteen_digits[1:])


def is_valid_registration_number(text):
    """True if `text` parses as T + 13 digits whose digits form a valid corporate number.

    A False result does NOT prove the number is wrong for a sole proprietor; use the registry for those.
    """
    reg = normalize_registration_number(text)
    return bool(reg) and is_valid_corporate_number(reg[1:])


def make_corporate_number(twelve_digits):
    """Build a valid 13-digit corporate number from 12 digits (used by the synthetic generator)."""
    return str(check_digit(twelve_digits)) + twelve_digits
