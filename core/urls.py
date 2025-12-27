from django.urls import path, include
from core import views
urlpatterns = [
    # authentication paths
    path('register', views.register, name="register"),
    path('verify-email', views.emailverification, name="emailverification"),
    path('resend-verification', views.resend_verification, name='resend_verification'),
    path('login', views.login, name='login'),
    path('forgot-password', views.forgotpassword, name="forgotpassword"),
    path('email-verify', views.forgotpasswordemailverify, name="forgotpasswordemailverify"),
    path('reset-password', views.resetpassword, name="resetpassword"),
    path('logout', views.logout, name='logout'),

    # dashboard paths
    path('Upload-section', views.admindashboard, name='dashboard'),
    path('hemloo', views.dashboard_dd, name='dashboard_dd'),
    path('', views.searchablepanel, name='searchablepanel'),
    path('dashboard/search', views.search_dashboard, name='dashboard_search'),
    path('search/inventory', views.search_dashboard, name='search_dashboard'),

    # upload Receipts and Stickers imgs
    path('receipts', views.upload_receipts, name='upload_receipts'),
    path('stickers', views.upload_stickers, name='upload_stickers'),

    # Showing all receipts view paths
    path('allreceipts', views.all_receipts, name='all_receipts'),
    path('receipts/delete/<int:receipt_id>', views.delete_receipt, name='delete_receipt'),
    path('receipts/delete-multiple', views.delete_multiple_receipts, name='delete_multiple_receipts'),
    path('receipts/details/<int:receipt_id>', views.receipt_details, name='receipt_details'),
    path('receipts/edit/<int:receipt_id>', views.edit_receipt, name='edit_receipt'),
    path('item/details/<int:item_id>', views.item_details, name='item_details'),
    path('receipt-item/delete/<int:item_id>', views.delete_receipt_item, name='delete_receipt_item'),
    path('receipt-item/delete-multiple', views.delete_multiple_items, name='delete_multiple_items'),
    path('allreceiptitems', views.all_receipt_items, name='all_receipt_items'),
    path("receipt-item/update", views.update_receipt_item, name="update_receipt_item"),

    # Showing all stickers view paths
    path('allstickers', views.all_stickers, name='all_stickers'),
    path('stickers/delete/<int:sticker_id>', views.delete_sticker, name='delete_sticker'),
    path('stickers/delete-multiple', views.delete_multiple_stickers, name='delete_multiple_stickers'),
    path('stickers/details/<int:sticker_id>', views.sticker_details, name='sticker_details'),
    path('stickers/edit/<int:sticker_id>', views.edit_sticker, name='edit_sticker'),
    path('stickerdata/details/<int:stickerdata_id>', views.sticker_data_details, name='sticker_data_details'),
    path('sticker-data/delete/<int:stickerdata_id>', views.delete_sticker_data, name='delete_sticker_data'),
    path('sticker-data/delete-multiple', views.delete_multiple_sticker_data, name='delete_multiple_sticker_data'),
    path('allstickerdata', views.all_sticker_data, name='all_sticker_data'),
    path("sticker-data/update", views.update_sticker_data, name="update_sticker_data"),

    # Showing all matched_products view paths
    path('allmatches', views.all_matches, name='all_matches'),
    path('matches/delete/<int:match_id>', views.delete_match, name='delete_match'),
    path('matches/delete-multiple', views.delete_multiple_matches, name='delete_multiple_matches'),
    path('matches/details/<int:match_id>', views.match_details, name='match_details'),
    path('allunmatched', views.all_unmatched, name='all_unmatched'),
   
   # Showing all ASIN's view paths
    path("asins/upload", views.asin_upload_page, name="asin_upload_page"),
    path("asins/upload-file/", views.upload_asins_file, name="upload_asins_csv"),
    path("asins/all", views.all_asins, name="all_asins"),

    path('matched-products', views.all_matched_products, name='all_matched_products'),
    path('run-matching', views.run_matching, name='run_matching'),
    path('update-receipt-item', views.update_receipt_item, name='update_receipt_item'),  
]