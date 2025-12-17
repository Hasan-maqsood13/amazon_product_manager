import os
from PIL import Image
import numpy as np
from openai import OpenAI
from decimal import Decimal
from django.utils import timezone
from .models import *
from dotenv import load_dotenv
import easyocr
import pytesseract
import io
from pdf2image import convert_from_bytes  # New import for PDF handling

load_dotenv()
# OpenAI Client
client = OpenAI(api_key=os.getenv('api_key'))
# EasyOCR Reader (backup ke liye)
easy_reader = easyocr.Reader(['en'], gpu=False)

def ocr_on_image(pil_image):
    """Helper function to perform OCR on a PIL Image."""
    img_array = np.array(pil_image)
    
    # Try EasyOCR
    easy_result = easy_reader.readtext(img_array, detail=1, paragraph=False)
    easy_lines = [det[1] for det in easy_result]
    easy_confidences = [det[2] for det in easy_result]
    easy_raw_text = "\n".join(easy_lines)
    easy_avg_conf = sum(easy_confidences) / len(easy_confidences) * 100 if easy_confidences else 0
    
    # If low confidence, try Tesseract
    if easy_avg_conf < 70:
        tess_config = r'--oem 3 --psm 6'
        tess_raw_text = pytesseract.image_to_string(pil_image, config=tess_config)
        if len(tess_raw_text) > len(easy_raw_text):
            return tess_raw_text, 80.0
        else:
            return easy_raw_text, easy_avg_conf
    else:
        return easy_raw_text, easy_avg_conf

def extract_text_from_image(file_content):
    """Local OCR for image files using bytes."""
    try:
        img = Image.open(io.BytesIO(file_content)).convert('RGB')
        raw_text, avg_conf = ocr_on_image(img)
        return raw_text, avg_conf
    except Exception as e:
        print(f"Image OCR error: {e}")
        return "", 0.0

def extract_text_from_pdf(file_content):
    """Local OCR for PDF: Convert to images and OCR each page."""
    try:
        pages = convert_from_bytes(file_content, dpi=300, poppler_path=r'C:\poppler\Library\bin')  # Apna path daalo, jaise jahan bin folder hai  # High DPI for better accuracy
        raw_texts = []
        conf_scores = []
        for page_num, page in enumerate(pages, start=1):
            page_text, page_conf = ocr_on_image(page)
            raw_texts.append(f"--- Page {page_num} ---\n{page_text}")
            conf_scores.append(page_conf)
        
        raw_text = "\n\n".join(raw_texts)
        avg_conf = sum(conf_scores) / len(conf_scores) if conf_scores else 0.0
        return raw_text, avg_conf
    except Exception as e:
        print(f"PDF OCR error: {e}")
        return "", 0.0

def extract_text_with_ocr(receipt_instance):
    """
    Updated: Use local OCR for both images and PDFs.
    """
    try:
        file_path = receipt_instance.image_path.path
        file_ext = os.path.splitext(file_path)[1].lower()
      
        # Debugging ke liye
        print(f"Processing file: {file_path}, Type: {file_ext}")
      
        with open(file_path, 'rb') as f:
            file_content = f.read()
      
        if file_ext == '.pdf':
            print("Using local OCR for PDF extraction...")
            raw_text, avg_conf = extract_text_from_pdf(file_content)
          
        elif file_ext in ['.jpg', '.jpeg', '.png']:
            print("Using local OCR for image extraction...")
            raw_text, avg_conf = extract_text_from_image(file_content)
          
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")
      
        return raw_text, avg_conf
      
    except Exception as e:
        print(f"Error in extract_text_with_ocr: {e}")
        # Agar kuch bhi fail ho jaye to empty text return karein
        return "", 0.0
