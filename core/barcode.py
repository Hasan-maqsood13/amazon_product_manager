import pyzbar.pyzbar as pyzbar
from PIL import Image
import numpy as np
from django.utils import timezone
from Receipts.models import receipts # Agar Receipts app mein stickers model hai toh. Assuming Stickers.models is correct.
from Stickers.models import stickers, sticker_data # Corrected import
from decimal import Decimal

def extract_barcode_data(image_path):
    """Extract barcode data using pyzbar."""
    img = Image.open(image_path)
    # Convert to grayscale might help sometimes, but pyzbar works well with color too
    # img = img.convert('L') 
    img_np = np.array(img)
    
    barcodes = pyzbar.decode(img_np)
    
    extracted_codes = []
    for barcode in barcodes:
        code_data = barcode.data.decode("utf-8")
        code_type = barcode.type
        extracted_codes.append({
            'data': code_data,
            'type': code_type,
            # We don't get confidence score easily with pyzbar, keeping it simple for now.
        })
    return extracted_codes

def process_sticker(sticker_id):
    """Process a single sticker: barcode scan + save data."""
    try:
        # Fetch the sticker object using the correct model from Stickers app
        sticker = stickers.objects.get(id=sticker_id)
        sticker.status = 'processing'
        sticker.save()

        # Use the absolute path to the image file
        image_full_path = sticker.image_path.path
        extracted_codes = extract_barcode_data(image_full_path)

        if not extracted_codes:
            sticker.status = 'no_barcode_found'
            sticker.save()
            return

        # Assuming one main code per sticker for this task
        first_code = extracted_codes[0]['data'] 

        # Save to sticker_data table
        sticker_data.objects.create(
            sticker=sticker,
            extracted_sku=first_code,
            cleaned_sku=first_code, # Simple cleaning for now
            matching_status='pending',
            created_at=timezone.now(),
            processed_at=timezone.now()
        )

        sticker.status = 'done'
        sticker.save()

    except stickers.DoesNotExist:
        print(f"Sticker with ID {sticker_id} not found.")
    except Exception as e:
        if 'sticker' in locals():
            sticker.status = 'failed'
            sticker.save()
        print(f"Error processing sticker {sticker_id}: {e}")
        raise e