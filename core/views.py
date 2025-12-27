from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.contrib.auth.hashers import make_password, check_password
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.contrib import messages
from django.utils import timezone
from pyzbar.pyzbar import decode
from django.urls import reverse
from django.db.models import Q
from openai import OpenAI
from io import StringIO
from PIL import Image
import pandas as pd
import numpy as np
import easyocr
import random
import json
import csv
import re

# functions that are importing from other modules
from core.preprocessing import preprocess_image_pro
from core.barcode import process_sticker
from core.ocr import process_receipt
from core.validators import validate_multiple_images, validate_multiple_stickers
from .models import *
from .utils import *
from core.models import *
from core.validators import *
from core.preprocessing import *
from core.validators import *


def generate_verification_code(length=4):
    """Generate a random 4-digit numeric code"""
    return str(random.randint(1000, 9999))
# Create your views here.
def custom_404(request, exception):
    return render(request, '404.html', status=404)


# Authentication Views
def register(request):
    if request.method == 'POST':
        username = request.POST.get('username').strip()
        email = request.POST.get('email').strip()
        password = request.POST.get('password').strip()
        errors = {}
        if not username:
            errors['username'] = "Username is required."
        elif not re.match(r'^[A-Za-z ]+$', username):
            errors['username'] = "Username can only contain letters and spaces."
        elif User.objects.filter(username=username).exists():
            errors['username'] = "This username is already taken."
        if not email:
            errors['email'] = "Email is required."
        elif User.objects.filter(email=email).exists():
            errors['email'] = "This email is already registered."
        if not password:
            errors['password'] = "Password is required."
        else:
            if len(password) < 8:
                errors['password'] = "Password must be at least 8 characters long."
            elif not re.search(r'[A-Z]', password):
                errors['password'] = "Password must contain at least one uppercase letter."
            elif not re.search(r'[a-z]', password):
                errors['password'] = "Password must contain at least one lowercase letter."
            elif not re.search(r'\d', password):
                errors['password'] = "Password must contain at least one digit."
            elif not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                errors['password'] = "Password must contain at least one special character."
        if errors:
            return JsonResponse({'success': False, 'errors': errors})
        try:
            verification_code = generate_verification_code()
            user = User.objects.create(
                username=username,
                email=email,
                password=make_password(password),
                verification_token=verification_code
            )
            send_mail(
            'Verify Your Email',
            f'Hello {user.username},\n\nThank you for registering!\nYour verification code is: {verification_code}',
            'hasanmaqsood13@gmail.com',
            [user.email],
            fail_silently=False,
            )
            request.session['verification_email'] = email
            request.session['user_id'] = user.id
            next_url = f"/verify-email/?email={user.email}"
            return JsonResponse({'success': True, 'next_url': next_url})
        except Exception as e:
            return JsonResponse({'success': False, 'errors': {'general': str(e)}})
    return render(request, 'register.html')


def emailverification(request):
    if 'verification_email' not in request.session:
        return redirect('register')
    if request.method == 'POST':
        d1 = request.POST.get('dijit1', '').strip()
        d2 = request.POST.get('dijit2', '').strip()
        d3 = request.POST.get('dijit3', '').strip()
        d4 = request.POST.get('dijit4', '').strip()
        entered_otp = d1 + d2 + d3 + d4
        if len(entered_otp) != 4 or not entered_otp.isdigit():
            return JsonResponse({
                'success': False,
                'message': 'Please enter a valid 4-digit code.'
            })
        verification_email = request.session.get('verification_email')
        if not verification_email:
            return JsonResponse({
                'success': False,
                'message': 'Session expired. Please register again.'
            })
        try:
            user = User.objects.get(email=verification_email)
            if user.verification_token == entered_otp:
                user.is_active = True
                user.is_verified = True
                user.verification_token = None
                user.save()
                if 'verification_email' in request.session:
                    del request.session['verification_email']
                if 'user_id' in request.session:
                    del request.session['user_id']
                return JsonResponse({
                    'success': True,
                    'message': 'Congratulations! Your account is now verified.',
                    'redirect_url': '/login'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid OTP. Please try again.'
                })
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'User not found. Please register again.'
            })
    return render(request, 'verify_email.html')


def resend_verification(request):
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        if not user_id:
            return JsonResponse({'success': False, 'message': 'Session expired.'})
        try:
            user = User.objects.get(id=user_id)
            new_code = generate_verification_code()
            user.verification_token = new_code
            user.save()
            send_mail(
                'Verify Your Email',
                f'Hello {user.username},\n\nThank you for registering!\nYour verification code is: {new_code}',
                'hasanmaqsood13@gmail.com',
                [user.email],
                fail_silently=False,
            )
            return JsonResponse({'success': True, 'message': 'New verification code sent.'})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User not found.'})
    return JsonResponse({'success': False, 'message': 'Invalid request.'})


