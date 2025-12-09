import easyocr
import pytesseract
from PIL import Image
import numpy as np
from openai import OpenAI
from decimal import Decimal
from django.utils import timezone
from .models import *
import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI Client
client = OpenAI(api_key=os.getenv('api_key'))

# EasyOCR Reader
easy_reader = easyocr.Reader(['en'], gpu=False)  # gpu=True if available

def extract_text_with_ocr(image_path):
    """Extract text using EasyOCR first, fallback to Tesseract for better accuracy on complex receipts."""
    pil_image = Image.open(image_path).convert('RGB')
    img_array = np.array(pil_image)
    
    # Try EasyOCR
    easy_result = easy_reader.readtext(img_array, detail=1, paragraph=False)
    easy_lines = [det[1] for det in easy_result]
    easy_confidences = [det[2] for det in easy_result]
    easy_raw_text = "\n".join(easy_lines)
    easy_avg_conf = sum(easy_confidences) / len(easy_confidences) * 100 if easy_confidences else 0
    
    # If low confidence, try Tesseract as fallback
    if easy_avg_conf < 70:  # Threshold for fallback
        tess_config = r'--oem 3 --psm 6'  # PSM 6 for block of text
        tess_raw_text = pytesseract.image_to_string(pil_image, config=tess_config)
        tess_lines = tess_raw_text.split('\n')
        # Simple confidence estimation for Tesseract (not native, approximate)
        tess_avg_conf = 80 if len(tess_lines) > len(easy_lines) else easy_avg_conf  # Heuristic
        
        # Choose better one based on line count/content length
        if len(tess_raw_text) > len(easy_raw_text):
            return tess_raw_text, tess_avg_conf
        else:
            return easy_raw_text, easy_avg_conf
    else:
        return easy_raw_text, easy_avg_conf

def parse_with_ai(raw_text):
    """Improved AI parsing: Strict item extraction, handle duplicates, different formats."""
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
   - Fix OCR mistakes ("M1LK" → "MILK", “C0KE” → “COKE”)  
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
   - "QTY 2", "Qty2", "2 @", "x2", "2X", "2 EA", "*2", "2pk", “2-pack”
   - If nothing found, default to 1.

5. **SKU/UPC/CODE Extraction Rules**  
   Look for:
   - 6 to 14 digit numbers  
   - alphanumeric product codes  
   - codes BEFORE or AFTER item name  
   - codes in parentheses or at end of line  
   - barcodes split across lines (e.g., “1234” + “567890”) → merge if clearly adjacent

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
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,  # Lower for consistency
        max_tokens=2000  # Increase for long receipts
    )
    return response.choices[0].message.content.strip()

def process_receipt(receipt_id):
    """Process receipt: OCR + AI + save, with better error handling."""
    receipt = receipts.objects.get(id=receipt_id)
    receipt.status = 'processing'
    receipt.save()
    
    try:
        raw_text, avg_conf = extract_text_with_ocr(receipt.image_path.path)
        receipt.raw_ocr_text = raw_text
        receipt.save()
        
        parsed = parse_with_ai(raw_text)
        lines = [line.strip() for line in parsed.split('\n') if line.strip()]
        
        seen_skus = set()  # To avoid duplicates
        i = 0
        line_num = 1
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
                
                # Duplicate check
                if code != 'Not found' and code in seen_skus:
                    code = 'Duplicate - ' + code  # Or handle as needed
                
                seen_skus.add(code)
                
                qty_val = Decimal(qty_str) if qty_str.replace('.', '', 1).isdigit() else None
                unit_val = Decimal(unit_str) if unit_str != 'Not found' and unit_str.replace('.', '', 1).isdigit() else None
                total_val = Decimal(total_str) if total_str != 'Not found' and total_str.replace('.', '', 1).isdigit() else None
                
                item = receipt_items(
                    receipt=receipt,
                    line_number=line_num,
                    product_name=name,
                    sku=code if code != 'Not found' else None,
                    quantity=qty_val,
                    unit_price=unit_val,
                    total_price=total_val,
                    raw_text='\n'.join(lines[i:i+5]),  # Save item-specific raw
                    confidence_score=Decimal(avg_conf),
                    created_at=timezone.now()
                )
                item.save()
                line_num += 1
                i += 5  # Skip to next item block
            else:
                i += 1  # Skip invalid lines
        
        receipt.status = 'done'
        receipt.save()
    
    except Exception as e:
        receipt.status = 'failed'
        receipt.raw_ocr_text += f'\nError: {str(e)}'  # Log error
        receipt.save()
        raise e