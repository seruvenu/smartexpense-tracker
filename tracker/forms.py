from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from decimal import Decimal
import datetime
from .models import Category, Budget, Expense

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'}))

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Food, Rent, Entertainment'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional description...'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError("Category name cannot be empty.")
        if self.user:
            qs = Category.objects.filter(user=self.user, name__iexact=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("You already have a category with this name.")
        return name


class BudgetForm(forms.ModelForm):
    month_year = forms.CharField(
        widget=forms.TextInput(attrs={'type': 'month', 'class': 'form-control'}),
        help_text="Select target month and year (e.g. 2026-10)"
    )

    class Meta:
        model = Budget
        fields = ['category', 'monthly_limit', 'month_year']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'monthly_limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['category'].queryset = Category.objects.filter(user=self.user)
        if not self.initial.get('month_year'):
            self.initial['month_year'] = datetime.date.today().strftime('%Y-%m')

    def clean_monthly_limit(self):
        limit = self.cleaned_data.get('monthly_limit')
        if limit is None or limit <= Decimal('0.00'):
            raise ValidationError("Monthly budget limit must be greater than zero.")
        return limit

    def clean_month_year(self):
        val = self.cleaned_data.get('month_year', '').strip()
        if not val:
            val = datetime.date.today().strftime('%Y-%m')
        # Validate format YYYY-MM
        try:
            parts = val.split('-')
            if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
                raise ValueError()
            int(parts[0])
            m = int(parts[1])
            if m < 1 or m > 12:
                raise ValueError()
        except ValueError:
            raise ValidationError("Invalid month format. Please use YYYY-MM format.")
        return val

    def clean(self):
        cleaned = super().clean()
        cat = cleaned.get('category')
        month = cleaned.get('month_year')
        # Only when EDITING a budget: moving it onto a category + month that already has
        # one would crash on the unique constraint. (The "Set Monthly Limit" form has no
        # instance and intentionally updates an existing budget, so it is not checked.)
        if self.instance.pk and self.user and cat and month:
            clash = Budget.objects.filter(
                user=self.user, category=cat, month_year=month
            ).exclude(pk=self.instance.pk)
            if clash.exists():
                raise ValidationError("A budget for this category and month already exists.")
        return cleaned


class ExpenseForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=datetime.date.today
    )

    class Meta:
        model = Expense
        fields = ['amount', 'date', 'category', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'maxlength': 500, 'placeholder': 'Optional notes (e.g. Lunch with client)'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['category'].queryset = Category.objects.filter(user=self.user)

    def clean_notes(self):
        notes = (self.cleaned_data.get('notes') or '').strip()
        if len(notes) > 500:
            raise ValidationError("Notes can be at most 500 characters.")
        return notes

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= Decimal('0.00'):
            raise ValidationError("Expense amount must be greater than zero.")
        return amount


from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm


class StyledPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'you@example.com', 'autofocus': True})


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