def login(request):
    request.session.flush()
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            user = User.objects.get(email=email)
            if not check_password(password, user.password):
                return JsonResponse({'success': False, 'message': 'Invalid password.'})
            if not user.is_verified:
                return JsonResponse({'success': False, 'message': 'Please verify your email first.'})
            if not user.is_active:
                return JsonResponse({'success': False, 'message': 'Account deactivated.'})
            user.last_login = timezone.now()
            user.save()
            request.session['user_id'] = user.id
            request.session['username'] = user.username
            request.session['role'] = user.role

            next_url = reverse('searchablepanel') if user.role == "admin" else reverse('searchablepanel')
            
            return JsonResponse({'success': True, 'next_url': next_url})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Invalid email.'})
    return render(request, 'login.html')


def forgotpassword(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            reset_token = generate_verification_code()
            user.verification_token = reset_token
            user.is_verified = False
            user.save()
            request.session['reset_email'] = email
            request.session['user_id'] = user.id
            next_url = f"/email-verify/?email={user.email}"
            return JsonResponse({
                'success': True,
                'message': 'Password reset instructions sent to your email.',
                'next_url': next_url,
            })
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'No account found with this email address.'
            })
    return render(request, 'forgotpassword.html')


def forgotpasswordemailverify(request):
    if 'reset_email' not in request.session:
        return redirect('forgotpassword')
    if request.method == 'POST':
        dijit1 = request.POST.get('dijit1', '')
        dijit2 = request.POST.get('dijit2', '')
        dijit3 = request.POST.get('dijit3', '')
        dijit4 = request.POST.get('dijit4', '')
        otp = dijit1 + dijit2 + dijit3 + dijit4
        if not all([dijit1, dijit2, dijit3, dijit4]):
            return JsonResponse({'success': False, 'message': 'Please enter all digits.'})
        user_email = request.session.get('reset_email')
        if not user_email:
            return JsonResponse({'success': False, 'message': "Session expired. Please sign up again."})
        try:
            user = User.objects.get(email=user_email)
            if user.verification_token == otp:
                user.is_verified = True
                user.save()
                if 'reset_email' in request.session:
                    del request.session['reset_email']
                return JsonResponse({
                    'success': True,
                    'message': 'Email verified successfully!',
                    'redirect_url': '/reset-password/'
                })
            else:
                return JsonResponse({'success': False, 'message': 'Invalid verification code.'})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User not found.'})
    return render(request, 'forgotpasswordemailverify.html')


def resetpassword(request):
    if 'user_id' not in request.session:
        return redirect('forgotpassword')
    if request.method == 'POST':
        new_password = request.POST.get('newPassword')
        confirm_password = request.POST.get('confirmPassword')
        user_id = request.session.get('user_id')
        if not user_id:
            return JsonResponse({'success': False, 'message': 'Session expired. Please try again.'})
        if not new_password or not confirm_password:
            return JsonResponse({'success': False, 'message': 'All fields are required.'})
        if new_password != confirm_password:
            return JsonResponse({'success': False, 'message': 'Passwords do not match.'})
        if len(new_password) < 8:
            return JsonResponse({'success': False, 'message': 'Password must be at least 8 characters long.'})
        try:
            user = User.objects.get(id=user_id)
            user.password = make_password(new_password)
            user.save()
            del request.session['user_id']
            if 'reset_email' in request.session:
                del request.session['reset_email']
            return JsonResponse({'success': True, 'message': 'Password reset successfully.', 'redirect_url': '/login'})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User not found.'})
    return render(request, 'resetpassword.html')


def logout(request):
    try:
        request.session.flush()
        messages.success(request, "You have been logged out successfully.")
        return redirect('login')
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
    

