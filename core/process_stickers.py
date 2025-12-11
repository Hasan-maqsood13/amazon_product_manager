from pyzbar.pyzbar import decode
from PIL import Image
from .models import stickers, sticker_data  # Import your models

def scan_barcode(image_path):
    # Same function as above in Step 1
    try:
        img = Image.open(image_path)
        decoded_objects = decode(img)
        if decoded_objects:
            return decoded_objects[0].data.decode('utf-8')
        return None
    except Exception as e:
        print(f"Error scanning: {e}")
        return None

def process_stickers(sticker_id):
    """
    Processes a pending sticker: Scans barcode and saves to sticker_data.
    """
    try:
        sticker = stickers.objects.get(id=sticker_id)
        if sticker.status != 'pending':
            return  # Skip if not pending

        barcode = scan_barcode(sticker.image_path.path)  # Full path to image

        if barcode:
            # Save to sticker_data
            sticker_data.objects.create(
                user=sticker.user,
                image_path=sticker.image_path.name,  # Relative path as CharField
                original_filename=sticker.original_filename,
                file_size=sticker.file_size,
                upload_date=sticker.upload_date,
                status='processed',
                year=sticker.year,
                month=sticker.month,
                barcode=barcode  # The extracted code
            )
            sticker.status = 'processed'
        else:
            sticker.status = 'failed'  # No barcode found

        sticker.save()
    except Exception as e:
        print(f"Error processing sticker {sticker_id}: {e}")
        stickers.objects.filter(id=sticker_id).update(status='failed')