from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.contrib.auth.hashers import make_password, check_password
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from config.settings import EMAIL_HOST_USER
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from django.core.mail import send_mail
from django.utils.text import slugify
from django.core import serializers
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from urllib.parse import unquote
from django.db.models import Sum
from django.urls import reverse
from datetime import timedelta
from datetime import datetime
import random
import json
import re
from django.utils.timezone import now
from core.models import *
from django.core.files.base import ContentFile
from core.validators import validate_multiple_images
import threading
from openai import OpenAI
import easyocr
from PIL import Image
import numpy as np
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from .models import *
from core.validators import *
from core.preprocessing import *
from pyzbar.pyzbar import decode
from core.process_stickers import *
from core.validators import *

def generate_verification_code(length=4):
    """Generate a random 4-digit numeric code"""
    return str(random.randint(1000, 9999))

# Create your views here.
def home(request):
    return HttpResponse("Welcome to the Home Page")


# Authentication Views
def register(request):
    if request.method == 'POST':
        username = request.POST.get('username').strip()
        email = request.POST.get('email').strip()
        password = request.POST.get('password').strip()

        errors = {}

        if not username:
            errors['name'] = "Name is required."
        elif not re.match(r'^[A-Za-z ]+$', username):
            errors['name'] = "Name can only contain letters and spaces."
        elif User.objects.filter(username=username).exists():
            errors['name'] = "This username is already taken."

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

            # send_mail(
            #     'Verify Your Email',
            #     f'Hello {user.username},\n\nThank you for registering!\nYour verification code is: {verification_code}',
            #     'hasanmaqsood13@gmail.com',
            #     [user.email],
            #     fail_silently=False,
            # )

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


            next_url = "/dashboard/" if user.role == "admin" else "/hemloo/"
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
    














# Dashboard Views
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
    






from core.validators import *
from core.preprocessing import *
from core.ocr import process_receipt

# Upload Receipts and Stickers Views
@csrf_exempt
def upload_receipts(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    user, err = get_session_user(request)
    if err: return err
    files = request.FILES.getlist("files")
    if not files:
        return JsonResponse({"success": False, "message": "No files selected"})
    # Step 1: Validate and filter by quality
    valid_files, rejected_files = validate_multiple_images(files)
   
    if not valid_files:
        return JsonResponse({
            "success": False,
            "message": "All files rejected due to poor quality",
            "rejected": [{"file": r['file'], "reason": r['errors'][0]} for r in rejected_files]
        })
   
    # If some files were rejected, inform user
    response_data = {
        "success": True,
        "accepted": len(valid_files),
        "rejected": len(rejected_files)
    }
   
    if rejected_files:
        response_data["rejection_details"] = [
            {"file": r['file'], "reason": r['errors'][0]}
            for r in rejected_files[:5]  # Limit to 5 for response size
        ]
    # Step 2: Process valid files
    saved_ids = []
    for file in valid_files:
        try:
            processed_file = preprocess_image_pro(file)
           
            receipt = receipts(
                user=user,
                original_filename=file.name,
                file_size=file.size,
                year=now().year,
                month=now().month,
                status='pending'  # Changed to 'pending'
            )
            receipt.image_path.save(file.name, processed_file, save=True)
            saved_ids.append(receipt.id)
        except Exception as e:
            print(f"Error processing {file.name}: {e}")
            continue
    # Step 3: OCR + AI Processing (synchronous for now)
    for sid in saved_ids:
        try:
            process_receipt(sid)
            response_data['message'] = 'Processing complete!'  # Optional
        except Exception as e:
            print(f"Error in OCR/AI for receipt {sid}: {e}")
            receipts.objects.filter(id=sid).update(status='failed')

    return JsonResponse(response_data)

from core.barcode import process_sticker

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

    # Simple extension validation
    valid_files, rejected_files = validate_multiple_stickers(files)

    response_data = {
        "success": True,
        "accepted": len(valid_files),
        "rejected": len(rejected_files),
        "results": [],  # ← Ye naya hai
        "failed_count": 0,
        "success_count": 0
    }

    if rejected_files:
        response_data["rejection_details"] = [
            {"file": r['file'], "reason": r['errors'][0]} for r in rejected_files
        ]

    # Save + Process each file
    for file in valid_files:
        try:
            sticker = stickers(
                user=user,
                original_filename=file.name,
                file_size=file.size,
                year=timezone.now().year,
                month=timezone.now().month,
                status='pending'
            )
            sticker.image_path.save(file.name, file, save=True)

            # Process immediately
            result = process_sticker(sticker.id)

            if result["status"] == "success":
                response_data["success_count"] += 1
                response_data["results"].append({
                    "file": result["file"],
                    "barcode": result["barcode"],
                    "status": "success"
                })
            else:
                response_data["failed_count"] += 1
                response_data["results"].append({
                    "file": result["file"],
                    "status": "failed",
                    "reason": result.get("reason", "Barcode not detected")
                })

        except Exception as e:
            response_data["failed_count"] += 1
            response_data["results"].append({
                "file": file.name,
                "status": "failed",
                "reason": "Processing error"
            })

    return JsonResponse(response_data)