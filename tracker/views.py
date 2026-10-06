from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib import messages
from django.db.models import Sum
from django.views.decorators.http import require_POST
from decimal import Decimal
import datetime

from .models import Category, Budget, Expense
from .forms import UserRegistrationForm, CategoryForm, BudgetForm, ExpenseForm
from .services import month_summary, parse_month, shift_month
from .alerts import budget_status
from .money import format_money


# Default categories for new users
DEFAULT_CATEGORIES = [
    ("Food", "Dining, groceries, and drinks"),
    ("Transportation", "Fuel, public transit, rideshare, car maintenance"),
    ("Housing", "Rent, mortgage, property tax, maintenance"),
    ("Utilities", "Electricity, water, internet, phone bills"),
    ("Entertainment", "Movies, games, subscriptions, leisure"),
    ("Shopping", "Clothing, electronics, personal items"),
    ("Healthcare", "Medical expenses, pharmacy, health insurance"),
]

def auto_create_default_categories(user):
    """Populates standard expense categories for a new user if none exist."""
    if not Category.objects.filter(user=user).exists():
        for name, desc in DEFAULT_CATEGORIES:
            Category.objects.create(user=user, name=name, description=desc)


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auto_create_default_categories(user)
            login(request, user)
            messages.success(request, f"Welcome to SmartExpense, {user.username}! Default categories have been created for you.")
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()

    return render(request, 'tracker/register.html', {'form': form})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')


@login_required
def dashboard(request):
    user = request.user
    auto_create_default_categories(user)

    selected_month, year, month = parse_month(request.GET.get('month'))
    summary = month_summary(user, selected_month)  # all calculations live in services.py

    context = {
        **summary,
        'selected_month': selected_month,
        'selected_date': datetime.date(year, month, 1),
        'prev_month': shift_month(year, month, -1),
        'next_month': shift_month(year, month, 1),
        'recent_expenses': Expense.objects.filter(user=user).select_related('category')[:5],
        'expense_form': ExpenseForm(user=user),
    }
    return render(request, 'tracker/dashboard.html', context)


@login_required
def expense_create(request):
    """
    POST /expenses/create/: Accepts form data (amount, date, category, notes).
    Returns HTTP 302 redirect on success or HTTP 200 with validation errors.
    """
    if request.method == 'POST':
        post_data = request.POST.copy()
        
        # Handle category passed as name string (e.g. category="Food") or ID
        cat_input = post_data.get('category', '').strip()
        if cat_input and not cat_input.isdigit():
            cat = Category.objects.filter(user=request.user, name__iexact=cat_input).first()
            if cat:
                post_data['category'] = str(cat.id)

        form = ExpenseForm(post_data, user=request.user)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            messages.success(request, f"Logged expense of {format_money(expense.amount)} for {expense.category.name}.")
            return redirect('dashboard') # 302 Redirect
        else:
            # HTTP 200 response with validation errors
            return render(request, 'tracker/expense_form.html', {
                'form': form,
                'title': 'Log New Expense',
                'action_url': '/expenses/create/',
            }, status=200)
    else:
        form = ExpenseForm(user=request.user)
        return render(request, 'tracker/expense_form.html', {
            'form': form,
            'title': 'Log New Expense',
            'action_url': '/expenses/create/',
        })


@login_required
def expense_list(request):
    user = request.user
    selected_month = request.GET.get('month', '')
    selected_category = request.GET.get('category', '')

    expenses = Expense.objects.filter(user=user).select_related('category')
    
    if selected_month:
        try:
            year, month = map(int, selected_month.split('-'))
            expenses = expenses.filter(date__year=year, date__month=month)
        except ValueError:
            pass

    if selected_category.isdigit():  # ignore junk like ?category=abc instead of crashing
        expenses = expenses.filter(category_id=int(selected_category))
    else:
        selected_category = ''

    categories = Category.objects.filter(user=user)
    
    context = {
        'expenses': expenses,
        'categories': categories,
        'selected_month': selected_month,
        'selected_category': selected_category,
    }
    return render(request, 'tracker/expense_list.html', context)


