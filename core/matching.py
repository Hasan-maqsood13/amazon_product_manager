# matching.py
from .models import sticker_data, receipt_items, match_history, ASINs, MatchedProducts
from django.utils import timezone
from django.db.models import Q
from difflib import SequenceMatcher

def perform_complete_matching(user):
    """
    Complete matching algorithm jo saari possible matches create karega
    """
    # TASK 1: Sticker Data → Receipt Items Matching
    sticker_matches = perform_sticker_receipt_matching(user)
   
    # TASK 2: ASIN Titles → Receipt Items Matching aur MatchedProducts mein save
    asin_matches = perform_asin_receipt_matching_with_save(user)
   
    print(f"✅ Complete matching completed for user: {user.username}")
    print(f"📊 Results: {sticker_matches} sticker matches, {asin_matches['products_created']} ASIN matches")
   
    return {
        'sticker_matches': sticker_matches,
        'asin_matches': asin_matches
    }

def perform_sticker_receipt_matching(user):
    """
    Sticker data ko receipt items ke sath match karega - NO DUPLICATES
    """
    # Sirf pending stickers ko lo
    pending_stickers = sticker_data.objects.filter(
        user=user,
        matching_status='pending'
    )
   
    total_matches_created = 0
   
    for sticker in pending_stickers:
        if not sticker.barcode or sticker.barcode.strip() == '':
            # Agar barcode nahi hai
            sticker.matching_status = 'done'
            sticker.matched_status = 'unmatched'
            sticker.save()
            continue
       
        # Sabhi receipt items lo jo same SKU rakhte hain
        matching_items = receipt_items.objects.filter(
            receipt__user=user,
            sku=sticker.barcode.strip(),
            status='processed'
        )
       
        matches_created_for_this_sticker = 0
       
        for item in matching_items:
            # IMPORTANT: Check if already matched with ANY sticker (not just this one)
            already_matched = match_history.objects.filter(
                receipt_item=item
            ).exists()
           
            # Also check if THIS sticker already matched with THIS item
            this_match_exists = match_history.objects.filter(
                sticker_data=sticker,
                receipt_item=item
            ).exists()
           
            if not already_matched and not this_match_exists:
                # Create match history record
                match_history.objects.create(
                    sticker_data=sticker,
                    receipt_item=item,
                    SKU=sticker.barcode,
                    matched_at=timezone.now()
                )
               
                # Update item matched_status
                item.matched_status = 'matched'
                item.save()
               
                matches_created_for_this_sticker += 1
                total_matches_created += 1
                print(f"✅ Sticker {sticker.barcode} → Item {item.product_name}")
       
        # Update sticker status
        sticker.matching_status = 'done'
        sticker.matched_status = 'matched' if matches_created_for_this_sticker > 0 else 'unmatched'
        sticker.save()
   
    print(f"📊 Sticker → Receipt Matching: {total_matches_created} new matches created")
    return total_matches_created

def perform_asin_receipt_matching_with_save(user):
    """
    ASIN titles ko receipt items ke product names se match karega - ONLY EXACT MATCH
    """
    # User ke sare ASINs lo
    user_asins = ASINs.objects.filter(user=user)
   
    # User ke sare receipt items lo
    user_receipt_items = receipt_items.objects.filter(
        receipt__user=user,
        status='processed'
    ).exclude(
        Q(product_name__isnull=True) | Q(product_name='') | Q(product_name='Unknown')
    )
   
    total_matches_found = 0
    matched_products_created = 0
   
    for asin in user_asins:
        asin_title = asin.title.strip().lower()
        match_count = 0
       
        for item in user_receipt_items:
            product_name = item.product_name.strip().lower()
           
            if is_match_found(asin_title, product_name):
                match_count += 1
                total_matches_found += 1
               
                # Check if already matched
                existing_match = MatchedProducts.objects.filter(
                    user=user,
                    receipt_item=item,
                    asin_record=asin
                ).exists()
               
                if not existing_match:
                    # Create MatchedProducts record
                    MatchedProducts.objects.create(
                        user=user,
                        receipt_item=item,
                        asin_record=asin,
                        confidence=determine_confidence_level(asin_title, product_name),
                        matched_at=timezone.now()
                    )
                    matched_products_created += 1
                    print(f"✅ ASIN {asin.asin} → Item {item.product_name}")
       
        # Update ASIN match count
        asin.match_count = match_count
        asin.save()
   
    print(f"📊 ASIN → Receipt Matching: {total_matches_found} matches found")
    print(f"📦 MatchedProducts created: {matched_products_created} new records")
   
    return {
        'matches_found': total_matches_found,
        'products_created': matched_products_created
    }

def determine_confidence_level(asin_title, product_name):
    """
    Match ki confidence level determine karega - Ab sirf exact hi possible hai
    """
    return 'exact'

def is_match_found(asin_title, product_name):
    """
    ONLY EXACT match checking (case-insensitive, stripped)
    """
    # Remove extra spaces and convert to lowercase
    asin_title = asin_title.strip().lower()
    product_name = product_name.strip().lower()
   
    # Sirf exact equality
    if asin_title == product_name:
        return True
   
    return False

# For backward compatibility
def perform_matching(user):
    """
    Legacy function
    """
    return perform_sticker_receipt_matching(user)

def match_receipt_with_asins(receipt_item):
    """
    Ek receipt item ko ASINs ke sath match karega - ONLY EXACT MATCH
    """
    try:
        if not receipt_item.product_name or receipt_item.product_name == 'Unknown':
            return 0
       
        user = receipt_item.receipt.user
        user_asins = ASINs.objects.filter(user=user)
       
        product_name_lower = receipt_item.product_name.strip().lower()
        matches_found = 0
       
        for asin in user_asins:
            asin_title_lower = asin.title.strip().lower()
           
            # ONLY exact match
            if asin_title_lower == product_name_lower:
               
                # Check if already matched
                existing = MatchedProducts.objects.filter(
                    user=user,
                    receipt_item=receipt_item,
                    asin_record=asin
                ).exists()
               
                if not existing:
                    MatchedProducts.objects.create(
                        user=user,
                        receipt_item=receipt_item,
                        asin_record=asin,
                        confidence='exact',
                        matched_at=timezone.now()
                    )
                   
                    # Update ASIN count
                    asin.match_count += 1
                    asin.save()
                   
                    matches_found += 1
                    print(f"✅ {receipt_item.product_name} → {asin.asin}")
       
        return matches_found
       
    except Exception as e:
        print(f"❌ Error matching receipt item: {e}")
        return 0

def match_sticker_with_receipt(user):
    """
    Simple sticker-receipt matching (for barcode.py)
    """
    return perform_sticker_receipt_matching(user)