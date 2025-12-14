from .models import sticker_data, receipt_items, match_history
from django.utils import timezone

def perform_matching(user):
    pending_stickers = sticker_data.objects.filter(user=user, matching_status='pending', status='processed')
    for sticker in pending_stickers:
        if not sticker.barcode:
            continue  # Skip if no barcode
        matching_items = receipt_items.objects.filter(receipt__user=user, sku=sticker.barcode, status='done')
        matched = False
        for item in matching_items:
            matched_count = match_history.objects.filter(receipt_item=item).count()
            quantity = int(item.quantity) if item.quantity else 0
            if matched_count < quantity:
                match_history.objects.create(
                    sticker_data=sticker,
                    receipt_item=item,
                    SKU=sticker.barcode,
                    matched_at=timezone.now()
                )
                sticker.matching_status = 'done'  # Changed from 'matched' to 'done'
                sticker.save()
                matched = True
                break  # Move to next sticker after matching
        if not matched:
            # NEW: If no match found after checking all items, set to 'unmatched'
            sticker.matching_status = 'unmatched'
            sticker.save()