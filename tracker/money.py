from decimal import Decimal, InvalidOperation

from django.conf import settings


def currency_symbol():
    """The symbol comes from settings.CURRENCY_SYMBOL (default: rupee)."""
    return getattr(settings, 'CURRENCY_SYMBOL', '₹')


def _to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def format_money(value, absolute=False):
    """45.5 -> '₹45.50', -245 -> '-₹245.00' (absolute=True gives '₹245.00')."""
    amount = _to_decimal(value)
    if absolute:
        amount = abs(amount)
    sign = '-' if amount < 0 else ''
    return f"{sign}{currency_symbol()}{abs(amount):,.2f}"
