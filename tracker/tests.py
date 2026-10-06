from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from decimal import Decimal
import datetime

from tracker.models import Category, Budget, Expense
from tracker.forms import BudgetForm


class UserAuthAndIsolationTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='Password123!')
        self.user2 = User.objects.create_user(username='user2', password='Password123!')
        self.client1 = Client()
        self.client1.login(username='user1', password='Password123!')
        self.client2 = Client()
        self.client2.login(username='user2', password='Password123!')

    def test_unauthenticated_redirect(self):
        """Unauthenticated access to dashboard/expenses/budgets/categories redirects to login."""
        unauth_client = Client()
        urls_to_test = [
            reverse('dashboard'),
            reverse('expense_list'),
            reverse('category_list'),
            reverse('budget_list'),
        ]
        for url in urls_to_test:
            response = unauth_client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login/', response.url)

    def test_user_data_isolation(self):
        """Users can only view and interact with their own categories and expenses."""
        cat1 = Category.objects.create(user=self.user1, name='User1 Category')
        cat2 = Category.objects.create(user=self.user2, name='User2 Category')

        Expense.objects.create(user=self.user1, category=cat1, amount=Decimal('50.00'), date='2026-10-01')
        exp2 = Expense.objects.create(user=self.user2, category=cat2, amount=Decimal('100.00'), date='2026-10-01')

        # User 1 dashboard should only list cat1 and exp1
        resp = self.client1.get(reverse('dashboard'))
        self.assertContains(resp, 'User1 Category')
        self.assertNotContains(resp, 'User2 Category')

        # User 1 trying to edit/delete User 2 expense gets 404
        edit_url = reverse('expense_update', kwargs={'pk': exp2.pk})
        resp_edit = self.client1.get(edit_url)
        self.assertEqual(resp_edit.status_code, 404)


class BudgetCalculationAndAlertTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='Password123!')
        self.category = Category.objects.create(user=self.user, name='Dining Out')
        self.month_year = '2026-10'

    def test_budget_spent_and_remaining_calculation(self):
        """Test calculation of total spent and remaining budget for a category."""
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            monthly_limit=Decimal('200.00'),
            month_year=self.month_year
        )

        Expense.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal('45.50'),
            date=datetime.date(2026, 10, 5),
            notes='Dinner'
        )
        Expense.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal('24.50'),
            date=datetime.date(2026, 10, 10),
            notes='Lunch'
        )

        total_spent = budget.get_spent()
        self.assertEqual(total_spent, Decimal('70.00'))
        self.assertEqual(budget.remaining_budget, Decimal('130.00'))
        self.assertEqual(budget.percentage_spent, 35.0)

    def test_alert_threshold_normal_state(self):
        """Spending below 80% should yield 'normal' alert state."""
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            monthly_limit=Decimal('100.00'),
            month_year=self.month_year
        )
        # 50% spending
        Expense.objects.create(user=self.user, category=self.category, amount=Decimal('50.00'), date='2026-10-01')
        
        info = budget.get_alert_info()
        self.assertEqual(info['status'], 'normal')
        self.assertEqual(info['label'], 'Normal')
        self.assertEqual(info['badge_class'], 'bg-success')

    def test_alert_threshold_warning_state(self):
        """Spending at or above 80% and below 100% should yield 'warning' alert state."""
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            monthly_limit=Decimal('100.00'),
            month_year=self.month_year
        )
        # Exactly 80% spending
        Expense.objects.create(user=self.user, category=self.category, amount=Decimal('80.00'), date='2026-10-01')
        
        info = budget.get_alert_info()
        self.assertEqual(info['status'], 'warning')
        self.assertEqual(info['label'], 'Warning')
        self.assertIn('bg-warning', info['badge_class'])

        # 95% spending
        Expense.objects.create(user=self.user, category=self.category, amount=Decimal('15.00'), date='2026-10-02')
        info_95 = budget.get_alert_info()
        self.assertEqual(info_95['status'], 'warning')

    def test_alert_threshold_danger_state(self):
        """Spending at or above 100% should yield 'danger' alert state."""
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            monthly_limit=Decimal('100.00'),
            month_year=self.month_year
        )
        # Exactly 100% spending
        Expense.objects.create(user=self.user, category=self.category, amount=Decimal('100.00'), date='2026-10-01')
        
        info = budget.get_alert_info()
        self.assertEqual(info['status'], 'danger')
        self.assertEqual(info['label'], 'Danger')
        self.assertEqual(info['badge_class'], 'bg-danger')

        # 120% spending
        Expense.objects.create(user=self.user, category=self.category, amount=Decimal('20.00'), date='2026-10-02')
        info_120 = budget.get_alert_info()
        self.assertEqual(info_120['status'], 'danger')


class ExpenseCreateEndpointTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='expuser', password='Password123!')
        self.client = Client()
        self.client.login(username='expuser', password='Password123!')
        self.category = Category.objects.create(user=self.user, name='Food')

    def test_post_expense_create_valid_id(self):
        """POST /expenses/create/ with valid data returns HTTP 302 redirect on success."""
        response = self.client.post(reverse('expense_create'), {
            'amount': '45.50',
            'date': '2023-10-15',
            'category': str(self.category.id),
            'notes': 'Lunch with client'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))

        # Verify DB object
        exp = Expense.objects.get(user=self.user)
        self.assertEqual(exp.amount, Decimal('45.50'))
        self.assertEqual(str(exp.date), '2023-10-15')
        self.assertEqual(exp.category, self.category)
        self.assertEqual(exp.notes, 'Lunch with client')

    def test_post_expense_create_by_category_name(self):
        """POST /expenses/create/ accepting category name string."""
        response = self.client.post(reverse('expense_create'), {
            'amount': '25.00',
            'date': '2023-10-16',
            'category': 'Food',
            'notes': 'Coffee'
        })
        self.assertEqual(response.status_code, 302)
        exp = Expense.objects.get(notes='Coffee')
        self.assertEqual(exp.category, self.category)

    def test_post_expense_create_invalid_negative_amount(self):
        """Form validation must reject negative amounts and return HTTP 200 with errors."""
        response = self.client.post(reverse('expense_create'), {
            'amount': '-15.00',
            'date': '2023-10-15',
            'category': str(self.category.id),
            'notes': 'Invalid negative amount'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'amount', 'Expense amount must be greater than zero.')

    def test_post_expense_create_zero_amount(self):
        """Form validation must reject zero amounts."""
        response = self.client.post(reverse('expense_create'), {
            'amount': '0.00',
            'date': '2023-10-15',
            'category': str(self.category.id),
            'notes': 'Zero amount'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'amount', 'Expense amount must be greater than zero.')


class CategoryCRUDTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='catuser', password='Password123!')
        self.client = Client()
        self.client.login(username='catuser', password='Password123!')

    def test_category_create_update_delete(self):
        """Test full CRUD lifecycle for categories."""
        # Create
        resp_create = self.client.post(reverse('category_create'), {
            'name': 'Travel',
            'description': 'Flights and hotels'
        })
        self.assertEqual(resp_create.status_code, 302)
        cat = Category.objects.get(user=self.user, name='Travel')

        # Update
        resp_update = self.client.post(reverse('category_update', kwargs={'pk': cat.pk}), {
            'name': 'Travel & Vacations',
            'description': 'Updated desc'
        })
        self.assertEqual(resp_update.status_code, 302)
        cat.refresh_from_db()
        self.assertEqual(cat.name, 'Travel & Vacations')

        # Delete
        resp_delete = self.client.post(reverse('category_delete', kwargs={'pk': cat.pk}))
        self.assertEqual(resp_delete.status_code, 302)
        self.assertFalse(Category.objects.filter(pk=cat.pk).exists())


# ======================================================================
# Added: shared alert logic, month summary, dashboard, notification bell
# ======================================================================
from django.conf import settings
from django.test import SimpleTestCase, override_settings

from tracker.alerts import budget_status, get_status
from tracker.services import forecast_month_end, month_summary, parse_month, shift_month
from tracker.templatetags.tracker_extras import money, money_abs


class BudgetStatusLogicTests(SimpleTestCase):
    """Boundary tests for the 80% warning / 100% danger rules."""

    def test_threshold_boundaries(self):
        limit = Decimal('100.00')
        cases = [
            ('0.00', 'normal'),
            ('79.99', 'normal'),
            ('80.00', 'warning'),
            ('99.99', 'warning'),
            ('100.00', 'danger'),
            ('100.01', 'danger'),
            ('250.00', 'danger'),
        ]
        for spent, expected in cases:
            with self.subTest(spent=spent):
                self.assertEqual(get_status(Decimal(spent), limit), expected)
                self.assertEqual(budget_status(Decimal(spent), limit)['status'], expected)

    def test_zero_limit_is_normal_and_safe(self):
        info = budget_status(Decimal('50.00'), Decimal('0.00'))
        self.assertEqual(info['status'], 'normal')
        self.assertEqual(info['percentage'], 0.0)

    def test_numbers_for_warning_budget(self):
        info = budget_status(Decimal('165.00'), Decimal('200.00'))
        self.assertEqual(info['percentage'], 82.5)
        self.assertEqual(info['remaining'], Decimal('35.00'))
        self.assertEqual(info['over_amount'], Decimal('0.00'))
        self.assertEqual(info['label'], 'Warning')

    def test_numbers_for_over_budget(self):
        info = budget_status(Decimal('275.00'), Decimal('30.00'))
        self.assertEqual(info['percentage'], 916.7)
        self.assertEqual(info['display_percentage'], 100.0)  # bar never overflows
        self.assertEqual(info['over_amount'], Decimal('245.00'))
        self.assertEqual(info['remaining'], Decimal('-245.00'))


class MonthHelperTests(SimpleTestCase):
    def test_parse_month_valid(self):
        self.assertEqual(parse_month('2026-10'), ('2026-10', 2026, 10))

    def test_parse_month_invalid_falls_back_to_current(self):
        current = datetime.date.today().strftime('%Y-%m')
        for bad in ['2026-13', 'abc', '', None, '2026']:
            with self.subTest(value=bad):
                self.assertEqual(parse_month(bad)[0], current)

    def test_shift_month_wraps_years(self):
        self.assertEqual(shift_month(2026, 1, -1), '2025-12')
        self.assertEqual(shift_month(2026, 12, 1), '2027-01')
        self.assertEqual(shift_month(2026, 10, 1), '2026-11')

    def test_forecast_current_month(self):
        today = datetime.date(2026, 10, 10)
        result = forecast_month_end(2026, 10, Decimal('100.00'), Decimal('500.00'), today)
        self.assertEqual(result['projected'], Decimal('310.00'))  # 100 / 10 days * 31 days
        self.assertFalse(result['will_exceed'])
        self.assertEqual(result['days_left'], 21)

        result = forecast_month_end(2026, 10, Decimal('200.00'), Decimal('500.00'), today)
        self.assertEqual(result['projected'], Decimal('620.00'))
        self.assertTrue(result['will_exceed'])

    def test_forecast_skipped_for_other_months_or_no_budget(self):
        today = datetime.date(2026, 10, 10)
        self.assertIsNone(forecast_month_end(2026, 9, Decimal('100'), Decimal('500'), today))
        self.assertIsNone(forecast_month_end(2026, 10, Decimal('100'), Decimal('0'), today))


class MoneyFilterTests(SimpleTestCase):
    def test_default_currency_is_rupee(self):
        self.assertEqual(settings.CURRENCY_SYMBOL, '₹')

    def test_money_formats_negative_numbers_properly(self):
        self.assertEqual(money(Decimal('-245')), '-₹245.00')
        self.assertEqual(money(1234.5), '₹1,234.50')
        self.assertEqual(money(Decimal('45.5')), '₹45.50')
        self.assertEqual(money('not a number'), '₹0.00')

    def test_money_abs(self):
        self.assertEqual(money_abs(Decimal('-245')), '₹245.00')

    @override_settings(CURRENCY_SYMBOL='$')
    def test_symbol_comes_from_settings(self):
        self.assertEqual(money(Decimal('45.5')), '$45.50')


class MonthSummaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sam', password='Password123!')
        self.other = User.objects.create_user(username='other', password='Password123!')
        month = '2026-10'
        self.food = Category.objects.create(user=self.user, name='Food')
        self.rent = Category.objects.create(user=self.user, name='Rent')
        self.fun = Category.objects.create(user=self.user, name='Fun')
        self.misc = Category.objects.create(user=self.user, name='Misc')  # has no budget

        for cat in (self.food, self.rent, self.fun):
            Budget.objects.create(user=self.user, category=cat, monthly_limit=Decimal('100.00'), month_year=month)

        Expense.objects.create(user=self.user, category=self.food, amount=Decimal('85.00'), date=datetime.date(2026, 10, 3))   # warning
        Expense.objects.create(user=self.user, category=self.rent, amount=Decimal('120.00'), date=datetime.date(2026, 10, 4))  # danger
        Expense.objects.create(user=self.user, category=self.fun, amount=Decimal('10.00'), date=datetime.date(2026, 10, 5))    # normal
        Expense.objects.create(user=self.user, category=self.misc, amount=Decimal('40.00'), date=datetime.date(2026, 10, 6))   # unbudgeted
        # These must NOT be counted:
        Expense.objects.create(user=self.user, category=self.food, amount=Decimal('500.00'), date=datetime.date(2026, 9, 28))  # other month
        other_cat = Category.objects.create(user=self.other, name='Food')
        Expense.objects.create(user=self.other, category=other_cat, amount=Decimal('999.00'), date=datetime.date(2026, 10, 3))  # other user

        self.summary = month_summary(self.user, '2026-10')

    def test_categories_sorted_worst_first(self):
        names = [row['category'].name for row in self.summary['budgeted']]
        statuses = [row['status'] for row in self.summary['budgeted']]
        self.assertEqual(names, ['Rent', 'Food', 'Fun'])
        self.assertEqual(statuses, ['danger', 'warning', 'normal'])

    def test_totals_ignore_other_months_and_other_users(self):
        s = self.summary
        self.assertEqual(s['total_spent'], Decimal('255.00'))
        self.assertEqual(s['total_budget'], Decimal('300.00'))
        self.assertEqual(s['budgeted_spent'], Decimal('215.00'))
        self.assertEqual(s['unbudgeted_spent'], Decimal('40.00'))
        self.assertEqual(s['total_remaining'], Decimal('85.00'))

    def test_counts_and_unbudgeted_list(self):
        self.assertEqual(self.summary['counts'], {'danger': 1, 'warning': 1, 'normal': 1, 'all': 3})
        self.assertEqual([r['category'].name for r in self.summary['unbudgeted']], ['Misc'])

    def test_chart_data_sorted_by_amount(self):
        self.assertEqual(self.summary['chart_data']['labels'], ['Rent', 'Food', 'Misc', 'Fun'])
        self.assertEqual(self.summary['chart_data']['values'], [120.0, 85.0, 40.0, 10.0])


class DashboardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dash', password='Password123!')
        self.client = Client()
        self.client.login(username='dash', password='Password123!')
        self.food = Category.objects.create(user=self.user, name='Food')
        self.fun = Category.objects.create(user=self.user, name='Fun')
        self.bills = Category.objects.create(user=self.user, name='Bills')

    def _budget(self, category, limit, spent, month='2026-10', day=2):
        Budget.objects.create(user=self.user, category=category, monthly_limit=Decimal(limit), month_year=month)
        y, m = map(int, month.split('-'))
        Expense.objects.create(user=self.user, category=category, amount=Decimal(spent), date=datetime.date(y, m, day))

    def test_dashboard_shows_all_three_alert_states(self):
        self._budget(self.food, '100.00', '50.00')   # normal
        self._budget(self.fun, '100.00', '85.00')    # warning
        self._budget(self.bills, '100.00', '100.00') # danger
        resp = self.client.get(reverse('dashboard'), {'month': '2026-10'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-status="normal"')
        self.assertContains(resp, 'data-status="warning"')
        self.assertContains(resp, 'data-status="danger"')
        self.assertEqual(resp.context['counts'], {'danger': 1, 'warning': 1, 'normal': 1, 'all': 3})
        self.assertEqual(resp.context['budgeted'][0]['status'], 'danger')

    def test_over_budget_amount_is_not_formatted_as_negative_dollars(self):
        self._budget(self.fun, '30.00', '275.00')
        resp = self.client.get(reverse('dashboard'), {'month': '2026-10'})
        self.assertContains(resp, '₹245.00 over')
        self.assertNotContains(resp, '₹-')
        self.assertNotContains(resp, '$')

    def test_invalid_month_falls_back_to_current_month(self):
        resp = self.client.get(reverse('dashboard'), {'month': '2026-13'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['selected_month'], datetime.date.today().strftime('%Y-%m'))

    def test_set_budget_button_links_to_form_for_selected_month(self):
        self._budget(self.food, '100.00', '50.00', month='2026-10')
        resp = self.client.get(reverse('dashboard'), {'month': '2026-10'})
        self.assertContains(resp, reverse('budget_set') + '?month=2026-10')
        self.assertContains(resp, 'Set budget')

    def test_set_budget_form_opens_on_the_chosen_month(self):
        resp = self.client.get(reverse('budget_set'), {'month': '2026-11'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '2026-11')

    def test_empty_state_prompts_for_first_budget(self):
        resp = self.client.get(reverse('dashboard'), {'month': '2026-10'})
        self.assertContains(resp, 'Set your first budget')

    def test_spending_without_budget_is_listed_with_set_budget_link(self):
        Expense.objects.create(user=self.user, category=self.food, amount=Decimal('12.00'), date=datetime.date(2026, 10, 2))
        resp = self.client.get(reverse('dashboard'), {'month': '2026-10'})
        self.assertContains(resp, 'Spending without a budget')
        self.assertContains(resp, 'Set budget')


class NotificationBellTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='bell', password='Password123!')
        self.other = User.objects.create_user(username='bell2', password='Password123!')
        self.client = Client()
        self.client.login(username='bell', password='Password123!')
        self.month = datetime.date.today().strftime('%Y-%m')

    def _alert(self, user, name, limit, spent):
        cat = Category.objects.create(user=user, name=name)
        Budget.objects.create(user=user, category=cat, monthly_limit=Decimal(limit), month_year=self.month)
        Expense.objects.create(user=user, category=cat, amount=Decimal(spent), date=datetime.date.today())

    def test_bell_counts_only_warning_and_danger(self):
        self._alert(self.user, 'Food', '100.00', '50.00')   # normal -> no notification
        self._alert(self.user, 'Fun', '100.00', '85.00')    # warning
        self._alert(self.user, 'Bills', '100.00', '120.00') # danger
        resp = self.client.get(reverse('budget_list'))
        self.assertEqual(resp.context['nav_alert_count'], 2)
        self.assertTrue(resp.context['nav_alert_has_danger'])
        self.assertEqual(resp.context['nav_alerts'][0]['category'].name, 'Bills')  # worst first
        self.assertContains(resp, 'Notifications')

    def test_bell_ignores_other_users(self):
        self._alert(self.other, 'Bills', '100.00', '150.00')
        resp = self.client.get(reverse('budget_list'))
        self.assertEqual(resp.context['nav_alert_count'], 0)
        self.assertContains(resp, 'No budget alerts this month')


class BudgetEditDuplicateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dup', password='Password123!')
        self.client = Client()
        self.client.login(username='dup', password='Password123!')
        self.food = Category.objects.create(user=self.user, name='Food')
        self.rent = Category.objects.create(user=self.user, name='Rent')
        Budget.objects.create(user=self.user, category=self.food, monthly_limit=Decimal('100.00'), month_year='2026-10')
        self.rent_budget = Budget.objects.create(user=self.user, category=self.rent, monthly_limit=Decimal('100.00'), month_year='2026-10')

    def test_editing_budget_onto_existing_category_month_is_rejected(self):
        data = {'category': self.food.id, 'monthly_limit': '120.00', 'month_year': '2026-10'}
        form = BudgetForm(data, instance=self.rent_budget, user=self.user)
        self.assertFalse(form.is_valid())

    def test_duplicate_edit_shows_error_instead_of_crashing(self):
        data = {'category': self.food.id, 'monthly_limit': '120.00', 'month_year': '2026-10'}
        resp = self.client.post(reverse('budget_update', args=[self.rent_budget.pk]), data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'already exists')

    def test_normal_edit_still_works(self):
        data = {'category': self.rent.id, 'monthly_limit': '150.00', 'month_year': '2026-10'}
        resp = self.client.post(reverse('budget_update', args=[self.rent_budget.pk]), data)
        self.assertEqual(resp.status_code, 302)
        self.rent_budget.refresh_from_db()
        self.assertEqual(self.rent_budget.monthly_limit, Decimal('150.00'))

    def test_set_monthly_limit_form_still_updates_existing_budget(self):
        data = {'category': self.food.id, 'monthly_limit': '175.00', 'month_year': '2026-10'}
        resp = self.client.post(reverse('budget_set'), data)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Budget.objects.filter(user=self.user, category=self.food).count(), 1)
        self.assertEqual(Budget.objects.get(user=self.user, category=self.food).monthly_limit, Decimal('175.00'))


class LogoutTests(TestCase):
    def test_logout_requires_post(self):
        User.objects.create_user(username='lo', password='Password123!')
        client = Client()
        client.login(username='lo', password='Password123!')
        self.assertEqual(client.get(reverse('logout')).status_code, 405)
        resp = client.post(reverse('logout'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp.url)


class ForgotPasswordTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('venu', 'venu@example.com', 'OldPass#12345')

    def test_login_page_links_to_reset(self):
        self.assertContains(self.client.get(reverse('login')), reverse('password_reset'))

    def test_reset_email_and_new_password_works(self):
        from django.core import mail
        resp = self.client.post(reverse('password_reset'), {'email': 'venu@example.com'})
        self.assertRedirects(resp, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        link = [l for l in mail.outbox[0].body.splitlines() if '/reset/' in l][0]
        page = self.client.get(link.split('testserver')[1], follow=True)
        resp = self.client.post(page.redirect_chain[-1][0],
                                {'new_password1': 'Brand#New9876', 'new_password2': 'Brand#New9876'})
        self.assertRedirects(resp, reverse('password_reset_complete'))
        self.assertTrue(self.client.login(username='venu', password='Brand#New9876'))

    def test_unknown_email_gives_same_response_and_sends_nothing(self):
        from django.core import mail
        resp = self.client.post(reverse('password_reset'), {'email': 'nobody@example.com'})
        self.assertRedirects(resp, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)


class OverBudgetMinusTests(TestCase):
    def test_over_budget_amount_shows_minus_everywhere(self):
        user = User.objects.create_user('u', 'u@example.com', 'pw12345!x')
        cat = Category.objects.create(user=user, name='Food')
        month = datetime.date.today().strftime('%Y-%m')
        Budget.objects.create(user=user, category=cat, monthly_limit=Decimal('100'), month_year=month)
        Expense.objects.create(user=user, category=cat, amount=Decimal('345'), date=datetime.date.today())
        self.client.force_login(user)
        for name in ('dashboard', 'budget_list'):
            self.assertContains(self.client.get(reverse(name)), '-₹245.00')

    def test_money_minus_filter(self):
        from tracker.templatetags.tracker_extras import money_minus
        self.assertEqual(money_minus(Decimal('245')), '-₹245.00')
        self.assertEqual(money_minus(Decimal('-245')), '-₹245.00')


class RobustFilterTests(TestCase):
    def test_junk_query_params_do_not_crash(self):
        user = User.objects.create_user('u', 'u@example.com', 'pw12345!x')
        self.client.force_login(user)
        for qs in ('?category=abc', '?month=abc', '?month=2026-13'):
            self.assertEqual(self.client.get(reverse('expense_list') + qs).status_code, 200)
        self.assertEqual(self.client.get(reverse('budget_list') + '?month=zzz').status_code, 200)

    def test_budget_page_query_count_does_not_grow_with_budgets(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        user = User.objects.create_user('u', 'u@example.com', 'pw12345!x')
        month = datetime.date.today().strftime('%Y-%m')
        self.client.force_login(user)

        def add_budget(i):
            cat = Category.objects.create(user=user, name=f'C{i}')
            Budget.objects.create(user=user, category=cat, monthly_limit=Decimal('50'), month_year=month)

        add_budget(0)
        with CaptureQueriesContext(connection) as one:
            self.client.get(reverse('budget_list'))
        for i in range(1, 6):
            add_budget(i)
        with CaptureQueriesContext(connection) as six:
            self.client.get(reverse('budget_list'))
        self.assertEqual(len(one), len(six))


class DataIntegrityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', 'u@example.com', 'pw12345!x')
        self.cat = Category.objects.create(user=self.user, name='Food')

    def test_database_rejects_non_positive_amount(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            Expense.objects.create(user=self.user, category=self.cat, amount=Decimal('0'), date=datetime.date.today())

    def test_database_rejects_non_positive_budget(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            Budget.objects.create(user=self.user, category=self.cat, monthly_limit=Decimal('-1'), month_year='2026-10')

    def test_overlong_notes_are_rejected_by_the_endpoint(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('expense_create'), {
            'amount': '10', 'date': '2026-10-01', 'category': self.cat.id, 'notes': 'x' * 501})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Expense.objects.count(), 0)

    def test_logged_in_user_skips_login_page(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse('login')), reverse('dashboard'))
