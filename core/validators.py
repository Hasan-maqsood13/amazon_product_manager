# validators.py
from django.core.exceptions import ValidationError
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import io
import numpy as np
import cv2
from skimage import filters
import tempfile
import os

# PDF ko remove kar diya hai
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'} 
MAX_SIZE_MB = 10
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024

# Minimum quality thresholds
MIN_BLUR_THRESHOLD = 50.0  # Laplacian variance - higher is clearer
MIN_BRIGHTNESS = 40        # 0-255 scale
MIN_CONTRAST = 1.5         # Contrast ratio
MAX_NOISE_THRESHOLD = 25   # Lower is less noisy
MIN_EDGE_DENSITY = 0.01    # Edge density for text detection

def calculate_blur_score(image_array):
    """
    Calculate blur score using Laplacian variance.
    Higher score = less blurry
    """
    if len(image_array.shape) == 3:
        gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_array
    
    # Calculate Laplacian variance
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    return laplacian_var

def calculate_brightness(image_array):
    """Calculate average brightness of image"""
    if len(image_array.shape) == 3:
        gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_array
    return np.mean(gray)

def calculate_contrast(image_array):
    """Calculate contrast of image"""
    if len(image_array.shape) == 3:
        gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_array
    
    # Contrast as standard deviation
    contrast = np.std(gray)
    return contrast / 50.0  # Normalize

def calculate_noise_level(image_array):
    """Estimate noise level in image"""
    if len(image_array.shape) == 3:
        gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_array
    
    # Use median absolute deviation as noise estimator
    median = np.median(gray)
    mad = np.median(np.abs(gray - median))
    return mad

def calculate_edge_density(image_array):
    """Calculate edge density (good for text detection)"""
    if len(image_array.shape) == 3:
        gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_array
    
    # Apply Canny edge detection
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.sum(edges > 0) / (gray.shape[0] * gray.shape[1])
    return edge_density

def assess_image_quality(file):
    """
    Comprehensive image quality assessment
    Returns: (is_acceptable, reason)
    """
    try:
        # Convert file to numpy array
        file.seek(0)
        img = Image.open(file)
        
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Save to temp file for OpenCV
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            img.save(tmp.name, 'JPEG', quality=90)
            tmp_path = tmp.name
        
        # Read with OpenCV
        image_array = cv2.imread(tmp_path)
        
        if image_array is None:
            os.unlink(tmp_path)
            return False, "Could not read image"
        
        # Calculate quality metrics
        blur_score = calculate_blur_score(image_array)
        brightness = calculate_brightness(image_array)
        contrast = calculate_contrast(image_array)
        noise_level = calculate_noise_level(image_array)
        edge_density = calculate_edge_density(image_array)
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        # Debug prints (remove in production)
        print(f"Quality Check - {file.name}:")
        print(f"  Blur Score: {blur_score:.2f} (min {MIN_BLUR_THRESHOLD})")
        print(f"  Brightness: {brightness:.2f} (min {MIN_BRIGHTNESS})")
        print(f"  Contrast: {contrast:.2f} (min {MIN_CONTRAST})")
        print(f"  Noise Level: {noise_level:.2f} (max {MAX_NOISE_THRESHOLD})")
        print(f"  Edge Density: {edge_density:.4f} (min {MIN_EDGE_DENSITY})")
        
        # Check thresholds
        reasons = []
        
        if blur_score < MIN_BLUR_THRESHOLD:
            reasons.append(f"Image is too blurry (score: {blur_score:.1f})")
        
        if brightness < MIN_BRIGHTNESS:
            reasons.append(f"Image is too dark (brightness: {brightness:.1f})")
        
        if contrast < MIN_CONTRAST:
            reasons.append(f"Image lacks contrast (contrast: {contrast:.1f})")
        
        if noise_level > MAX_NOISE_THRESHOLD:
            reasons.append(f"Image has too much noise (noise: {noise_level:.1f})")
        
        if edge_density < MIN_EDGE_DENSITY and blur_score < MIN_BLUR_THRESHOLD * 1.5:
            reasons.append("Image lacks clear edges/text")
        
        if reasons:
            return False, "; ".join(reasons)
        
        return True, "Image quality is acceptable"
        
    except Exception as e:
        print(f"Error in quality assessment for {file.name}: {str(e)}")
        return False, f"Quality check failed: {str(e)}"

def validate_image_file(file):
    errors = []
    
    # 1. File size
    if file.size > MAX_SIZE_BYTES:
        errors.append(f"{file.name}: File size must be under {MAX_SIZE_MB}MB")

    # 2. Extension
    ext = file.name.split('.')[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"{file.name}: Only JPG, JPEG, and PNG images are allowed.")

    # 3. Corrupted image check
    if ext in ['jpg', 'jpeg', 'png']:
        try:
            file.seek(0)
            img = Image.open(file)
            img.verify()
            file.seek(0)  # Reset pointer
            
            # 4. NEW: Image Quality Assessment
            file.seek(0)
            is_acceptable, reason = assess_image_quality(file)
            file.seek(0)  # Reset again
            
            if not is_acceptable:
                errors.append(f"{file.name}: Poor image quality - {reason}")
                
        except Exception:
            errors.append(f"{file.name}: Corrupted or invalid image file")

    if errors:
        raise ValidationError(errors)

def validate_multiple_images(files):
    """Validate multiple images and return only valid ones"""
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