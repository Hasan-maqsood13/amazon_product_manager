from django.db import models
from django.utils import timezone
from .utils import receipt_upload_path
from .utils import sticker_upload_path
class User(models.Model):
    username = models.CharField(max_length=33, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    verification_token = models.CharField(max_length=255, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
   
    Role_choices = (
        ('admin', 'Admin'),
        ('user', 'user'),
    )
    role = models.CharField(max_length=10, choices=Role_choices, default='user')
   
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_updated = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)
   
    def __str__(self):
        return f"{self.username} - {self.email} - {self.role}"
class receipts(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ]
   
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='receipts'
    )
    image_path = models.FileField(upload_to=receipt_upload_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    upload_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    year = models.IntegerField()
    month = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    raw_ocr_text = models.TextField(blank=True, null=True)
   
    def __str__(self):
        return f"Receipt #{self.id} - {self.original_filename} - {self.status}"
class receipt_items(models.Model):
    STATUS_CHOICES = [
        ('processed', 'Processed'),
        ('flagged', 'Flagged for review'),
    ]
  
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
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='processed')
  
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            required_fields = [self.sku, self.product_name, self.quantity, self.unit_price, self.total_price, self.raw_text]
            if not all(field is not None and field != '' for field in required_fields):
                self.status = 'flagged'
            else:
                self.status = 'processed'
       
        super().save(*args, **kwargs)
       
        if is_new:
            self.match_with_asins()
  
    def match_with_asins(self):
        """ASINs ke sath match karein"""
        try:
            # Agar product name nahi hai to return
            if not self.product_name or self.product_name.strip() == '' or self.product_name == 'Unknown':
                return
          
            product_name_lower = self.product_name.strip().lower()
            user = self.receipt.user
          
            # User ke sare ASINs lo
            user_asins = ASINs.objects.filter(user=user)
            matched_any = False
          
            for asin in user_asins:
                asin_title_lower = asin.title.strip().lower()
              
                # Simple exact match check
                if asin_title_lower == product_name_lower:
                    # MatchedProducts mein save karein
                    MatchedProducts.objects.get_or_create(
                        user=user,
                        receipt_item=self,
                        asin_record=asin,
                        defaults={'matched_at': timezone.now()}
                    )
                  
                    # ASIN ka match_count +1 karein
                    asin.match_count += 1
                    asin.save()
                  
                    matched_any = True
                    print(f"✅ {self.product_name} matched with ASIN: {asin.asin}")
          
            # No matched_status anymore
              
        except Exception as e:
            print(f"❌ Error matching item {self.id}: {e}")
  
    def __str__(self):
        return f"Item #{self.line_number} - {self.product_name or 'Unknown'} - SKU: {self.sku or ''}"
class stickers(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ]
   
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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    year = models.IntegerField()
    month = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)
   
    def __str__(self):
        return f"Sticker #{self.id} - {self.original_filename}"
class sticker_data(models.Model):
    STATUS_CHOICES = [
        ('processed', 'Processed'),
        ('flagged', 'Flagged for review'),
    ]
   
    MATCHED_STATUS_CHOICES = [
        ('matched', 'Matched'),
        ('unmatched', 'Unmatched'),
    ]
   
    MATCHING_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('done', 'Done'),
    )
   
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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processed')
    year = models.IntegerField()
    month = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    matching_status = models.CharField(
        max_length=20,
        choices=MATCHING_STATUS_CHOICES,
        default='pending'
    )
    matched_status = models.CharField(max_length=20, choices=MATCHED_STATUS_CHOICES, default='unmatched')
   
    def save(self, *args, **kwargs):
        # Automatic status update only on creation
        is_new = self.pk is None
        if is_new:
            required_fields = [self.image_path, self.original_filename, self.file_size, self.barcode]
            if not all(field is not None and field != '' for field in required_fields):
                self.status = 'flagged'
            else:
                self.status = 'processed'
        super().save(*args, **kwargs)
   
    def __str__(self):
        return f"StickerData #{self.id} - {self.original_filename} - {self.barcode}"
   
   
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
        return f"Match #{self.id} - StickerData #{self.sticker_data.id} to ReceiptItem #{self.receipt_item.id}"
class ASINs(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='asins'
    )
    title = models.CharField(max_length=500)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    asin = models.CharField(max_length=20)
    created_at = models.DateTimeField(default=timezone.now)
    match_count = models.IntegerField(default=0) # ✅ Simple count field
    class Meta:
        unique_together = ('user', 'title', 'price', 'asin')
    def __str__(self):
        return f"{self.id} - {self.asin} - {self.title} - Count: {self.match_count}"
class MatchedProducts(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='matched_products'
    )
    receipt_item = models.ForeignKey(
        receipt_items,
        on_delete=models.CASCADE,
        related_name='asin_matches'
    )
    asin_record = models.ForeignKey(
        ASINs,
        on_delete=models.CASCADE,
        related_name='receipt_matches'
    )
    matched_at = models.DateTimeField(default=timezone.now)
   
    class Meta:
        unique_together = ('receipt_item', 'asin_record')
   
    def __str__(self):
        return f"Match #{self.id} - {self.receipt_item.product_name} → {self.asin_record.asin}"