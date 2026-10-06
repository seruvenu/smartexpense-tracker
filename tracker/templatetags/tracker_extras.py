from decimal import Decimal

from django import template

from tracker.money import currency_symbol as _currency_symbol
from tracker.money import format_money

register = template.Library()


@register.filter
def money(value):
    """-245 -> '-₹245.00' (instead of '₹-245.00')."""
    return format_money(value)


@register.filter
def money_abs(value):
    """-245 -> '₹245.00' (use with words like 'over' or 'exceeded')."""
    return format_money(value, absolute=True)


@register.simple_tag
def currency_symbol():
    """{% currency_symbol %} -> the symbol from settings (for form labels, JS, ...)."""
    return _currency_symbol()


@register.filter
def money_minus(value):
    """245 -> '-₹245.00' (always negative: use for amounts that are over budget)."""
    return format_money(-abs(Decimal(str(value))))
