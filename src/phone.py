"""US phone numbers as one shape: (xxx) xxx-xxxx.

Ten digits (or eleven with a leading 1) become the standard form. Anything
else — an extension, an international number, a partial — is kept exactly as
typed, because rewriting a number we do not understand would lose it.
"""

import re


def format_phone(value):
    """Return `value` as (xxx) xxx-xxxx when it is a US number, else unchanged."""
    if not value:
        return value
    digits = re.sub(r'\D', '', str(value))
    if len(digits) == 11 and digits[0] == '1':
        digits = digits[1:]
    if len(digits) != 10 or re.search(r'[A-Za-z#]', str(value)):
        return value
    return f'({digits[:3]}) {digits[3:6]}-{digits[6:]}'
