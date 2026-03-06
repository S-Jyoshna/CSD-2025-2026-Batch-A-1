from django.contrib import admin
from . import views
from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path('getApprovedLoans/',views.get_approved_loans,name="getApprovedLoans"),
    path('', TemplateView.as_view(template_name='index.html'), name='index'),
    # Single User Login URL: one page (user/login.html) for Home, post-registration, and Apply for Loan redirect.
    path('login/', views.login, name='login'),
    # Single registration page (full fields); Home "Register here" and Login "Sign up" both use this.
    path('signup/', views.signup, name='signup'),
    path('admin/',views.admin,name='admin'),
    path('home/',views.home,name='home'),
    path('profile/', views.profile, name='profile'),
    # Logout: clears session + client sessionStorage (UI/navigation only).
    path('logout/', views.logout_view, name='logout'),
    path('getprofile/',view=views.getprofile,name="getprofile"),
    path('loanrequest/', views.loanrequest, name='loanrequest'),
    path('payment/', views.payment, name='payment'),
    path('loan/<int:loan_id>/pay/', views.payment, name='loan_payment'),
    path('transaction/', views.transaction, name='transaction'),
    path('user/transactions/', views.transaction, name='user_transactions'),
    # Admin-only dashboard route: use unique name to avoid conflicts with user dashboards.
    path('dashboard/', views.dashboard, name='admin_dashboard'),
    path('managecustomer/',views.managecustomer,name='managecustomer'),
    path('manageloanrequest/', views.manageloanrequest,name='manageloanrequest'),
    path('admin/loan/<int:loan_id>/', views.admin_view_loan, name='admin_view_loan'),
    path('profileadmin/',views.profileadmin,name='profileadmin'),
    path('approveLoan/', views.approveloan, name='approveloan'),
    path('rejectLoan/',views.rejectloan,name='rejectloan'),
    path('approve_user/', views.approve_user, name='approve_user'),
    path('reject_user/', views.reject_user, name='reject_user'),
    path('admin/view_customer/<int:user_id>/', views.admin_view_customer, name='admin_view_customer'),
    path('block_user/', views.block_user, name='block_user'),
    path('approved_loans/',views.approved_loans,name='approved_loans'),
    path('applied_loans/',views.applied_loans,name='applied_loans'),
    path('payment/',views.payment,name='payment'),
    path('paymentadmin/',views.paymentadmin,name='paymentadmin'),
    path('submit_feedback/',views.submit_feedback,name='submit_feedback'),
    path('admin_feedback/',views.admin_feedback,name='admin_feedback'),
    path('update_status/', views.update_status, name='update_status'),
    

]
