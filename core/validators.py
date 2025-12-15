# validators.py
from django.core.exceptions import ValidationError
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import io
import numpy as np
import cv2
from skimage import filters
import tempfile
import os
# Allowed file types
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf'}
MAX_SIZE_MB = 10
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024
# New soft threshold
MIN_BLUR_THRESHOLD = 5.0 # <5 = image is extremely bad / unreadable
def get_blur_score(image_array):
    """Calculate blur score using Laplacian variance."""
    if len(image_array.shape) == 3:
        gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_array
    return cv2.Laplacian(gray, cv2.CV_64F).var()
def validate_image_file(file):
    errors = []
    # -------------------------------
    # 1. File size check
    # -------------------------------
    if file.size > MAX_SIZE_BYTES:
        errors.append(f"{file.name}: File size must be under {MAX_SIZE_MB}MB.")
    # -------------------------------
    # 2. Extension check
    # -------------------------------
    ext = file.name.split('.')[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"{file.name}: Only JPG, JPEG, PNG and PDF allowed.")
    if ext == 'pdf':
        # Bas size check karein, image checks nahi
        if errors:
            raise ValidationError(errors)
        return
    # -------------------------------
    # 3. Corrupted image check
    # -------------------------------
    try:
        file.seek(0)
        img = Image.open(file)
        img.verify() # corruption test
    except Exception:
        errors.append(f"{file.name}: Corrupted or invalid image file.")
        raise ValidationError(errors)
    # Reset pointer after verify()
    file.seek(0)
    # -------------------------------------
    # 4. Blur check (SOFT VALIDATION MODE)
    # -------------------------------------
    try:
        img = Image.open(file).convert("RGB")
        img_np = np.array(img)
        blur_score = get_blur_score(img_np)
        # Debug
        print(f"{file.name} → Blur Score = {blur_score:.2f}")
        # Only reject extremely unreadable images
        if blur_score < MIN_BLUR_THRESHOLD:
            errors.append(f"{file.name}: Image is extremely blurred/unreadable.")
    except Exception:
        # If blur check fails → do NOT reject the image
        pass
    # -------------------------------
    # Final decision
    # -------------------------------
    if errors:
        raise ValidationError(errors)
def validate_multiple_images(files):
    valid_files = []
    rejected_files = []
    for file in files:
        try:
            validate_image_file(file)
            valid_files.append(file)
        except ValidationError as e:
            rejected_files.append({
                'file': file.name,
                'errors': e.messages
            })
    return valid_files, rejected_files
def validate_sticker_image(file):
    errors = []
    ext = file.name.split('.')[-1].lower()
    if ext not in {'jpg', 'jpeg', 'png'}:
        errors.append(f"{file.name}: Only JPG, JPEG, or PNG allowed.")
  
    if errors:
        raise ValidationError(errors)
def validate_multiple_stickers(files):
    valid_files = []
    rejected_files = []
    for file in files:
        try:
            validate_sticker_image(file)
            valid_files.append(file)
        except ValidationError as e:
            rejected_files.append({
                'file': file.name,
                'errors': e.messages
            })
    return valid_files, rejected_files