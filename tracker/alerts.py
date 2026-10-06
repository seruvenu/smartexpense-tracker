"""Pure budget-alert logic (no database access) so it is easy to unit test.

Rules:
    spent <  80% of limit  -> normal
    spent >= 80% of limit  -> warning
    spent >= 100% of limit -> danger
"""
from decimal import Decimal

WARNING_PERCENT = 80  # warning starts at 80 %
DANGER_PERCENT = 100  # danger starts at 100 %

STATUS_META = {
    'normal': {'label': 'Normal', 'badge_class': 'bg-success', 'progress_class': 'bg-success'},
    'warning': {'label': 'Warning', 'badge_class': 'bg-warning text-dark', 'progress_class': 'bg-warning'},
    'danger': {'label': 'Danger', 'badge_class': 'bg-danger', 'progress_class': 'bg-danger'},
}

# Used to sort the worst categories first.
STATUS_ORDER = {'danger': 0, 'warning': 1, 'normal': 2}


def _dec(value):
    return value if isinstance(value, Decimal) else Decimal(str(value))


def get_status(spent, limit):
    """Return 'normal', 'warning' or 'danger' using exact Decimal maths."""
    spent, limit = _dec(spent), _dec(limit)
    if limit <= 0:
        return 'normal'
    if spent * 100 >= limit * DANGER_PERCENT:
        return 'danger'
    if spent * 100 >= limit * WARNING_PERCENT:
        return 'warning'
    return 'normal'


def budget_status(spent, limit):
    """Return everything the UI needs for one budget: status, label, colours, numbers."""
    spent, limit = _dec(spent), _dec(limit)
    status = get_status(spent, limit)
    pct = round(spent * 100 / limit, 1) if limit > 0 else Decimal('0.0')
    info = {
        'spent': spent,
        'limit': limit,
        'remaining': limit - spent,
        'over_amount': max(spent - limit, Decimal('0.00')),
        'percentage': float(pct),
        'display_percentage': float(min(pct, Decimal('100'))),
        'status': status,
    }
    info.update(STATUS_META[status])
    return info
