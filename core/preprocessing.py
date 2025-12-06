# preprocessing.py
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import io
from django.core.files.uploadedfile import InMemoryUploadedFile

def enhance_for_ocr(image_array):
    """Enhance image specifically for OCR readability"""
    if len(image_array.shape) == 3:
        gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_array
    
    # Apply CLAHE for contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    # Denoise
    denoised = cv2.fastNlMeansDenoising(enhanced, h=10)
    
    # Sharpen
    kernel = np.array([[-1,-1,-1],
                       [-1, 9,-1],
                       [-1,-1,-1]])
    sharpened = cv2.filter2D(denoised, -1, kernel)
    
    return sharpened

def preprocess_image_pro(file):
    """
    Advanced preprocessing with quality feedback
    """
    try:
        # Read image
        file.seek(0)
        img = Image.open(file)
        
        # Auto-rotate using EXIF
        img = ImageOps.exif_transpose(img)
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Convert to numpy array for OpenCV processing
        img_array = np.array(img)
        
        # Apply advanced enhancements
        enhanced_array = enhance_for_ocr(img_array)
        
        # Convert back to PIL Image
        result_img = Image.fromarray(enhanced_array)
        
        # Save to BytesIO
        output = io.BytesIO()
        result_img.save(output, format='JPEG', quality=95, optimize=True)
        output.seek(0)
        
        return InMemoryUploadedFile(
            output,
            'ImageField',
            file.name,
            'image/jpeg',
            output.getbuffer().nbytes,
            None
        )
        
    except Exception as e:
        print(f"Preprocessing error: {e}")
        # Return original file if preprocessing fails
        file.seek(0)
        return file