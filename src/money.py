"""Money is stored as whole cents in an Integer column - never a float.

These helpers are the only place dollars and cents meet: forms parse into
cents on the way in, the `currency` template filter formats cents on the way
out, and nothing in between does arithmetic on a float.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# Ten trillion dollars. Well past any estate, and well inside SQLite's 64-bit
# integer, so a stray keystroke ("1e30") is refused instead of overflowing.
MAX_CENTS = 10 ** 15


def to_cents(value):
    """Dollars (number or text like "$1,250.50") -> int cents. None/"" -> None.

    Raises ValueError on anything that is not a number."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("not an amount")
    if isinstance(value, (int, float, Decimal)):
        amount = Decimal(str(value))
    else:
        text = str(value).strip().replace("$", "").replace(",", "")
        if text == "":
            return None
        try:
            amount = Decimal(text)
        except InvalidOperation:
            raise ValueError(f"'{value}' is not an amount")
    if not amount.is_finite():
        raise ValueError(f"'{value}' is not an amount")
    # Checked before quantize, which itself raises past 28 digits.
    if abs(amount * 100) > MAX_CENTS:
        raise ValueError(f"'{value}' is too large an amount")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cents_to_input(cents):
    """Cents -> the text a form field shows: 1250 -> "12.50", 120000 -> "1200"."""
    if cents is None:
        return ""
    dollars, rem = divmod(abs(int(cents)), 100)
    sign = "-" if cents < 0 else ""
    return f"{sign}{dollars}" if rem == 0 else f"{sign}{dollars}.{rem:02d}"


def format_cents(cents):
    """Cents -> "$1,250" or "$1,250.50" (no decimals when they are zero)."""
    if cents is None:
        return ""
    dollars, rem = divmod(abs(int(cents)), 100)
    sign = "-" if cents < 0 else ""
    if rem == 0:
        return f"{sign}${dollars:,}"
    return f"{sign}${dollars:,}.{rem:02d}"


def cents_to_dollars(cents):
    """For chart payloads only, where the browser needs a plain number."""
    return 0 if cents is None else int(cents) / 100
