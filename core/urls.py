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

    # Showing all receipts and stickers view paths
    path('allreceipts/', views.all_receipts, name='all_receipts'),
    path('receipts/delete/<int:receipt_id>/', views.delete_receipt, name='delete_receipt'),
    path('receipts/delete-multiple/', views.delete_multiple_receipts, name='delete_multiple_receipts'),
    path('receipts/details/<int:receipt_id>/', views.receipt_details, name='receipt_details'),
    path('receipts/edit/<int:receipt_id>/', views.edit_receipt, name='edit_receipt'),
    path('item/details/<int:item_id>/', views.item_details, name='item_details'),
    path('receipt-item/delete/<int:item_id>/', views.delete_receipt_item, name='delete_receipt_item'),
    path('receipt-item/delete-multiple/', views.delete_multiple_items, name='delete_multiple_items'),
    path('allreceiptitems/', views.all_receipt_items, name='all_receipt_items'),
    path("receipt-item/update/", views.update_receipt_item, name="update_receipt_item"),


    path('allstickers/', views.all_stickers, name='all_stickers'),
    path('stickers/delete/<int:sticker_id>/', views.delete_sticker, name='delete_sticker'),
    path('stickers/delete-multiple/', views.delete_multiple_stickers, name='delete_multiple_stickers'),
    path('stickers/details/<int:sticker_id>/', views.sticker_details, name='sticker_details'),
    path('stickers/edit/<int:sticker_id>/', views.edit_sticker, name='edit_sticker'),
    path('stickerdata/details/<int:stickerdata_id>/', views.sticker_data_details, name='sticker_data_details'),
    path('sticker-data/delete/<int:stickerdata_id>/', views.delete_sticker_data, name='delete_sticker_data'),
    path('sticker-data/delete-multiple/', views.delete_multiple_sticker_data, name='delete_multiple_sticker_data'),
    path('allstickerdata/', views.all_sticker_data, name='all_sticker_data'),
    path("sticker-data/update/", views.update_sticker_data, name="update_sticker_data"),


    path('allmatches/', views.all_matches, name='all_matches'),
    path('matches/delete/<int:match_id>/', views.delete_match, name='delete_match'),
    path('matches/delete-multiple/', views.delete_multiple_matches, name='delete_multiple_matches'),
    path('matches/details/<int:match_id>/', views.match_details, name='match_details'),
    path('allunmatched/', views.all_unmatched, name='all_unmatched'),

]