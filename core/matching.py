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


from django.db.models import Q
from difflib import SequenceMatcher


def match_receipt_items_with_asins(user):
    """
    Receipt items ko ASINs table se match karta hai
    """
    from .models import receipt_items, ASINs, MatchedProducts
    
    # Un receipt items ko lo jo abhi match nahi hue
    unmatched_items = receipt_items.objects.filter(
        receipt__user=user,
        status='done',  # Sirf successfully processed items
        asin_matches__isnull=True  # Jo pehle match nahi hue
    ).exclude(
        Q(product_name__isnull=True) | Q(product_name='') | Q(product_name='Unknown')
    )
    
    # User ke sarey ASINs lo
    user_asins = ASINs.objects.filter(user=user)
    
    matched_count = 0
    
    for item in unmatched_items:
        product_name = item.product_name.strip().lower()
        
        # Try 1: Exact Match (case-insensitive)
        exact_match = user_asins.filter(title__iexact=product_name).first()
        if exact_match:
            MatchedProducts.objects.get_or_create(
                user=user,
                receipt_item=item,
                asin_record=exact_match,
                defaults={'confidence': 'exact'}
            )
            matched_count += 1
            continue
        
        # Try 2: Partial Match (title mein product name ho)
        partial_matches = user_asins.filter(title__icontains=product_name)
        if partial_matches.exists():
            MatchedProducts.objects.get_or_create(
                user=user,
                receipt_item=item,
                asin_record=partial_matches.first(),
                defaults={'confidence': 'partial'}
            )
            matched_count += 1
            continue
        
        # Try 3: Fuzzy Match (similarity ratio > 80%)
        best_match = None
        best_ratio = 0.8  # 80% similarity threshold
        
        for asin in user_asins:
            ratio = SequenceMatcher(None, product_name, asin.title.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = asin
        
        if best_match:
            MatchedProducts.objects.get_or_create(
                user=user,
                receipt_item=item,
                asin_record=best_match,
                defaults={'confidence': 'fuzzy'}
            )
            matched_count += 1
    
    return matched_count