@login_required
def expense_update(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Expense updated successfully.")
            return redirect('expense_list')
    else:
        form = ExpenseForm(instance=expense, user=request.user)

    return render(request, 'tracker/expense_form.html', {
        'form': form,
        'title': 'Edit Expense',
        'is_update': True,
        'expense': expense,
    })


@login_required
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        amount = expense.amount
        cat_name = expense.category.name
        expense.delete()
        messages.success(request, f"Deleted expense of {format_money(amount)} ({cat_name}).")
        return redirect('expense_list')
    
    return render(request, 'tracker/expense_confirm_delete.html', {'expense': expense})


@login_required
def category_list(request):
    categories = Category.objects.filter(user=request.user)
    # Add count of linked expenses & budgets to each category
    cat_data = []
    for cat in categories:
        cat_data.append({
            'category': cat,
            'expense_count': cat.expenses.count(),
            'budget_count': cat.budgets.count(),
        })

    return render(request, 'tracker/category_list.html', {'categories_data': cat_data})


@login_required
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, user=request.user)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, f"Category '{category.name}' created.")
            return redirect('category_list')
    else:
        form = CategoryForm(user=request.user)

    return render(request, 'tracker/category_form.html', {'form': form, 'title': 'Create New Category'})


@login_required
def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{category.name}' updated.")
            return redirect('category_list')
    else:
        form = CategoryForm(instance=category, user=request.user)

    return render(request, 'tracker/category_form.html', {'form': form, 'title': 'Edit Category', 'category': category})


@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    expense_count = category.expenses.count()
    budget_count = category.budgets.count()

    if request.method == 'POST':
        name = category.name
        category.delete() # Handles cascading safely per schema
        messages.success(request, f"Category '{name}' and associated records deleted safely.")
        return redirect('category_list')

    return render(request, 'tracker/category_confirm_delete.html', {
        'category': category,
        'expense_count': expense_count,
        'budget_count': budget_count,
    })


@login_required
def budget_list(request):
    user = request.user
    selected_month = request.GET.get('month', datetime.date.today().strftime('%Y-%m'))
    budgets = Budget.objects.filter(user=user, month_year=selected_month).select_related('category')
    _, year, month = parse_month(selected_month)
    spent_map = {  # one query for every category, instead of one per budget
        row['category_id']: row['total']
        for row in Expense.objects.filter(user=user, date__year=year, date__month=month)
        .values('category_id').annotate(total=Sum('amount'))
    }

    budget_info = [
        {'budget': b, 'alert_info': budget_status(spent_map.get(b.category_id, Decimal('0.00')), b.monthly_limit)}
        for b in budgets
    ]

    return render(request, 'tracker/budget_list.html', {
        'budget_info': budget_info,
        'selected_month': selected_month,
    })


@login_required
def budget_create_or_update(request):
    user = request.user
    if request.method == 'POST':
        form = BudgetForm(request.POST, user=user)
        if form.is_valid():
            category = form.cleaned_data['category']
            month_year = form.cleaned_data['month_year']
            monthly_limit = form.cleaned_data['monthly_limit']

            budget, created = Budget.objects.update_or_create(
                user=user,
                category=category,
                month_year=month_year,
                defaults={'monthly_limit': monthly_limit}
            )

            action_text = "set" if created else "updated"
            messages.success(request, f"Monthly budget of {format_money(monthly_limit)} {action_text} for {category.name} ({month_year}).")
            return redirect('budget_list')
    else:
        initial_category = request.GET.get('category')
        initial_month = request.GET.get('month', datetime.date.today().strftime('%Y-%m'))
        form = BudgetForm(user=user, initial={'category': initial_category, 'month_year': initial_month})

    return render(request, 'tracker/budget_form.html', {'form': form, 'title': 'Set Monthly Category Budget'})


@login_required
def budget_update(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=budget, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Budget for {budget.category.name} updated.")
            return redirect('budget_list')
    else:
        form = BudgetForm(instance=budget, user=request.user)

    return render(request, 'tracker/budget_form.html', {'form': form, 'title': 'Edit Budget', 'budget': budget})


@login_required
def budget_delete(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        cat_name = budget.category.name
        m_year = budget.month_year
        budget.delete()
        messages.success(request, f"Budget for {cat_name} ({m_year}) removed.")
        return redirect('budget_list')

    return render(request, 'tracker/budget_confirm_delete.html', {'budget': budget})
