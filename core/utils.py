import os
from datetime import datetime


def receipt_upload_path(instance, filename):
    today = datetime.now()
    path = f"upload/receipts/{today.strftime('%Y')}/{today.strftime('%m')}/{today.strftime('%d')}/"
    return os.path.join(path, filename)


def sticker_upload_path(instance, filename):
    today = datetime.now()
    path = f"upload/stickers/{today.strftime('%Y')}/{today.strftime('%m')}/{today.strftime('%d')}/"
    return os.path.join(path, filename)
