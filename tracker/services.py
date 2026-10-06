"""Database-backed helpers shared by the dashboard view and the notification bell."""
import calendar
import datetime
from decimal import Decimal

from django.db.models import Sum

from .alerts import STATUS_ORDER, budget_status
from .models import Budget, Category, Expense


def parse_month(value):
    """Return ('YYYY-MM', year, month). Falls back to the current month on bad input."""
    today = datetime.date.today()
    try:
        year, month = map(int, str(value).split('-'))
        datetime.date(year, month, 1)  # raises ValueError for month 13, year 0, ...
    except (ValueError, TypeError):
        year, month = today.year, today.month
    return f"{year:04d}-{month:02d}", year, month


def shift_month(year, month, delta):
    """Return the 'YYYY-MM' string `delta` months away from year/month."""
    index = year * 12 + (month - 1) + delta
    new_year, new_month = divmod(index, 12)
    return f"{new_year:04d}-{new_month + 1:02d}"


def forecast_month_end(year, month, budgeted_spent, total_budget, today=None):
    """Projected month-end spending, only for the month that is currently running."""
    today = today or datetime.date.today()
    if (year, month) != (today.year, today.month) or total_budget <= 0 or budgeted_spent <= 0:
        return None
    days_in_month = calendar.monthrange(year, month)[1]
    projected = (budgeted_spent / Decimal(today.day) * Decimal(days_in_month)).quantize(Decimal('0.01'))
    return {
        'projected': projected,
        'will_exceed': projected > total_budget,
        'difference': abs(projected - total_budget),
        'days_left': days_in_month - today.day,
    }


def month_summary(user, month_str, today=None):
    """Everything the dashboard needs for one user and one month (3 queries)."""
    month_str, year, month = parse_month(month_str)

    categories = list(Category.objects.filter(user=user))
    budgets = {b.category_id: b for b in Budget.objects.filter(user=user, month_year=month_str)}
    spent_rows = (
        Expense.objects.filter(user=user, date__year=year, date__month=month)
        .values('category_id')
        .annotate(total=Sum('amount'))
    )
    spent_map = {row['category_id']: row['total'] for row in spent_rows}

    budgeted, unbudgeted = [], []
    total_spent = Decimal('0.00')
    total_budget = Decimal('0.00')
    budgeted_spent = Decimal('0.00')

    for category in categories:
        spent = spent_map.get(category.id, Decimal('0.00'))
        total_spent += spent
        budget = budgets.get(category.id)
        if budget is not None:
            row = budget_status(spent, budget.monthly_limit)
            row.update({'category': category, 'budget': budget})
            budgeted.append(row)
            total_budget += budget.monthly_limit
            budgeted_spent += spent
        elif spent > 0:
            unbudgeted.append({'category': category, 'spent': spent})

    # Worst first: danger, then warning, then normal; highest % first inside each group.
    budgeted.sort(key=lambda r: (STATUS_ORDER[r['status']], -r['percentage'], r['category'].name.lower()))
    unbudgeted.sort(key=lambda r: -r['spent'])

    counts = {'danger': 0, 'warning': 0, 'normal': 0}
    for row in budgeted:
        counts[row['status']] += 1
    counts['all'] = len(budgeted)

    chart_rows = [(r['category'].name, r['spent']) for r in budgeted if r['spent'] > 0]
    chart_rows += [(r['category'].name, r['spent']) for r in unbudgeted]
    chart_rows.sort(key=lambda item: -item[1])

    return {
        'budgeted': budgeted,
        'unbudgeted': unbudgeted,
        'has_budgets': bool(budgeted),
        'total_spent': total_spent,
        'total_budget': total_budget,
        'budgeted_spent': budgeted_spent,
        'unbudgeted_spent': total_spent - budgeted_spent,
        # "Remaining" only compares budgeted categories with their own budgets.
        'total_remaining': total_budget - budgeted_spent,
        'overall': budget_status(budgeted_spent, total_budget),
        'counts': counts,
        'chart_data': {
            'labels': [name for name, _ in chart_rows],
            'values': [float(amount) for _, amount in chart_rows],
        },
        'forecast': forecast_month_end(year, month, budgeted_spent, total_budget, today),
    }
