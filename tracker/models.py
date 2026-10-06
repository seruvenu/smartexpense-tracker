from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from decimal import Decimal

from django.core.validators import MinValueValidator

from .alerts import budget_status
from .money import format_money

class Category(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        unique_together = ('user', 'name')
        ordering = ['name']

    def __str__(self):
        return self.name


class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='budgets')
    monthly_limit = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    month_year = models.CharField(max_length=7)  # Format: YYYY-MM
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'category', 'month_year')
        ordering = ['-month_year', 'category__name']
        constraints = [
            models.CheckConstraint(condition=models.Q(monthly_limit__gt=0), name='budget_limit_positive'),
        ]

    def __str__(self):
        return f"{self.category.name} ({self.month_year}) - {format_money(self.monthly_limit)}"

    def get_spent(self):
        """Calculates total expenses logged for this category in month_year."""
        try:
            year, month = map(int, self.month_year.split('-'))
            total = Expense.objects.filter(
                user=self.user,
                category=self.category,
                date__year=year,
                date__month=month
            ).aggregate(total=Sum('amount'))['total']
            return total if total is not None else Decimal('0.00')
        except (ValueError, TypeError):
            return Decimal('0.00')

    @property
    def remaining_budget(self):
        return self.monthly_limit - self.get_spent()

    @property
    def spent_amount(self):
        return self.get_spent()

    @property
    def percentage_spent(self):
        spent = self.get_spent()
        if self.monthly_limit > 0:
            return round((spent / self.monthly_limit) * 100, 1)
        return 0.0

    def get_alert_info(self):
        """Returns threshold alert state, badge classes, and remaining budget.

        The rules live in tracker/alerts.py so the dashboard, the notification
        bell and the unit tests all use exactly the same logic.
        """
        return budget_status(self.get_spent(), self.monthly_limit)


class Expense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='expenses')
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    date = models.DateField()
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='expense_amount_positive'),
        ]
        indexes = [  # the dashboard and expense list filter by user + date / category
            models.Index(fields=['user', 'date'], name='expense_user_date_idx'),
            models.Index(fields=['user', 'category', 'date'], name='expense_user_cat_date_idx'),
        ]

    def __str__(self):
        return f"{format_money(self.amount)} on {self.date} ({self.category.name})"