def parse_with_ai(raw_text):
    """AI parsing function - Yeh bilkul waisi hi rahegi"""
    prompt = f"""
You are an advanced, error-tolerant receipt-analysis AI trained to extract every purchased item with maximum accuracy from imperfect OCR text.
You MUST follow all rules below:
====================================================
                GLOBAL OBJECTIVE
====================================================
Given the raw OCR receipt text, extract EVERY purchased line item with PERFECT accuracy for:
- Item Name
- Quantity
- Unit Price
- Total Price
- Item Code (SKU/UPC/PLU/Lookup code)
Your extraction must:
✔ Correct OCR mistakes
✔ Join broken words
✔ Detect numeric patterns even when spacing is distorted
✔ Handle ANY receipt format (Walmart, Target, Costco, small shops, international receipts, thermal receipts, faded receipts)
✔ Not hallucinate or invent ANY data
✔ Re-check the entire OCR text multiple times to recover missing codes or numbers
✔ Validate math consistency (qty × unit = total)
✔ Recalculate missing fields when possible
====================================================
            EXTRACTION INSTRUCTIONS
====================================================
1. **Identify Item Lines ONLY**
   An item line is ANY line that:
   - has a name + price
   - or name + code
   - or code + price
   - or name only followed by a price on the next line
   - or appears in a grouped format where description and numeric values are separated.
   Ignore:
   - tax lines, subtotal lines, total, payment method, change due
   - store headers, addresses, ads
   - coupons unless they explicitly reference a specific purchased item
2. **Item Name Reconstruction**
   - Fix OCR mistakes ("M1LK" → "MILK", "C0KE" → "COKE")
   - Join broken names split across lines
   - Remove extra symbols, timestamps, clerk IDs
   - Preserve clarity without inventing words
3. **Price Extraction Rules**
   Accept price patterns such as:
   - `$3.49`
   - `3.49`
   - `3,49` (European)
   - `3 49`
   - `3.49F` (OCR noise → convert to 3.49)
   If unit price missing but total present + quantity present → compute unit.
   If total missing but unit + qty present → compute total.
4. **Quantity Extraction Rules**
   Use these patterns (OCR is very messy):
   - "QTY 2", "Qty2", "2 @", "x2", "2X", "2 EA", "*2", "2pk", "2-pack"
   - If nothing found, default to 1.
5. **SKU/UPC/CODE Extraction Rules**
   Look for:
   - 6 to 14 digit numbers
   - alphanumeric product codes
   - codes BEFORE or AFTER item name
   - codes in parentheses or at end of line
   - barcodes split across lines (e.g., "1234" + "567890") → merge if clearly adjacent
   After extracting codes:
   → Re-scan the ENTIRE raw text again to ensure no code was missed.
6. **Self-Consistency Validation**
   For each item:
   - Verify math: qty × unit ≈ total
   - If mismatch but one field is clearly OCR-broken, fix it
   - Never guess; only fix using verifiable numeric patterns
7. **STRICT OUTPUT FORMAT**
   Output EXACTLY using this structure for every item block:
   - Item Name: <clean exact name, corrected but not invented>
     Quantity: <number>
     Unit Price: $<price> OR Not found
     Total Price: $<price> OR Not found
     Code: <code if found, else Not found>
NO commentary.
NO explanation.
NO extra text.
ONLY item blocks exactly in the above format.
====================================================
               RAW OCR RECEIPT TEXT
====================================================
{raw_text}
====================================================
Begin extraction now.
====================================================
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return ""
    
def process_receipt(receipt_id):
    """Process receipt with new OCR system"""
    receipt = receipts.objects.get(id=receipt_id)
    receipt.status = 'processing'
    receipt.save()
 
    try:
        raw_text, avg_conf = extract_text_with_ocr(receipt)
      
        receipt.raw_ocr_text = raw_text
        receipt.save()
     
        if not raw_text or len(raw_text.strip()) < 10:
            receipt.status = 'failed'
            receipt.raw_ocr_text = "ERROR: No text extracted from file"
            receipt.save()
            return
      
        parsed = parse_with_ai(raw_text)
      
        if not parsed:
            receipt.status = 'failed'
            receipt.raw_ocr_text += "\nERROR: AI parsing failed"
            receipt.save()
            return
      
        lines = [line.strip() for line in parsed.split('\n') if line.strip()]
     
        seen_skus = set()
        i = 0
        line_num = 1
        items_created = 0
      
        while i < len(lines):
            if lines[i].startswith('- Item Name:'):
                name = lines[i].replace('- Item Name:', '').strip()
             
                qty_line = lines[i+1] if i+1 < len(lines) and lines[i+1].startswith('Quantity:') else 'Quantity: 1'
                qty_str = qty_line.replace('Quantity:', '').strip()
             
                unit_line = lines[i+2] if i+2 < len(lines) and lines[i+2].startswith('Unit Price:') else 'Unit Price: Not found'
                unit_str = unit_line.replace('Unit Price:', '').replace('$', '').strip()
             
                total_line = lines[i+3] if i+3 < len(lines) and lines[i+3].startswith('Total Price:') else 'Total Price: Not found'
                total_str = total_line.replace('Total Price:', '').replace('$', '').strip()
             
                code_line = lines[i+4] if i+4 < len(lines) and lines[i+4].startswith('Code:') else 'Code: Not found'
                code = code_line.replace('Code:', '').strip()
             
                if code != 'Not found' and code in seen_skus:
                    code = 'Duplicate - ' + code
             
                seen_skus.add(code)
             
                qty_val = Decimal(qty_str) if qty_str.replace('.', '', 1).isdigit() else None
                unit_val = Decimal(unit_str) if unit_str != 'Not found' and unit_str.replace('.', '', 1).isdigit() else None
                total_val = Decimal(total_str) if total_str != 'Not found' and total_str.replace('.', '', 1).isdigit() else None
             
                # ✅ DIRECT receipt item create karein
                item = receipt_items(
                    receipt=receipt,
                    line_number=line_num,
                    product_name=name if name else 'Unknown',
                    sku=code if code != 'Not found' else None,
                    quantity=qty_val,
                    unit_price=unit_val,
                    total_price=total_val,
                    raw_text='\n'.join(lines[i:i+5]),
                    confidence_score=Decimal(avg_conf),
                    created_at=timezone.now()
                )
                
                # Save karein - ye automatically match_with_asins() call karega
                item.save()
              
                line_num += 1
                items_created += 1
                i += 5
            else:
                i += 1
      
        if items_created > 0:
            receipt.status = 'done'
            print(f"✅ {items_created} items created and automatically matched with ASINs")
        else:
            receipt.status = 'failed'
            receipt.raw_ocr_text += "\nERROR: No items extracted"
      
        receipt.save()
        print(f"Receipt {receipt_id} processed: {items_created} items created")
 
    except Exception as e:
        print(f"Error processing receipt {receipt_id}: {e}")
        receipt.status = 'failed'
        receipt.raw_ocr_text += f'\nError: {str(e)}'
        receipt.save()
        raise e