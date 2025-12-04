from PIL import Image, ImageEnhance, ImageFilter, ExifTags
import io


def preprocess_image(file):
    img = Image.open(file)

    # 1) Auto Rotate using EXIF
    try:
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == "Orientation":
                break
        exif = img._getexif()
        if exif is not None:
            orientation_value = exif.get(orientation)
            if orientation_value == 3:
                img = img.rotate(180, expand=True)
            elif orientation_value == 6:
                img = img.rotate(270, expand=True)
            elif orientation_value == 8:
                img = img.rotate(90, expand=True)
    except:
        pass

    # 2) Denoise (simple, safe filter)
    img = img.filter(ImageFilter.MedianFilter(size=3))

    # 3) Sharpness
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(1.7)

    # 4) Contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.3)

    # Convert back to in-memory file
    processed_io = io.BytesIO()
    img.save(processed_io, format="JPEG", quality=92)
    processed_io.seek(0)

    return processed_io
