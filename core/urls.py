from django.urls import path, include
from core import views

urlpatterns = [
    path('', views.home, name='home'),

    # authentication paths
    path('register/', views.register, name="register"),
    path('verify-email/', views.emailverification, name="emailverification"),
    path('resend-verification/', views.resend_verification, name='resend_verification'),
    path('login/', views.login, name='login'),
    path('forgot-password/', views.forgotpassword, name="forgotpassword"),
    path('email-verify/', views.forgotpasswordemailverify, name="forgotpasswordemailverify"),
    path('reset-password/', views.resetpassword, name="resetpassword"),
    path('logout/', views.logout, name='logout'),

    # dashboard paths
    path('dashboard/', views.admindashboard, name='dashboard'),
    path('hemloo/', views.dashboard_dd, name='dashboard_dd'),


    # upload Receipts and Stickers imgs
    path('receipts/', views.upload_receipts, name='upload_receipts'),
    path('stickers/', views.upload_stickers, name='upload_stickers'),
]