def admindashboard(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    user = User.objects.get(id=user_id)
    if not user.is_verified or not user.is_active or user.role != "admin":
        return HttpResponseForbidden("Access Denied")
    return render(request, 'admindashboard.html')


def dashboard_dd(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    user = User.objects.get(id=user_id)
    if not user.is_verified or not user.is_active or user.role != "user":
        return HttpResponseForbidden("Access Denied")
    return HttpResponse("Welcome to the User Dashboard")


def get_session_user(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return None, JsonResponse({"success": False, "error": "User not logged in."}, status=401)
    try:
        user = User.objects.get(id=user_id)
        return user, None
    except User.DoesNotExist:
        return None, JsonResponse({"success": False, "error": "User not found."}, status=404)
    

def perform_matching(user):
    pending_stickers = sticker_data.objects.filter(
        user=user, matching_status='pending', status='processed')
    for sticker in pending_stickers:
        if not sticker.barcode:
            continue
        matching_items = receipt_items.objects.filter(
            receipt__user=user, sku=sticker.barcode, status='done')
        for item in matching_items:
            matched_count = match_history.objects.filter(
                receipt_item=item).count()
            quantity = int(item.quantity) if item.quantity else 0
            if matched_count < quantity:
                match_history.objects.create(
                    sticker_data=sticker,
                    receipt_item=item,
                    SKU=sticker.barcode,
                    matched_at=timezone.now()
                )
                sticker.matching_status = 'matched'
                sticker.save()
                break

def update_receipt_status_after_processing(receipt_id, has_items=True):
    """
    Receipt processing ke baad status update karein
    """
    try:
        receipt = receipts.objects.get(id=receipt_id)
        if has_items:
            receipt.status = 'done'
        else:
            receipt.status = 'failed'
        receipt.save()
    except receipts.DoesNotExist:
        pass


@csrf_exempt
def upload_receipts(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
   
    user, err = get_session_user(request)
    if err:
        return err
   
    files = request.FILES.getlist("files")
    if not files:
        return JsonResponse({"success": False, "message": "No files selected"})
   
    valid_files, rejected_files = validate_multiple_images(files)
   
    response_data = {
        "accepted_files": [f.name for f in valid_files],
        "rejected_files": [{"file": r['file'], "reason": r['errors'][0]} for r in rejected_files],
        "accepted": len(valid_files),
        "rejected": len(rejected_files)
    }
   
    if not valid_files:
        response_data["success"] = False
        response_data["message"] = "All files rejected due to poor quality"
        return JsonResponse(response_data)
   
    response_data["success"] = True
    saved_ids = []
   
    for file in valid_files:
        try:
            ext = file.name.split('.')[-1].lower()
            if ext in ['jpg', 'jpeg', 'png']:
                processed_file = preprocess_image_pro(file)
            else:
                processed_file = file
            receipt = receipts(
                user=user,
                original_filename=file.name,
                file_size=file.size,
                year=timezone.now().year,
                month=timezone.now().month,
                status='pending'
            )
            receipt.image_path.save(file.name, processed_file, save=True)
            saved_ids.append(receipt.id)
        except Exception as e:
            print(f"Error processing {file.name}: {e}")
            continue
   
    total_items = 0
    for sid in saved_ids:
        try:
            process_receipt(sid)
           
            item_count = receipt_items.objects.filter(receipt_id=sid).count()
            total_items += item_count
           
            receipt_obj = receipts.objects.get(id=sid)
            if item_count > 0:
                receipt_obj.status = 'done'
                print(f"✅ Receipt {sid} processed: {item_count} items created")
            else:
                receipt_obj.status = 'failed'
                print(f"⚠️ Receipt {sid} failed: No items extracted")
            receipt_obj.save()
               
        except Exception as e:
            print(f"Error in OCR/AI for receipt {sid}: {e}")
            receipts.objects.filter(id=sid).update(status='failed')
   
    response_data["items_created"] = total_items
    response_data["message"] = f"{total_items} items created and automatically matched with ASINs"
   
    from core.matching import perform_sticker_receipt_matching
    sticker_matches = perform_sticker_receipt_matching(user)
    response_data["sticker_matches"] = sticker_matches
    response_data["message"] += f" and {sticker_matches} sticker matches created"
   
    return JsonResponse(response_data)


@csrf_exempt
def upload_stickers(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
   
    user, err = get_session_user(request)
    if err:
        return err
   
    files = request.FILES.getlist("files")
    if not files:
        return JsonResponse({"success": False, "message": "No files selected"})
   
    valid_files, rejected_files = validate_multiple_stickers(files)
    response_data = {
        "success": True,
        "accepted": len(valid_files),
        "rejected": len(rejected_files),
        "results": [],
        "failed_count": 0,
        "success_count": 0
    }
   
    if rejected_files:
        response_data["rejection_details"] = [
            {"file": r['file'], "reason": r['errors'][0]} for r in rejected_files
        ]
   
    processed_files = []
   
    for file in valid_files:
        if file.name in processed_files:
            response_data["results"].append({
                "file": file.name,
                "status": "skipped",
                "reason": "Duplicate in batch"
            })
            continue
       
        try:
            existing_sticker = stickers.objects.filter(
                user=user,
                original_filename=file.name,
                file_size=file.size
            ).first()
           
            if existing_sticker:
                response_data["results"].append({
                    "file": file.name,
                    "status": "skipped",
                    "reason": "Already uploaded before"
                })
                continue
           
            sticker = stickers(
                user=user,
                original_filename=file.name,
                file_size=file.size,
                year=timezone.now().year,
                month=timezone.now().month,
                status='pending'
            )
            sticker.image_path.save(file.name, file, save=True)
           
            result = process_sticker(sticker.id)
           
            processed_files.append(file.name)
           
            if result["status"] == "success":
                response_data["success_count"] += 1
                response_data["results"].append({
                    "file": result["file"],
                    "barcode": result.get("barcode"),
                    "status": "success"
                })
            elif result["status"] == "skipped":
                response_data["results"].append({
                    "file": result["file"],
                    "status": "skipped",
                    "reason": result.get("reason", "Already processed")
                })
            else:
                response_data["failed_count"] += 1
                response_data["results"].append({
                    "file": result.get("file", file.name),
                    "status": "failed",
                    "reason": result.get("reason", "Barcode not detected")
                })
           
        except Exception as e:
            print(f"Error processing sticker {file.name}: {e}")
            response_data["failed_count"] += 1
            response_data["results"].append({
                "file": file.name,
                "status": "failed",
                "reason": "Processing error"
            })
   
    return JsonResponse(response_data)


def all_receipts(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponseForbidden("Access Denied")
    if not user.is_verified or not user.is_active:
        return HttpResponseForbidden("Access Denied")
    receipts_list = receipts.objects.filter(user=user).order_by('-upload_date')
    return render(request, 'all_receipts.html', {'receipts': receipts_list})



@require_POST
def delete_receipt(request, receipt_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
    try:
        receipt = receipts.objects.get(id=receipt_id, user_id=user_id)
        receipt.delete()
        return JsonResponse({'status': 'success', 'message': f'Receipt #{receipt_id} deleted successfully.'})
    except receipts.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Receipt not found or forbidden'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_POST
def delete_multiple_receipts(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
    try:
        data = json.loads(request.body)
        receipt_ids = data.get('ids', [])
        if not receipt_ids:
            return JsonResponse({'status': 'error', 'message': 'No receipts selected for deletion.'}, status=400)
        deleted_count, _ = receipts.objects.filter(
            id__in=receipt_ids, user_id=user_id).delete()
        return JsonResponse({'status': 'success', 'message': f'{deleted_count} receipts deleted successfully.'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def receipt_details(request, receipt_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    receipt = get_object_or_404(receipts, id=receipt_id, user_id=user_id)

    return render(request, 'receipt_details.html', {'receipt': receipt})


def edit_receipt(request, receipt_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
    receipt_instance = get_object_or_404(
        receipts, id=receipt_id, user_id=user_id)
    if request.method == 'POST':
        try:
            receipt_instance.original_filename = request.POST.get(
                'original_filename', receipt_instance.original_filename)
            receipt_instance.status = request.POST.get(
                'status', receipt_instance.status)
            receipt_instance.save()
            return JsonResponse({'status': 'success', 'message': 'Receipt updated successfully.',
                                 'receipt_data': {
                                     'id': receipt_instance.id,
                                     'filename': receipt_instance.original_filename,
                                     'status': receipt_instance.status,
                                 }})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({
        'id': receipt_instance.id,
        'original_filename': receipt_instance.original_filename,
        'status': receipt_instance.status,
    })


def all_receipt_items(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponseForbidden("Access Denied")
    if not user.is_verified or not user.is_active:
        return HttpResponseForbidden("Access Denied")
    items_list = receipt_items.objects.filter(
        receipt__user=user).order_by('-created_at')
    return render(request, 'receipt_items.html', {'receipt_items': items_list})


@csrf_exempt
def update_receipt_item(request):
    if request.method == "POST":
        try:
            item = receipt_items.objects.get(id=request.POST.get("item_id"))
            item.line_number = request.POST.get("line_number")
            item.sku = request.POST.get("sku")
            item.product_name = request.POST.get("product_name")
            item.quantity = request.POST.get("quantity") or None
            item.unit_price = request.POST.get("unit_price") or None
            item.total_price = request.POST.get("total_price") or None
            item.status = request.POST.get("status")
            item.save()
            return JsonResponse({"success": True})
        except receipt_items.DoesNotExist:
            return JsonResponse({"success": False, "error": "Item not found"})


def item_details(request, item_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponseForbidden("Access Denied")
    if not user.is_verified or not user.is_active:
        return HttpResponseForbidden("Access Denied")
    item = get_object_or_404(
        receipt_items.objects.select_related('receipt'),
        id=item_id,
        receipt__user_id=user_id
    )
    return render(request, 'item_details.html', {'item': item})



@require_POST
@csrf_exempt
def delete_receipt_item(request, item_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
    try:
        item = receipt_items.objects.get(
            id=item_id,
            receipt__user_id=user_id
        )
        item.delete()
        return JsonResponse({'success': True, 'message': 'Item deleted successfully'})
    except receipt_items.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Item not found or forbidden'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def delete_multiple_items(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
    try:
        data = json.loads(request.body)
        item_ids = data.get('ids', [])
        if not item_ids:
            return JsonResponse({'success': False, 'error': 'No items selected for deletion'}, status=400)

        deleted_count = receipt_items.objects.filter(
            id__in=item_ids,
            receipt__user_id=user_id
        ).delete()[0]
        return JsonResponse({
            'success': True,
            'message': f'{deleted_count} items deleted successfully'
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

def all_stickers(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponseForbidden("Access Denied")
    if not user.is_verified or not user.is_active:
        return HttpResponseForbidden("Access Denied")
    stickers_list = stickers.objects.filter(user=user).order_by('-upload_date')
    return render(request, 'all_stickers.html', {'stickers': stickers_list})


@require_POST
def delete_sticker(request, sticker_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
    try:
        sticker = stickers.objects.get(id=sticker_id, user_id=user_id)
        sticker.delete()
        return JsonResponse({'status': 'success', 'message': f'Sticker #{sticker_id} deleted successfully.'})
    except stickers.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Sticker not found or forbidden'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    

@require_POST
def delete_multiple_stickers(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
    try:
        data = json.loads(request.body)
        sticker_ids = data.get('ids', [])
        if not sticker_ids:
            return JsonResponse({'status': 'error', 'message': 'No stickers selected for deletion.'}, status=400)
        deleted_count, _ = stickers.objects.filter(
            id__in=sticker_ids, user_id=user_id).delete()
        return JsonResponse({'status': 'success', 'message': f'{deleted_count} stickers deleted successfully.'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    

def sticker_details(request, sticker_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    sticker = get_object_or_404(stickers, id=sticker_id, user_id=user_id)
    return render(request, 'sticker_details.html', {'sticker': sticker})


def edit_sticker(request, sticker_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
    sticker_instance = get_object_or_404(
        stickers, id=sticker_id, user_id=user_id)
    if request.method == 'POST':
        try:
            sticker_instance.original_filename = request.POST.get(
                'original_filename', sticker_instance.original_filename)
            sticker_instance.status = request.POST.get(
                'status', sticker_instance.status)
            sticker_instance.save()
            return JsonResponse({'status': 'success', 'message': 'Sticker updated successfully.',
                                 'sticker_data': {
                                     'id': sticker_instance.id,
                                     'filename': sticker_instance.original_filename,
                                     'status': sticker_instance.status,
                                 }})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({
        'id': sticker_instance.id,
        'original_filename': sticker_instance.original_filename,
        'status': sticker_instance.status,
    })


def all_sticker_data(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponseForbidden("Access Denied")
    if not user.is_verified or not user.is_active:
        return HttpResponseForbidden("Access Denied")
    data_list = sticker_data.objects.filter(user=user).order_by('-created_at')
    return render(request, 'all_sticker_data.html', {'sticker_data': data_list})


@csrf_exempt
def update_sticker_data(request):
    if request.method == "POST":
        try:
            data_item = sticker_data.objects.get(
                id=request.POST.get("item_id"))
            data_item.barcode = request.POST.get("barcode")
            data_item.original_filename = request.POST.get("original_filename")
            data_item.status = request.POST.get("status")
            data_item.matching_status = request.POST.get("matching_status")
            data_item.save()
            return JsonResponse({"success": True})
        except sticker_data.DoesNotExist:
            return JsonResponse({"success": False, "error": "Sticker data not found"})
        

def sticker_data_details(request, stickerdata_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponseForbidden("Access Denied")
    if not user.is_verified or not user.is_active:
        return HttpResponseForbidden("Access Denied")
    data_item = get_object_or_404(
        sticker_data,
        id=stickerdata_id,
        user_id=user_id
    )
    return render(request, 'sticker_data_details.html', {'item': data_item})


@require_POST
@csrf_exempt
def delete_sticker_data(request, stickerdata_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
    try:
        data_item = sticker_data.objects.get(
            id=stickerdata_id,
            user_id=user_id
        )
        data_item.delete()
        return JsonResponse({'success': True, 'message': 'Sticker data deleted successfully'})
    except sticker_data.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Sticker data not found or forbidden'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

@require_POST
@csrf_exempt
def delete_multiple_sticker_data(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
    try:
        data = json.loads(request.body)
        data_ids = data.get('ids', [])
        if not data_ids:
            return JsonResponse({'success': False, 'error': 'No sticker data selected for deletion'}, status=400)
        deleted_count = sticker_data.objects.filter(
            id__in=data_ids,
            user_id=user_id
        ).delete()[0]
        return JsonResponse({
            'success': True,
            'message': f'{deleted_count} sticker data deleted successfully'
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    


def all_matches(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponseForbidden("Access Denied")
    if not user.is_verified or not user.is_active:
        return HttpResponseForbidden("Access Denied")
    matches_list = match_history.objects.filter(
        sticker_data__user=user).order_by('-matched_at')
    return render(request, 'all_matches.html', {'matches': matches_list})


@require_POST
def delete_match(request, match_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
    try:
        match = match_history.objects.get(
            id=match_id, sticker_data__user_id=user_id)
        match.delete()
        return JsonResponse({'status': 'success', 'message': f'Match #{match_id} deleted successfully.'})
    except match_history.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Match not found or forbidden'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    

@require_POST
def delete_multiple_matches(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
    try:
        data = json.loads(request.body)
        match_ids = data.get('ids', [])
        if not match_ids:
            return JsonResponse({'status': 'error', 'message': 'No matches selected for deletion.'}, status=400)
        deleted_count, _ = match_history.objects.filter(
            id__in=match_ids, sticker_data__user_id=user_id).delete()
        return JsonResponse({'status': 'success', 'message': f'{deleted_count} matches deleted successfully.'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    

def match_details(request, match_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    match = get_object_or_404(
        match_history, id=match_id, sticker_data__user_id=user_id)
    return render(request, 'match_details.html', {'match': match})


def all_unmatched(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponseForbidden("Access Denied")
    if not user.is_verified or not user.is_active:
        return HttpResponseForbidden("Access Denied")
    unmatched_list = sticker_data.objects.filter(
        user=user, matched_status='unmatched').order_by('-created_at')
    return render(request, 'all_unmatched.html', {'unmatched': unmatched_list})


def asin_upload_page(request):
    return render(request, 'asins_upload.html')

@csrf_exempt
def upload_asins_file(request):
    if request.method == "GET":
        return JsonResponse({"success": False, "message": "Invalid method"}, status=405)
    if request.method == "POST":
        user, err = get_session_user(request)
        if err:
            return err
        files = request.FILES.getlist("file")
        if len(files) != 1:
            return JsonResponse({"success": False, "message": "Only one file allowed at a time"}, status=400)
        file = files[0]
        inserted = 0
        skipped = 0
        try:
            if file.name.lower().endswith('.csv'):
                decoded_file = file.read().decode('utf-8')
                io_string = StringIO(decoded_file)
                reader = csv.DictReader(io_string)
                for row in reader:
                    title = row.get('title', '').strip()
                    price = float(row.get('price', 0))
                    asin = row.get('asin', '').strip()
                    if not title or not asin:
                        continue
                    if ASINs.objects.filter(user=user, title=title, price=price, asin=asin).exists():
                        skipped += 1
                        continue
                    ASINs.objects.create(
                        user=user,
                        title=title,
                        price=price,
                        asin=asin,
                        created_at=timezone.now()
                    )
                    inserted += 1
            elif file.name.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file)
                df = df.iloc[:, [0, 4, 16]] 
                df.columns = ['title', 'price', 'asin']
                for _, row in df.iterrows():
                    title = str(row['title']).strip()
                    price = float(row['price'])
                    asin = str(row['asin']).strip()
                    if not title or not asin:
                        continue
                    if ASINs.objects.filter(user=user, title=title, price=price, asin=asin).exists():
                        skipped += 1
                        continue
                    ASINs.objects.create(
                        user=user,
                        title=title,
                        price=price,
                        asin=asin,
                        created_at=timezone.now()
                    )
                    inserted += 1
            else:
                return JsonResponse({"success": False, "message": "Only CSV or Excel files are allowed"}, status=400)
            return JsonResponse({
                "success": True,
                "inserted": inserted,
                "skipped": skipped,
                "message": f"{inserted} new ASINs added, {skipped} skipped (already exists)."
            })
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Error processing file: {str(e)}"}, status=500)
        

def all_asins(request):
    user, err = get_session_user(request)
    if err:
        return err
    asins_list = ASINs.objects.filter(user=user).order_by('-created_at')
    context = {
        "asins": asins_list
    }
    return render(request, "all_asins.html", context)


def searchablepanel(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponseForbidden("Access Denied: User not found")
    if not user.is_verified or not user.is_active:
        return HttpResponseForbidden("Access Denied: Account not verified or active")
    total_receipts = receipts.objects.filter(user=user).count()
    total_stickers = stickers.objects.filter(user=user).count()
    total_matches = match_history.objects.filter(
        sticker_data__user=user).count()
    total_matched_with_asins = MatchedProducts.objects.filter(
        user=user).count()
    context = {
        'user': user,
        'total_receipts': total_receipts,
        'total_stickers': total_stickers,
        'total_matches': total_matches,
        'total_matched_with_asins': total_matched_with_asins,
    }
    return render(request, 'searchablepanel.html', context)


@csrf_exempt
def search_dashboard(request):
    if request.method == "POST":
        user_id = request.session.get('user_id')
        if not user_id:
            return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
        search_query = request.POST.get('search', '').strip().lower()
        if not search_query:
            return JsonResponse({'success': False, 'error': 'Please enter a search term'})
        results = []
       
        matched_products = MatchedProducts.objects.filter(
            user=user
        ).filter(
            Q(receipt_item__sku__icontains=search_query) |
            Q(receipt_item__product_name__icontains=search_query) |
            Q(asin_record__asin__icontains=search_query) |
            Q(asin_record__title__icontains=search_query)
        ).select_related('receipt_item', 'asin_record')[:20]
        for item in matched_products:
            results.append({
                'id': item.id,
                'type': 'Receipt → ASIN Match',
                'category': 'matched_asin',
                'sku': item.receipt_item.sku if item.receipt_item.sku else 'N/A',
                'product_name': item.receipt_item.product_name if item.receipt_item.product_name else 'N/A',
                'asin': item.asin_record.asin,
                'title': item.asin_record.title,
                'price': f"${item.asin_record.price:.2f}" if item.asin_record.price else 'N/A',
                'matched_at': item.matched_at.strftime('%b %d, %Y %I:%M %p') if item.matched_at else 'N/A',
                'url': f'/matched-products/details/{item.id}/'
            })
        sticker_matches = match_history.objects.filter(
            sticker_data__user=user
        ).filter(
            Q(SKU__icontains=search_query) |
            Q(receipt_item__product_name__icontains=search_query)
        ).select_related('sticker_data', 'receipt_item')[:20]
        for item in sticker_matches:
            results.append({
                'id': item.id,
                'type': 'Sticker → Receipt Match',
                'category': 'sticker_match',
                'sku': item.SKU if item.SKU else 'N/A',
                'product_name': item.receipt_item.product_name if item.receipt_item.product_name else 'N/A',
                'quantity': str(item.receipt_item.quantity) if item.receipt_item.quantity else 'N/A',
                'price': f"${item.receipt_item.unit_price:.2f}" if item.receipt_item.unit_price else 'N/A',
                'matched_at': item.matched_at.strftime('%b %d, %Y %I:%M %p') if item.matched_at else 'N/A',
                'url': f'/match/details/{item.id}/'
            })
        if len(results) < 10: 
            receipt_items_search = receipt_items.objects.filter(
                receipt__user=user
            ).filter(
                Q(sku__icontains=search_query) |
                Q(product_name__icontains=search_query)
            ).select_related('receipt')[:10]
            for item in receipt_items_search:
                results.append({
                    'id': item.id,
                    'type': 'Receipt Item',
                    'category': 'receipt',
                    'sku': item.sku if item.sku else 'N/A',
                    'product_name': item.product_name if item.product_name else 'N/A',
                    'quantity': str(item.quantity) if item.quantity else 'N/A',
                    'price': f"${item.unit_price:.2f}" if item.unit_price else 'N/A',
                    'total_price': f"${item.total_price:.2f}" if item.total_price else 'N/A',
                    'url': f'/item/details/{item.id}/',
                    'created_at': item.created_at.strftime('%b %d, %Y %I:%M %p') if item.created_at else 'N/A',
                })
        if len(results) < 10:
            asins_search = ASINs.objects.filter(user=user).filter(
                Q(asin__icontains=search_query) |
                Q(title__icontains=search_query)
            )[:10]
            for item in asins_search:
                results.append({
                    'id': item.id,
                    'type': 'ASIN Record',
                    'category': 'asin',
                    'asin': item.asin,
                    'title': item.title,
                    'price': f"${item.price:.2f}" if item.price else 'N/A',
                    'match_count': item.match_count,
                    'url': f'/asin/details/{item.id}/',
                    'created_at': item.created_at.strftime('%b %d, %Y %I:%M %p') if item.created_at else 'N/A'
                })
        return JsonResponse({
            'success': True,
            'results': results,
            'total_found': len(results),
            'search_query': search_query
        })
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)



def all_matched_products(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
   
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponseForbidden("Access Denied")
   
    if not user.is_verified or not user.is_active:
        return HttpResponseForbidden("Access Denied")
   
    print(f"🔍 User ID: {user_id}")
    print(f"👤 User: {user.username}")
   
    matched_products = MatchedProducts.objects.filter(
        user=user
    ).select_related('receipt_item', 'asin_record').order_by('-matched_at')
   
    print(f"📊 Total matched products found: {matched_products.count()}")
   
    for mp in matched_products[:5]:
        print(f"📦 Match: {mp.receipt_item.product_name} → {mp.asin_record.asin}")
   

    stats = {
        'total_matches': matched_products.count(),
        'unique_asins': matched_products.values('asin_record').distinct().count(),
        'unique_products': matched_products.values('receipt_item').distinct().count(),
    }
   

    print(f"📈 Stats: {stats}")
   
    return render(request, 'matched_products.html', {
        'matched_products': matched_products,
        'stats': stats,
        'user': user
    })


@csrf_exempt
def run_matching(request):
    """Manual matching run karne ke liye"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST allowed'})
   
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'error': 'Authentication required'})
   
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'})
   
    try:
        matched_products_count = 0
       
        receipt_items_list = receipt_items.objects.filter(
            receipt__user=user,
            status='processed'
        )
       
        for item in receipt_items_list:
            if item.product_name and item.product_name != 'Unknown':
                product_name_lower = item.product_name.strip().lower()
               
                matching_asins = ASINs.objects.filter(
                    user=user,
                    title__iexact=product_name_lower
                )
               
                for asin in matching_asins:
                    obj, created = MatchedProducts.objects.get_or_create(
                        user=user,
                        receipt_item=item,
                        asin_record=asin,
                        defaults={'matched_at': timezone.now()}
                    )
                   
                    if created:
                        matched_products_count += 1
                        asin.match_count += 1
                        asin.save()
       
        from core.matching import match_sticker_with_receipt
        sticker_matches = match_sticker_with_receipt(user)
       
        return JsonResponse({
            'success': True,
            'asin_matches': matched_products_count,
            'sticker_matches': sticker_matches,
            'message': f'{matched_products_count} ASIN matches, {sticker_matches} sticker matches created'
        })
       
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
   
@csrf_exempt
def update_receipt_item(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"})
   
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({"success": False, "error": "User not authenticated"})
   
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "error": "User not found"})
   
    print("=== DEBUG: Received POST Data ===")
    for key, value in request.POST.items():
        print(f"{key}: {value}")
   
    try:
        item_id = request.POST.get("item_id")
        if not item_id:
            return JsonResponse({"success": False, "error": "Item ID is required"})
       
        item = receipt_items.objects.get(
            id=item_id,
            receipt__user_id=user_id
        )
       
        print(f"=== DEBUG: Found item {item.id} ===")
        print(f"Old status: {item.status}")
       
        item.line_number = request.POST.get("line_number", item.line_number)
        item.sku = request.POST.get("sku", item.sku)
        item.product_name = request.POST.get("product_name", item.product_name)
       
        quantity = request.POST.get("quantity")
        if quantity and quantity.strip() and quantity != 'null':
            item.quantity = float(quantity)
        else:
            item.quantity = None
       
        unit_price = request.POST.get("unit_price")
        if unit_price and unit_price.strip() and unit_price != 'null':
            item.unit_price = float(unit_price)
        else:
            item.unit_price = None
       
        total_price = request.POST.get("total_price")
        if total_price and total_price.strip() and total_price != 'null':
            item.total_price = float(total_price)
        else:
            item.total_price = None
       
        new_status = request.POST.get("status")
        print(f"New status from form: {new_status}")
       
        if new_status and new_status.strip():
            item.status = new_status.strip()
       
        item.raw_text = request.POST.get("raw_text", "")
       
        item.save()
       
        item.refresh_from_db()
        print(f"=== DEBUG: After Save ===")
        print(f"New status: {item.status}")
       
        return JsonResponse({
            "success": True,
            "message": "Item updated successfully",
            "item_id": item.id,
            "new_status": item.status
        })
       
    except receipt_items.DoesNotExist:
        print("ERROR: Item not found")
        return JsonResponse({"success": False, "error": "Item not found or forbidden"})
    except ValueError as e:
        print(f"ERROR: Invalid numeric value: {str(e)}")
        return JsonResponse({"success": False, "error": f"Invalid numeric value: {str(e)}"})
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)})
   
@csrf_exempt
def update_sticker_data(request):
    if request.method == "POST":
        try:
            data_item = sticker_data.objects.get(
                id=request.POST.get("item_id"))
            data_item.barcode = request.POST.get("barcode")
            data_item.original_filename = request.POST.get("original_filename")
            data_item.status = request.POST.get("status")
            data_item.matched_status = request.POST.get("matched_status")
            data_item.save()
            return JsonResponse({"success": True})
        except sticker_data.DoesNotExist:
            return JsonResponse({"success": False, "error": "Sticker data not found"})