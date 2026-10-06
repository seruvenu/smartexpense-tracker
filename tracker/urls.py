from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import StyledPasswordResetForm, StyledSetPasswordForm

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    
    # Expense routes
    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/create/', views.expense_create, name='expense_create'),
    path('expenses/<int:pk>/update/', views.expense_update, name='expense_update'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='expense_delete'),

    # Category routes
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/update/', views.category_update, name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

    # Budget routes
    path('budgets/', views.budget_list, name='budget_list'),
    path('budgets/set/', views.budget_create_or_update, name='budget_set'),
    path('budgets/<int:pk>/update/', views.budget_update, name='budget_update'),
    path('budgets/<int:pk>/delete/', views.budget_delete, name='budget_delete'),

    # Auth routes
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='tracker/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Forgot password
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='tracker/password_reset_form.html',
        email_template_name='tracker/password_reset_email.txt',
        form_class=StyledPasswordResetForm), name='password_reset'),
    path('password-reset/sent/', auth_views.PasswordResetDoneView.as_view(
        template_name='tracker/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='tracker/password_reset_confirm.html',
        form_class=StyledSetPasswordForm), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='tracker/password_reset_complete.html'), name='password_reset_complete'),
]
