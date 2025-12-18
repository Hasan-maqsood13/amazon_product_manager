from pyzbar.pyzbar import decode
from PIL import Image
import cv2
import numpy as np
from django.utils import timezone
import os
def scan_barcode_robust(image_path):
    """
    Sabse powerful barcode scanner jo real-world FNSKU images pe kaam karta hai
    """
    try:
        # Open with PIL
        img = Image.open(image_path)
        img = img.convert('RGB')
        # Convert to numpy array
        img_array = np.array(img)
        # Method 1: Direct pyzbar
        decoded = decode(img_array)
        if decoded:
            return decoded[0].data.decode('utf-8')
        # Method 2: Grayscale + Thresholding
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        for thresh in [cv2.THRESH_BINARY, cv2.THRESH_BINARY + cv2.THRESH_OTSU]:
            _, binary = cv2.threshold(gray, 0, 255, thresh)
            decoded = decode(binary)
            if decoded:
                return decoded[0].data.decode('utf-8')
        # Method 3: Invert (black barcode on white)
        inverted = cv2.bitwise_not(gray)
        decoded = decode(inverted)
        if decoded:
            return decoded[0].data.decode('utf-8')
        # Method 4: Resize up (small images ke liye)
        large = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        decoded = decode(large)
        if decoded:
            return decoded[0].data.decode('utf-8')
        # Method 5: Denoise + Sharpen
        denoised = cv2.fastNlMeansDenoising(gray)
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(denoised, -1, kernel)
        decoded = decode(sharpened)
        if decoded:
            return decoded[0].data.decode('utf-8')
        return None
    except Exception as e:
        print(f"Barcode scan error: {e}")
        return None
def process_sticker(sticker_id):
    from core.models import stickers, sticker_data
    try:
        sticker = stickers.objects.get(id=sticker_id)
        print(f"Processing sticker {sticker_id}: {sticker.original_filename}")
       
        # Pehle check karein ke ye sticker pehle process to nahi ho chuka
        existing_sticker_data = sticker_data.objects.filter(
            user=sticker.user,
            original_filename=sticker.original_filename,
            file_size=sticker.file_size
        ).first()
       
        if existing_sticker_data:
            print(f"⚠️ Sticker {sticker_id} already processed before. Skipping...")
            return {
                "file": sticker.original_filename,
                "status": "skipped",
                "reason": "Already processed"
            }
        # Status update karein
        sticker.status = 'processing'
        sticker.save()
        barcode = scan_barcode_robust(sticker.image_path.path)
        if barcode and len(barcode.strip()) > 6:
            barcode = barcode.strip()
            print(f"Raw barcode detected: {barcode}")
            cleaned_barcode = barcode[:-6]
            print(f"Cleaned barcode: {cleaned_barcode}")
            # Sirf EK BAR sticker_data create karein
            sticker_data_obj = sticker_data.objects.create(
                user=sticker.user,
                image_path=sticker.image_path.name,
                original_filename=sticker.original_filename,
                file_size=sticker.file_size,
                barcode=cleaned_barcode,
                status='processed',
                year=sticker.year,
                month=sticker.month,
                upload_date=timezone.now(),
                created_at=timezone.now(),
                matching_status='pending',
                matched_status='unmatched'
            )
            sticker.status = 'done'
            sticker.save()
            print(f"✅ Sticker {sticker_id} processed successfully. Barcode: {cleaned_barcode}")
           
            # Automatic matching run karein
            try:
                from core.matching import perform_sticker_receipt_matching
                matches = perform_sticker_receipt_matching(sticker.user)
                print(f"✅ {matches} sticker-receipt matches created")
            except Exception as e:
                print(f"⚠️ Sticker matching error: {e}")
            return {
                "file": sticker.original_filename,
                "barcode": cleaned_barcode,
                "status": "success",
                "sticker_data_id": sticker_data_obj.id
            }
        else:
            # Barcode nahi mila, sirf EK BAR sticker_data create karein
            sticker_data_obj = sticker_data.objects.create(
                user=sticker.user,
                image_path=sticker.image_path.name,
                original_filename=sticker.original_filename,
                file_size=sticker.file_size,
                barcode=None,
                status='failed',
                year=sticker.year,
                month=sticker.month,
                upload_date=timezone.now(),
                created_at=timezone.now(),
                matching_status='unmatched',
                matched_status='unmatched'
            )
            sticker.status = 'failed'
            sticker.save()
            print(f"⚠️ Sticker {sticker_id} processed but no barcode found")
           
            return {
                "file": sticker.original_filename,
                "status": "failed",
                "reason": "No barcode found",
                "sticker_data_id": sticker_data_obj.id
            }
    except Exception as e:
        print(f"❌ Error processing sticker {sticker_id}: {e}")
       
        # Exception case mein bhi sirf EK BAR save karein
        try:
            # Check karein ke sticker object hai ya nahi
            if 'sticker' in locals():
                sticker_data_obj = sticker_data.objects.create(
                    user=sticker.user,
                    image_path=sticker.image_path.name,
                    original_filename=sticker.original_filename,
                    file_size=sticker.file_size,
                    barcode=None,
                    status='failed',
                    year=sticker.year,
                    month=sticker.month,
                    upload_date=timezone.now(),
                    created_at=timezone.now(),
                    matching_status='unmatched',
                    matched_status='unmatched'
                )
               
                sticker.status = 'failed'
                sticker.save()
            else:
                print(f"❌ Sticker object not found in exception")
               
        except Exception as inner_e:
            print(f"❌ Error creating sticker_data in exception: {inner_e}")
       
        return {
            "file": sticker.original_filename if 'sticker' in locals() else "Unknown",
            "status": "failed",
            "reason": str(e)
        }