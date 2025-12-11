from pyzxing import BarCodeReader

def extract_barcode_zxing(image_path):
    """
    Extract barcode/FNSKU using ZXing (BEST FREE METHOD)
    """
    try:
        reader = BarCodeReader()
        result = reader.decode(image_path)

        if not result:
            return None
        
        # result is a list of dictionaries — return first detected code
        return result[0].get("raw", None)

    except Exception as e:
        print("ZXing Barcode Error:", e)
        return None
