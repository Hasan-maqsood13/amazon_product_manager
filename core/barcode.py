# core/barcode.py  (naya file bana do)
from pyzbar.pyzbar import decode
from PIL import Image
import cv2
import numpy as np
from django.core.files.base import ContentFile
from io import BytesIO

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
    from .models import stickers, sticker_data
    import os

    try:
        sticker = stickers.objects.get(id=sticker_id)
        if sticker.status != 'pending':
            return

        barcode = scan_barcode_robust(sticker.image_path.path)

        if barcode and len(barcode.strip()) > 3:
            # Save to sticker_data
            sticker_data.objects.create(
                user=sticker.user,
                image_path=sticker.image_path.name,
                original_filename=sticker.original_filename,
                file_size=sticker.file_size,
                barcode=barcode.strip(),
                status='processed',    
                matching_status='pending',
                year=sticker.year,
                month=sticker.month,
            )
            sticker.status = 'processed'
            sticker.save()
            return {"file": sticker.original_filename, "barcode": barcode, "status": "success"}
        else:
            sticker.status = 'failed'
            sticker.save()
            return {"file": sticker.original_filename, "status": "failed", "reason": "No barcode found"}

    except Exception as e:
        print(f"Error processing sticker {sticker_id}: {e}")
        stickers.objects.filter(id=sticker_id).update(status='failed')
        return {"file": "Unknown", "status": "failed", "reason": str(e)}