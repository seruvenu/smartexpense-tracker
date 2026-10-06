import datetime

from .services import month_summary


def budget_notifications(request):
    """Adds the data for the navbar notification bell to every template."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}

    today = datetime.date.today()
    summary = month_summary(user, today.strftime('%Y-%m'), today)
    alerts = [row for row in summary['budgeted'] if row['status'] != 'normal']  # worst first
    return {
        'nav_alerts': alerts,
        'nav_alert_count': len(alerts),
        'nav_alert_has_danger': any(row['status'] == 'danger' for row in alerts),
        'nav_alert_month': today,
    }
