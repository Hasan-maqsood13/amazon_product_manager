import os
from django.core.exceptions import ValidationError
from PIL import Image

ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png']
MAX_FILE_SIZE_MB = 10


def validate_single_image(file):
    errors = []

    # Extension
    ext = os.path.splitext(file.name)[1].lower().replace(".", "")
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"{file.name}: Only JPG/PNG allowed.")

    # File size
    if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
        errors.append(f"{file.name}: File size exceeds 10MB limit.")

    # Corrupted check
    try:
        img = Image.open(file)
        img.verify()
    except:
        errors.append(f"{file.name}: Image file is corrupted or unreadable.")

    if errors:
        raise ValidationError(errors)


def validate_multiple_images(files):
    for file in files:
        validate_single_image(file)
