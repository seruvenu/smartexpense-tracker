from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tracker.models import Category, Budget, Expense
from decimal import Decimal
import datetime

class Command(BaseCommand):
    help = 'Seeds sample data for demo user exhibiting budget alert states'

    def handle(self, *args, **options):
        username = 'demo'
        password = 'password123'
        
        user, created = User.objects.get_or_create(username=username, defaults={'email': 'demo@example.com'})
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created demo user '{username}' with password '{password}'"))
        else:
            self.stdout.write(f"User '{username}' already exists.")

        month_year = datetime.date.today().strftime('%Y-%m')

        # Categories & Budget Limits
        category_data = [
            ("Dining Out", "Restaurants and coffee", Decimal('200.00'), Decimal('165.00'), 'warning'), # 82.5% -> Warning
            ("Groceries", "Weekly supermarket shopping", Decimal('400.00'), Decimal('250.00'), 'normal'), # 62.5% -> Normal
            ("Entertainment", "Movies, gaming, subscriptions", Decimal('150.00'), Decimal('175.00'), 'danger'), # 116.6% -> Danger
            ("Transportation", "Gas and transit fare", Decimal('100.00'), Decimal('45.00'), 'normal'), # 45% -> Normal
            ("Utilities", "Electricity and Internet bills", Decimal('250.00'), Decimal('250.00'), 'danger'), # 100% -> Danger
        ]

        today = datetime.date.today()

        for name, desc, limit, total_expense, expected_alert in category_data:
            cat, _ = Category.objects.get_or_create(user=user, name=name, defaults={'description': desc})
            
            # Set Budget
            Budget.objects.update_or_create(
                user=user,
                category=cat,
                month_year=month_year,
                defaults={'monthly_limit': limit}
            )

            # Create sample expenses if none exist for this month
            if not Expense.objects.filter(user=user, category=cat, date__year=today.year, date__month=today.month).exists():
                Expense.objects.create(
                    user=user,
                    category=cat,
                    amount=total_expense,
                    date=today - datetime.timedelta(days=2),
                    notes=f"Sample spending for {name}"
                )

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded demo data for {month_year}!"))
