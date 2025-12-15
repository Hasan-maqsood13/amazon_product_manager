from django.db import models
from django.utils import timezone
from .utils import receipt_upload_path
from .utils import sticker_upload_path
# Create your models here.
class User(models.Model):
    # Neccessary Info
    username = models.CharField(max_length=33, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    # Verification
    verification_token = models.CharField(max_length=255, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
 
    # Account Management
    Role_choices = (
        ('admin', 'Admin'),
        ('user', 'user'),
    )
    role = models.CharField(max_length=10, choices=Role_choices, default='user')
 
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    last_updated = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)
    def __str__(self):
        return f"{self.username} - {self.email} - {self.role}"
# Receipts models
class receipts(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='receipts'
    )
    image_path = models.FileField(upload_to=receipt_upload_path)  # Changed to FileField for PDF support
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    upload_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, default='pending')
    year = models.IntegerField()
    month = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    raw_ocr_text = models.TextField(blank=True, null=True) # Added for full raw OCR text
    def __str__(self):
        return f"Receipt #{self.id} - {self.original_filename} - {self.status}"
class receipt_items(models.Model):
    id = models.AutoField(primary_key=True)
    receipt = models.ForeignKey(
        receipts,
        on_delete=models.CASCADE,
        related_name='items'
    )
    line_number = models.IntegerField()
    sku = models.CharField(max_length=100, null=True, blank=True)
    product_name = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    raw_text = models.TextField(null=True, blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=50, default='processed') # New field added for flagging
    def __str__(self):
        return f"Item #{self.line_number} - {self.product_name or 'Unknown'} - SKU => {self.sku or ''} - Receipt #{self.receipt or ''} - -- - Status: {self.status}"
# Stickers models
class stickers(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='stickers'
    )
    image_path = models.ImageField(upload_to=sticker_upload_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    upload_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, default='pending')
    year = models.IntegerField()
    month = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    def __str__(self):
        return f"Sticker #{self.id} - {self.original_filename}"
 
 
class sticker_data(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='stickers_data'
    )
    image_path = models.CharField(max_length=500)
    barcode = models.CharField(max_length=100, blank=True, null=True)
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    upload_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, default='pending')
    year = models.IntegerField()
    month = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    MATCHING_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('unmatched', 'Unmatched'),
    )
    matching_status = models.CharField(
        max_length=20,
        choices=MATCHING_STATUS_CHOICES,
        default='pending'
    )
    def __str__(self):
        return f"StickerData #{self.id} - {self.original_filename}"
class match_history(models.Model):
    id = models.AutoField(primary_key=True)
    sticker_data = models.ForeignKey(
        sticker_data,
        on_delete=models.CASCADE,
        related_name='matches'
    )
    receipt_item = models.ForeignKey(
        receipt_items,
        on_delete=models.CASCADE,
        related_name='matches'
    )
    matched_at = models.DateTimeField(default=timezone.now)
    SKU = models.CharField(max_length=100)
    def __str__(self):
        return f"Match #{self.id} - StickerData #{self.sticker_data.id} to ReceiptItem #{self.receipt_item.id} - SKU: {self.SKU}"