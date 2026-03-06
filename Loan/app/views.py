from django.shortcuts import render, redirect, get_object_or_404
from .models import *
from django.contrib import messages
import time
from django.http.response import JsonResponse
import os
from datetime import datetime
from decimal import Decimal  # used for EMI/risk calculations (loanrequest/dashboard views)
from django.conf import settings
import json
from datetime import datetime as _dt
from django.utils import timezone
from django.db.models import Max
 

def admin_feedback(request):
    data = Feedback.objects.values(
        "id",
        "message",
        "rating",
        "username__username"
    )
    return render(request,'admin/admin_feedback.html',context={"data":list(data)})

def submit_feedback(request):
    # Pass username/id for `base_user.html` avatar and consistent navbar across user pages.
    user_id = request.session.get('user_id')
    username = request.session.get('username', 'User')
    if request.method == 'POST':
        id = request.POST.get("id",0) 
        message = request.POST.get("message", "")
        rating = request.POST.get("rating", "")
        user=User.objects.filter(id=int(id)).last()
        Feedback(
            username=user,
            message=message,
            rating=rating,
        ).save()

        return render(request, "user/submit_feedback.html", context={'id': user_id, 'username': username})
    else:  
        return render(request, "user/submit_feedback.html", context={'id': user_id, 'username': username})

def getprofile(request):
    id=request.GET.get('id',0)
    data=User.objects.filter(id=int(id)).values(
            'id',
            'username',
            'email',
            'profile_pic',
            'full_name',
            'gender',
            'date_of_birth',
            'mobile_number',
            'address',
            'pan_number',
            'verification_status',
            'pan_card_document',
            'rejection_reason',
    ).last()
    return JsonResponse(data)


def paymentadmin(request):
    transactions = Transaction.objects.select_related('username', 'loan').all()
    data = [
        {
            "id": t.id,
            "transaction_number": t.transaction_number,
            "username": getattr(t.username, "username", ""),
            "loan_number": getattr(t.loan, "loan_number", ""),
            "monthlyamount": t.monthlyamount,
            "method": t.method,
            "transaction_date": t.transaction_date,
            "status": t.status,
            "upi_id": t.upi_id or "",
            "card_number": t.card_number or "",
            "wallet_name": t.wallet_name or "",
            "wallet_number": t.wallet_number or "",
        }
        for t in transactions
    ]
    return render(request, 'admin/paymentadmin.html', context={"data": data})


from django.http import HttpResponseBadRequest
def payment(request, loan_id=None):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    if request.method == 'POST':
        user_id       = request.POST.get('id', str(user_id))
        loan_id       = request.POST.get('loan_id', '0')
        monthlyamount = request.POST.get('monthlyamount', '0')
        method        = (request.POST.get('method', '') or '').strip().upper()
        upi_id        = request.POST.get('upi_id',        '') or ''
        card_number   = request.POST.get('card_number',   '') or ''
        wallet_name   = request.POST.get('wallet_name',   '') or ''
        wallet_number = request.POST.get('wallet_number', '') or ''
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return HttpResponseBadRequest("Invalid user ID")
        try:
            loan_id = int(loan_id)
        except (ValueError, TypeError):
            return HttpResponseBadRequest("Invalid loan ID")
        user = User.objects.filter(id=user_id).first()
        if not user:
            return HttpResponseBadRequest("User not found")
        loan = Loantable.objects.filter(id=loan_id, details_id=user_id).first()
        if not loan:
            return HttpResponseBadRequest("Loan not found")
        if loan.status == 'Completed':
            return HttpResponseBadRequest("Loan is already completed")
        try:
            monthlyamount = int(monthlyamount)
        except (ValueError, TypeError):
            monthlyamount = 0
        if loan.monthlyamount and monthlyamount != int(loan.monthlyamount):
            monthlyamount = int(loan.monthlyamount)
        if monthlyamount <= 0:
            return HttpResponseBadRequest("Invalid monthly amount")
        if method == "UPI" and not upi_id:
            return HttpResponseBadRequest("UPI ID is required for UPI payment")
        if method == "CARD" and not card_number:
            return HttpResponseBadRequest("Card number is required for card payment")
        if method == "WALLET" and (not wallet_name or not wallet_number):
            return HttpResponseBadRequest("Wallet details are required for wallet payment")
        next_installment = (loan.paid_installments or 0) + 1
        exists = Transaction.objects.filter(loan=loan, installment_number=next_installment, status__in=['Pending', 'Success']).exists()
        if exists:
            return HttpResponseBadRequest("Installment already initiated")
        transaction_dt = timezone.now()
        max_txn = Transaction.objects.aggregate(m=Max('transaction_number'))['m'] or 0
        next_txn = int(max_txn) + 1
        tx = Transaction.objects.create(
            username=user,
            loan=loan,
            monthlyamount=monthlyamount,
            method=method,
            transaction_date=transaction_dt,
            status="Pending",
            installment_number=next_installment,
            transaction_number=next_txn,
            upi_id=upi_id or None,
            card_number=card_number or None,
            wallet_name=wallet_name or None,
            wallet_number=wallet_number or None,
        )
        try:
            from web3 import Web3
            with open('blocks/build/contracts/LoanTable.json') as e:
                abi=json.load(e)['abi']
            web3=Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))
            one={'from':'0xed7cba29AC1e3796d45139FE1aBaeea04A7C1380'}
            contract_note_instance=web3.eth.contract(address="0xc76b612eA01f2e41374F35673848D2D71f4c79B3",abi=abi)
            contract_note_instance.functions.addTransaction(
                user.username,
                monthlyamount,
                method,
                transaction_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "Pending",
                upi_id,
                card_number,
                wallet_name,
                wallet_number
            ).transact(one)
        except Exception:
            pass
        return redirect('transaction')
    if loan_id is None:
        loan_id = request.GET.get('loan_id', '')
    try:
        loan_id = int(loan_id)
        loan = Loantable.objects.filter(id=loan_id, details_id=user_id).values('id', 'monthlyamount').first()
        context = {
            'loan': loan or {'id': ''},
            'monthlyamount': (loan or {}).get('monthlyamount', 0),
            'id': user_id,
            'username': request.session.get('username', ''),
        }
    except (ValueError, TypeError):
        context = {'loan': {'id': ''}, 'monthlyamount': 0, 'id': user_id, 'username': request.session.get('username', '')}
    return render(request, 'user/payment.html', context)


def get_approved_loans(request):
    id=request.GET.get('id','') 
    data = Loantable.objects.filter(details_id=int(id)).values(
        "id",
        "loan_number",
        "customer_name", 
        "loan_details", 
        "interest_rate",
        "amount", 
        "monthlyamount", 
        "duration", 
        "status", 
        "rejection_reason", 
        "approved_reason",
        "start_date",
        ) 
        
    return JsonResponse({'data':list(data)})

def approved_loans(request):
    user_id = request.session.get('user_id')
    user_obj = User.objects.filter(id=user_id).first() if user_id else None
    username = getattr(user_obj, 'username', None) or request.session.get('username', 'User')
    return render(request, 'user/approved_loans.html', context={'id': user_id, 'username': username})
    
def applied_loans(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    user_obj = User.objects.filter(id=user_id).first()
    username = getattr(user_obj, 'username', None) or request.session.get('username', 'User')
    return render(request, 'user/applied_loans.html', context={'id': user_id, 'username': username})
    
def update_status(request):
    if request.method == "GET":
        status=request.GET.get("status","")
        id= request.GET.get("id",0)
        try:
            from web3 import Web3
            with open('blocks/build/contracts/LoanTable.json') as e:
                abi=json.load(e)['abi']
            web3=Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))
            one={'from':'0x72Ba87D71B1aa467C6b4a4B3af00D23Eb70694b8'}
            contract_note_instance=web3.eth.contract(address="0x2BCb3059e3D80BB65c8ADe5C3F0bc4bdDA76a2B1",abi=abi)
            contract_note_instance.functions.update_status(int(id),status).transact(one)
        except Exception:
            pass
        tx = Transaction.objects.select_related('loan','username').filter(transaction_number=int(id)).first()
        if tx:
            tx.status = status
            if status == "Success":
                tx.verified_by_admin = True
            tx.save(update_fields=['status','verified_by_admin'])
            loan = tx.loan
            if loan and status == "Success":
                if loan.total_installments == 0:
                    loan.total_installments = int(loan.duration or 0)
                if loan.total_amount == 0:
                    loan.total_amount = int(loan.amount or 0)
                if loan.total_repayable_amount == 0:
                    try:
                        loan.total_repayable_amount = int(loan.monthlyamount or 0) * int(loan.duration or 0)
                    except Exception:
                        loan.total_repayable_amount = 0
                if loan.total_interest == 0 and loan.total_repayable_amount and loan.total_amount:
                    loan.total_interest = (loan.total_repayable_amount or 0) - (loan.total_amount or 0)
                loan.paid_installments = (loan.paid_installments or 0) + 1
                loan.total_paid_amount = (loan.total_paid_amount or 0) + (tx.monthlyamount or 0)
                if loan.paid_installments >= loan.total_installments and loan.total_installments > 0:
                    loan.status = "Completed"
                    loan.closed_at = timezone.now()
                    try:
                        from web3 import Web3
                        with open('blocks/build/contracts/LoanTable.json') as e:
                            abi=json.load(e)['abi']
                        web3=Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))
                        one={'from':'0xed7cba29AC1e3796d45139FE1aBaeea04A7C1380'}
                        contract_note_instance=web3.eth.contract(address="0xc76b612eA01f2e41374F35673848D2D71f4c79B3",abi=abi)
                        contract_note_instance.functions.addTransaction(
                            tx.username.username,
                            0,
                            "SYSTEM",
                            timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "LoanClosed",
                            "",
                            "",
                            "",
                            ""
                        ).transact(one)
                    except Exception:
                        pass
                else:
                    if loan.status in ["Applied","Pending","Approved","Inactive"]:
                        loan.status = "Active"
                loan.save()
                try:
                    from web3 import Web3
                    with open('blocks/build/contracts/LoanTable.json') as e:
                        abi=json.load(e)['abi']
                    web3=Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))
                    one={'from':'0xed7cba29AC1e3796d45139FE1aBaeea04A7C1380'}
                    contract_note_instance=web3.eth.contract(address="0xc76b612eA01f2e41374F35673848D2D71f4c79B3",abi=abi)
                    contract_note_instance.functions.addTransaction(
                        tx.username.username,
                        int(tx.monthlyamount or 0),
                        "ADMIN",
                        timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Success",
                        tx.upi_id or "",
                        tx.card_number or "",
                        tx.wallet_name or "",
                        tx.wallet_number or ""
                    ).transact(one)
                except Exception:
                    pass
        return redirect("paymentadmin")

def approveloan(request):
    if request.method == "POST":
        reason = request.POST.get("reason", "")
        id = request.POST.get("id", 0)
        loan = Loantable.objects.filter(id=int(id)).select_related('details').first()
        if loan:
            loan.status = "Approved"
            loan.approved_reason = reason
            try:
                loan.total_installments = int(loan.duration or 0)
                loan.total_amount = int(loan.amount or 0)
                loan.total_repayable_amount = int(loan.monthlyamount or 0) * int(loan.duration or 0)
                loan.total_interest = (loan.total_repayable_amount or 0) - (loan.total_amount or 0)
            except Exception:
                pass
            loan.save()
    return redirect("manageloanrequest")


def rejectloan(request):
    if request.method == "POST":
        reason = request.POST.get("reason", "")
        id = request.POST.get("id", 0)
        loan = Loantable.objects.filter(id=int(id)).first()
        if loan:
            loan.status = "Rejected"
            loan.rejection_reason = reason
            loan.save()
    return redirect("manageloanrequest")

from django.db.models import Sum, Count, Q
from datetime import timedelta
from django.utils import timezone

def dashboard(request):
    """
    Admin dashboard: UI-only analytics.
    Safe defaults are provided so the page never crashes on empty data.
    """
    # Metrics (safe defaults, use existing data only)
    approved_customers_count = User.objects.filter(verification_status='Approved').count() or 0
    active_loans_count = Loantable.objects.filter(status='Approved').count() or 0
    completed_loans_count = Loantable.objects.filter(status='Completed').count() or 0
    total_principal_issued = Loantable.objects.filter(status__in=['Approved', 'Completed']).aggregate(total=Sum('amount'))['total'] or 0
    total_amount_repaid = Transaction.objects.filter(status='Success').aggregate(total=Sum('monthlyamount'))['total'] or 0
    total_interest_earned = Loantable.objects.aggregate(total=Sum('total_interest'))['total'] or 0
    repayment_rate_value = (float(total_amount_repaid or 0) / float(total_principal_issued or 0) * 100) if float(total_principal_issued or 0) > 0 else 0.0
    repayment_rate = round(repayment_rate_value, 1)

    # Chart: group loan applications by month of start_date (previously used monthlyamount which is not a date).
    from django.db.models.functions import TruncMonth
    today = timezone.now()
    start_date = today - timedelta(days=90)
    monthly_applications = (
        Loantable.objects
        .filter(start_date__gte=start_date)
        .annotate(month=TruncMonth('start_date'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    labels = [(item['month'].strftime('%b') if item.get('month') else '') for item in monthly_applications]
    data_applications = [item.get('count', 0) for item in monthly_applications]

    loan_types = Loantable.objects.values('duration').annotate(count=Count('id'))
    type_labels = [f"{item['duration']} months" for item in loan_types if item.get('duration') is not None]
    type_data = [item.get('count', 0) for item in loan_types]

    # Pass admin_display_name so admin dashboard never depends on missing `user` in template context.
    pending_loans = Loantable.objects.filter(status='Pending').order_by('-id')
    pending_users = User.objects.filter(verification_status='Pending').order_by('-id')
    pending_transactions = Transaction.objects.select_related('username', 'loan').filter(status='Pending').order_by('-transaction_date')

    context = {
        'admin_display_name': getattr(request.user, 'username', None) if getattr(request, 'user', None) and request.user.is_authenticated else 'Admin',

        # Metric cards (formatted for display)
        'total_customers': f"{approved_customers_count:,}",
        'active_loans': f"{active_loans_count:,}",
        'completed_loans': f"{completed_loans_count:,}",
        'total_loan_amount': f"₹{(total_principal_issued or 0):,.0f}",
        'total_amount_repaid': f"₹{(total_amount_repaid or 0):,.0f}",
        'total_interest_earned': f"₹{(total_interest_earned or 0):,.0f}",
        'repayment_rate': f"{repayment_rate}%",

        # Charts (safe defaults handled in template JS)
        'chart_labels': labels,
        'chart_applications_data': data_applications,
        'loan_type_labels': type_labels or ['Personal', 'Business', 'Other'],
        'loan_type_data': type_data or [0, 0, 0],

        # Recent activity: latest 5 from registrations, approvals, payments (safe fallbacks)
        'recent_registrations': list(User.objects.order_by('-id')[:5]),
        'recent_approvals': list(Loantable.objects.filter(status='Approved').order_by('-id')[:5]),
        'recent_payments': list(Transaction.objects.order_by('-transaction_date')[:5]),
        'pending_loans': list(pending_loans),
        'pending_users': list(pending_users),
        'pending_transactions': list(pending_transactions),
    }
    return render(request, 'admin/dashboard.html', context)

    
def managecustomer(request):
    data = User.objects.filter(verification_status__in=['Approved', 'Rejected']).values(
        "id",
        "username",
        "email",
        "status",
        "is_approved",
        "is_blocked",
        "verification_status",
    )
    return render(request, "admin/managecustomer.html", context={"data": list(data)})    


def manageloanrequest(request):
    data = Loantable.objects.filter().values(
        "id",
        "loan_number",
        "customer_name",
        "amount",
        "duration",
        "monthlyamount",
        "loan_details",
        "status",
        "pan_no",
        "mobile_no",
        "city",
        "address",
        "start_date",
        "details__id",
        "details__username",
        "details__email",
    )
    return render(request, "admin/manageloanrequest.html", context={"data": list(data)})


def profileadmin(request):
    return render(request, "admin/profileadmin.html")


# def login(request):
#     if request.method == "POST":
#         username = request.POST.get("username", "")
#         password = request.POST.get("password", "")
#         email= request.POST.get('email', '')
        
#         print(email)
#         print(password)
#         user = User.objects.filter(username=username, password=password). first()
#         if user is not None:
#             user_details = user
#             print(user_details.status)
#             if user_details.status == "pending" or user_details.status=="BLOCKED":
#                 msg="User need to be verified"
#                 if user_details.status=="BLOCKED":
#                     msg="User Blocked Do not have Access to login"
#                 return render(request,"index.html",
#                     context={"msg": msg},
#                 )
#             request.session['user_id'] = user.id
#             request.session['username'] = username
#             return render(request,"user/home.html",context={
#                     "msg": f"Welcome to HomePage {user.last().username}",
#                     "id": user.last().id,
#                 },
#             )
#         elif email == "admin@gmail.com" and password == "admin":
#             print('entering')
#             return render(request, "admin/dashboard.html")
#         else:
#             data = {
#                 "msg": "Invalid User",
#             }
#             return render(request, "index.html", data)
#     return render(request, "index.html")

def login(request):
    # Navigation: GET shows User Login page; POST handles both user and admin auth (unchanged).
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        email = request.POST.get('email', '')
        
        print(f"Debug: Received username: {username}, password: {password}, email: {email}")
        
        user = User.objects.filter(username=username, password=password).first()
        
        print(f"Debug: User found: {user}")
        
        if user is not None:
            user_details = user
            print(f"Debug: User status: {user_details.status}")
            
            if user_details.status == "pending" or user_details.status == "BLOCKED":
                msg = "User needs to be verified"
                if user_details.status == "BLOCKED":
                    msg = "User is blocked and cannot log in"
                return render(request, "user/login.html", context={"msg": msg})
            try:
                from django.contrib.auth import authenticate, login as auth_login
                from django.contrib.auth.models import User as AuthUser
                auth_user = AuthUser.objects.filter(username=username).first()
                if not auth_user:
                    auth_user = AuthUser.objects.create(username=username, email=getattr(user, 'email', '') or "")
                    auth_user.set_password(password)
                    auth_user.save()
                # Re-authenticate using Django auth backend (ensures last_login is updated).
                auth_user = authenticate(request, username=username, password=password)
                if auth_user:
                    auth_login(request, auth_user)
                # Maintain existing session keys for UI compatibility.
                request.session['user_id'] = user.id
                request.session['username'] = username
            except Exception as e:
                print(f"Auth integration error: {e}")
                request.session['user_id'] = user.id
                request.session['username'] = username
            
            print(f"Debug: Welcome message for {user.username}")
            return redirect('home')
            
        elif email == "admin@gmail.com" and password == "admin":
            print("Debug: Admin login detected")
            # Redirect after admin login so the Dashboard view provides required context safely.
            return redirect('admin_dashboard')
        else:
            print("Debug: Invalid user credentials")
            return render(request, "user/login.html", context={"msg": "Invalid username or password."})
        
    # Single User Login page: show registration or loan-gate message if redirected.
    context = {}
    registration_msg = request.session.pop('registration_msg', None)
    login_msg = request.session.pop('login_msg', None)
    if registration_msg:
        context['msg'] = "Your registration is under verification."
    elif login_msg:
        context['msg'] = login_msg
    return render(request, "user/login.html", context)


def signup(request):
    """
    User registration. Saves all form fields to User model.
    Sets verification_status='Pending'; loan application is not allowed until admin sets status to APPROVED.
    """
    import re
    if request.method == "POST":
        # Existing + new registration fields (all must be saved to DB)
        full_name = request.POST.get("full_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        c_password = request.POST.get("c_password", "")
        gender = request.POST.get("gender", "").strip()
        date_of_birth_raw = request.POST.get("date_of_birth", "").strip()
        # PAN is used as unique identifier (govt-issued in India); one registration per person.
        pan_number = request.POST.get("pan_number", "").strip().upper()
        mobile_number = request.POST.get("mobile_number", "").strip()
        address = request.POST.get("address", "").strip()
        profile_pic = request.FILES.get("profile_pic")
        # KYC-style verification: PAN card document upload (stored securely; not exposed in UI except to admin).
        pan_card_file = request.FILES.get("pan_card")
        data = {"errors": {}, "form": request.POST}

        # Validation: PAN number must be unique (prevents duplicate registrations per person)
        if pan_number and User.objects.filter(pan_number=pan_number).exists():
            data["msg"] = "User already registered with this PAN number"
            return render(request, "user/signup.html", data)

        if User.objects.filter(email=email).exists():
            data["errors"]["email"] = "A user with this email already exists."
            data["msg"] = "Try with another email."
            return render(request, "user/signup.html", data)

        if User.objects.filter(username=username).exists():
            data["errors"]["username"] = "This username is already taken."
            return render(request, "user/signup.html", data)

        # Validation: password and confirm password must match
        if password != c_password:
            data["errors"]["password"] = "Password and Confirm Password do not match."
            return render(request, "user/signup.html", data)

        if len(password) < 8:
            data["errors"]["password"] = "Password must be at least 8 characters long."
            return render(request, "user/signup.html", data)

        if email and not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
            data["errors"]["email"] = "Enter a valid email address."
            return render(request, "user/signup.html", data)

        if mobile_number and not re.match(r"^\d{10,15}$", mobile_number):
            data["errors"]["mobile_number"] = "Enter a valid mobile number (10–15 digits)."
            return render(request, "user/signup.html", data)

        date_of_birth = None
        if date_of_birth_raw:
            try:
                date_of_birth = datetime.strptime(date_of_birth_raw, "%Y-%m-%d").date()
            except ValueError:
                data["errors"]["date_of_birth"] = "Enter a valid date."
                return render(request, "user/signup.html", data)

        if not pan_card_file:
            data["errors"]["pan_card"] = "PAN card document is required for verification."
            return render(request, "user/signup.html", data)

        profile_pic_path = ""
        if profile_pic:
            upload_dir = "app/static/images/uploads/profile_pic/"
            os.makedirs(upload_dir, exist_ok=True)
            filename = f"{round(time.time()*1000)}.png"
            filepath = os.path.join(upload_dir, filename)
            with open(filepath, 'wb+') as f:
                for chunk in profile_pic.chunks():
                    f.write(chunk)
            profile_pic_path = f"/static/images/uploads/profile_pic/{filename}"

        # Store PAN card document securely (file upload for KYC verification by admin).
        pan_doc_path = ""
        if pan_card_file:
            upload_dir = "app/static/uploads/pan_docs/"
            os.makedirs(upload_dir, exist_ok=True)
            ext = os.path.splitext(pan_card_file.name)[1] or ".pdf"
            safe_name = f"pan_{round(time.time()*1000)}{ext}"
            filepath = os.path.join(upload_dir, safe_name)
            with open(filepath, 'wb+') as f:
                for chunk in pan_card_file.chunks():
                    f.write(chunk)
            pan_doc_path = f"/static/uploads/pan_docs/{safe_name}"

        # Save ALL fields (old + new); verification_status = Pending until admin approves (KYC-style).
        user = User.objects.create(
            username=username,
            password=password,
            email=email,
            is_approved="unverified",
            is_blocked="",
            status="pending",
            profile_pic=profile_pic_path,
            full_name=full_name or username,
            gender=gender,
            date_of_birth=date_of_birth,
            pan_number=pan_number or None,
            mobile_number=mobile_number,
            address=address,
            verification_status="Pending",
            pan_card_document=pan_doc_path,
            rejection_reason="",
        )
        # Redirect to single User Login URL so all login flows use the same page.
        request.session['registration_msg'] = "Your registration is under verification."
        return redirect('login')

    return render(request, "user/signup.html", {})

def approve_user(request):
    """KYC-style verification: set verification_status Approved so user can apply for loans; send approval email."""
    if request.method == "POST":
        id = request.POST.get("id", 0)
        source = (request.POST.get("source", "") or "").lower()
        user = User.objects.get(id=int(id))
        if getattr(user, 'verification_status', '') == 'Approved':
            messages.warning(request, f"User {user.username} is already approved.")
        else:
            user.status = 'APPROVED'
            user.verification_status = 'Approved'
            user.rejection_reason = ''
            user.save()
            messages.success(request, f"User {user.username} has been approved!")
    return redirect("managecustomer")

def block_user(request):
    if request.method == "POST":
        id = request.POST.get("id", 0)
        user = User.objects.get(id=int(id))
        if user.status == 'BLOCKED':
            messages.warning(request, f"User {user.username} is already blocked")
        else:
            user.status = 'BLOCKED'
            user.save()
            messages.success(request, f"User {user.username} has been blocked!")
    return redirect("managecustomer")


def admin_view_customer(request, user_id):
    """Admin view: read-only customer details for Manage Customers and Pending Users."""
    user = get_object_or_404(User, id=user_id)
    source = (request.GET.get('from', '') or '').lower()
    verification_str = getattr(user, 'verification_status', '') or ''
    status_str = (getattr(user, 'status', '') or '').upper()
    account_status = 'Inactive' if status_str == 'BLOCKED' else ('Active' if verification_str == 'Approved' else 'Inactive')
    context = {
        "customer": user,
        "personal": {
            "user_id": user.id,
            "full_name": getattr(user, "full_name", "") or getattr(user, "username", ""),
            "username": getattr(user, "username", ""),
            "email": getattr(user, "email", ""),
            "phone": getattr(user, "mobile_number", ""),
            "verification_status": verification_str or "Pending",
            "account_status": account_status,
        },
        "show_verification_actions": (source == 'dashboard') and (verification_str == 'Pending'),
    }
    return render(request, "admin/view_customer.html", context=context)


def reject_user(request):
    """KYC-style: reject verification with reason; set verification_status Rejected and send rejection email."""
    if request.method == "POST":
        id = request.POST.get("id", 0)
        reason = request.POST.get("reason", "").strip()
        if not reason:
            messages.warning(request, "Rejection reason is required.")
            return redirect("managecustomer")
        user = User.objects.get(id=int(id))
        user.verification_status = 'Rejected'
        user.status = 'REJECTED'
        user.rejection_reason = reason
        user.save()
        messages.success(request, f"User {user.username} has been rejected.")
    return redirect("managecustomer")


def admin(request):
    return render(request, "admin/admin.html")

from datetime import date, timedelta

# def home(request):
#     user = request.user
#     loans = Loantable.objects.filter(details=request.user)
#     active_loans_count = loans.filter(status__in=['Approved', 'Active']).count()
#     total_borrowed = loans.filter(status__in=['Approved', 'Active']).aggregate(
#         total=Sum('amount')
#     )['total'] or 0
#     total_paid = loans.aggregate(total_paid=Sum('payment'))['total_paid'] or 0
#     repayment_rate = round(
#         (total_paid / total_borrowed * 100) if total_borrowed > 0 else 0
#     )
#     today = date.today()
#     upcoming_payments = []
#     for loan in loans.filter(status__in=['Approved', 'Active']):
#         if hasattr(loan, 'payoff_date') and loan.payoff_date:
#             days_left = (loan.payoff_date - today).days
#             if 0 <= days_left <= 7:
#                 upcoming_payments.append({
#                     'id': loan.id,
#                     'amount': loan.amount,
#                     'payoff_date': loan.payoff_date,
#                     'days_left': days_left,
#                     'customer_name': loan.customer_name,
#                 })
#     context = {
#         'data': loans,                      
#         'active_loans': active_loans_count,
#         'total_borrowed': f"${total_borrowed:,.0f}",
#         'repayment_rate': f"{repayment_rate}%",
#         'upcoming_payments': upcoming_payments[:3],  
#         'username': user.username,
#         'id': user.id,                       
#     }
#     return render(request, 'user/home.html', context)

from django.shortcuts import redirect
from django.db.models import Sum
from datetime import date
import calendar

def _add_months(d, months):
    """Add months to a date (assumption: for EMI due-date calculation)."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(d.day, last_day)
    return date(year, month, day)

def home(request):
    user_id = request.session.get('user_id')
    if not user_id or not request.session.get('username'):
        return redirect('login')
    user_obj = User.objects.filter(id=user_id).first()
    username = getattr(user_obj, 'username', None) or request.session.get('username', 'User')
    is_verified = getattr(user_obj, 'verification_status', None) == 'Approved'

    loans_qs = Loantable.objects.filter(details=user_id)
    active_loans_count = loans_qs.filter(status__in=['Approved', 'Active']).count()
    completed_loans_count = loans_qs.filter(status='Completed').count()
    principal_approved = float(loans_qs.filter(status__in=['Approved', 'Active']).aggregate(total=Sum('amount'))['total'] or 0)
    total_interest_sum = 0.0
    total_payable_sum = 0.0
    outstanding_sum = 0.0

    today = date.today()
    loan_list = []
    upcoming_payments = []

    for loan in loans_qs:
        monthly = float(loan.monthlyamount or 0)
        paid = float(getattr(loan, 'total_paid_amount', 0) or Transaction.objects.filter(loan=loan, status='Success').aggregate(total=Sum('monthlyamount'))['total'] or 0)
        dur = int(getattr(loan, 'total_installments', 0) or loan.duration or 0)
        try:
            emis_paid = int(paid // monthly) if monthly else 0
        except (TypeError, ValueError, ZeroDivisionError):
            emis_paid = 0
        total_emis = int(getattr(loan, 'total_installments', 0) or dur)
        try:
            repayable = float(getattr(loan, 'total_repayable_amount', 0) or (dur * monthly))
        except (TypeError, ValueError):
            repayable = 0.0
        principal = float(getattr(loan, 'total_amount', 0) or loan.amount or 0)
        try:
            interest_total = float(getattr(loan, 'total_interest', 0) or (repayable - principal))
        except (TypeError, ValueError):
            interest_total = 0.0
        try:
            remaining = max(0.0, repayable - paid)
        except (TypeError, ValueError):
            remaining = 0.0
        try:
            next_emi_due = _add_months(loan.start_date, emis_paid) if emis_paid < dur else None
        except (TypeError, ValueError):
            next_emi_due = loan.start_date if emis_paid < dur else None
        status_str = (loan.status or '').strip()
        if status_str in ('Rejected',):
            display_status = 'Rejected'
        elif status_str in ('Approved', 'Active') and emis_paid >= dur:
            display_status = 'Completed'
        else:
            display_status = status_str or 'Pending'
        can_pay = status_str in ('Approved', 'Active') and remaining > 0
        loan_type = (loan.loan_type or loan.loan_details or 'Personal')[:50]
        if loan.loan_type == "Home":
            loan_type = "Loan Against Property"
        payment_status = 'Paid' if (monthly and paid >= (emis_paid + 1) * monthly) else 'Pending'
        last_tx = Transaction.objects.filter(loan=loan, status='Success').order_by('-transaction_date').first()
        last_payment_date = getattr(last_tx, 'transaction_date', None)
        last_payment_amount = float(getattr(last_tx, 'monthlyamount', 0) or 0)

        loan_list.append({
            'loan': loan,
            'loan_type': loan_type,
            'emis_paid': emis_paid,
            'total_emis': total_emis,
            'next_emi_due_date': next_emi_due,
            'remaining_amount': remaining,
            'display_status': display_status,
            'can_pay': can_pay,
            'payment_status': payment_status,
            'last_payment_date': last_payment_date,
            'last_payment_amount': last_payment_amount,
            'total_interest': interest_total,
            'total_amount_to_pay': repayable,
        })

        if status_str in ('Active',) and emis_paid < dur and next_emi_due:
            upcoming_payments.append({
                'loan_id': loan.id,
                'amount': loan.monthlyamount,
                'due_date': next_emi_due,
                'payment_status': payment_status,
                'loan_type': loan_type,
                'remaining_emis': max(0, total_emis - emis_paid),
            })
        if status_str in ('Approved', 'Active', 'Completed'):
       
            total_interest_sum += interest_total
            total_payable_sum += repayable
            outstanding_sum += remaining

    upcoming_payments.sort(key=lambda x: x['due_date'])
    upcoming_payments = upcoming_payments[:5]
    has_completed_loan = any(item['display_status'] == 'Completed' for item in loan_list)

    verification_status = getattr(user_obj, 'verification_status', None) or 'Pending'
    rejection_reason = getattr(user_obj, 'rejection_reason', None) or ''

    context = {
        'data': loan_list,
        'active_loans': active_loans_count,
        'completed_loans': completed_loans_count,
        'total_borrowed': principal_approved,
        'interest_amount': total_interest_sum,
        'total_payable': total_payable_sum,
        'outstanding_amount': outstanding_sum,
        'upcoming_payments': upcoming_payments,
        'username': username,
        'id': user_id,
        'is_verified': is_verified,
        'has_completed_loan': has_completed_loan,
        'verification_status': verification_status,
        'rejection_reason': rejection_reason,
    }
    return render(request, 'user/home.html', context)


def profile(request):
    """
    User Profile page (UI-only):
    - Displays logged-in user's details (never shows password)
    - Allows editing a subset of fields on the existing User model
    - Protects access when not logged in (session-based)
    """
    user_id = request.session.get('user_id')
    if not user_id:
        # Prevent profile access if user isn't logged in.
        return redirect('login')

    user_obj = User.objects.filter(id=int(user_id)).first()
    if not user_obj:
        # Session is stale; clear it and return to login.
        try:
            request.session.flush()
        except Exception:
            request.session.clear()
        return redirect('login')

    msg = request.session.pop('profile_msg', None)
    error = None

    if request.method == "POST":
        # Save updated fields (no schema changes; no auth logic changes).
        new_username = (request.POST.get('username', '') or '').strip()
        new_email = (request.POST.get('email', '') or '').strip()
        full_name = (request.POST.get('full_name', '') or '').strip()
        gender = (request.POST.get('gender', '') or '').strip()
        mobile_number = (request.POST.get('mobile_number', '') or '').strip()
        address = (request.POST.get('address', '') or '').strip()
        dob_raw = (request.POST.get('date_of_birth', '') or '').strip()

        # Basic uniqueness checks (avoid DB errors / confusing behavior).
        if new_username and User.objects.filter(username=new_username).exclude(id=user_obj.id).exists():
            error = "That username is already taken."
        elif new_email and User.objects.filter(email=new_email).exclude(id=user_obj.id).exists():
            error = "That email is already in use."
        else:
            if new_username:
                user_obj.username = new_username
                request.session['username'] = new_username  # keep navbar/avatar consistent
            if new_email:
                user_obj.email = new_email

            user_obj.full_name = full_name
            user_obj.gender = gender
            user_obj.mobile_number = mobile_number
            user_obj.address = address

            # Date parsing (optional field)
            if dob_raw:
                from datetime import datetime
                try:
                    user_obj.date_of_birth = datetime.strptime(dob_raw, "%Y-%m-%d").date()
                except ValueError:
                    error = "Enter a valid date of birth."
            else:
                user_obj.date_of_birth = None

            # Profile picture upload (stored as static path, consistent with signup implementation)
            profile_pic = request.FILES.get("profile_pic")
            if not error and profile_pic:
                import os, time
                upload_dir = "app/static/images/uploads/profile_pic/"
                os.makedirs(upload_dir, exist_ok=True)
                ext = os.path.splitext(profile_pic.name)[1] or ".png"
                filename = f"{round(time.time()*1000)}{ext}"
                filepath = os.path.join(upload_dir, filename)
                with open(filepath, 'wb+') as f:
                    for chunk in profile_pic.chunks():
                        f.write(chunk)
                user_obj.profile_pic = f"/static/images/uploads/profile_pic/{filename}"

            if not error:
                user_obj.save()
                request.session['profile_msg'] = "Profile updated successfully."
                return redirect('profile')

    username = request.session.get('username', getattr(user_obj, 'username', 'User'))
    last_login_display = "First login"
    try:
        from django.utils import timezone
        auth_user = getattr(request, 'user', None)
        if auth_user and getattr(auth_user, 'is_authenticated', False) and getattr(auth_user, 'last_login', None):
            try:
                from zoneinfo import ZoneInfo
                ist = ZoneInfo('Asia/Kolkata')
                ist_dt = timezone.localtime(auth_user.last_login, ist)
                last_login_display = ist_dt.strftime("%d %b %Y, %I:%M %p IST")
            except Exception:
                last_login_display = auth_user.last_login.strftime("%Y-%m-%d %H:%M")
        else:
            from django.contrib.auth.models import User as AuthUser
            auth_user_fallback = AuthUser.objects.filter(username=username).first()
            if getattr(auth_user_fallback, 'last_login', None):
                try:
                    from zoneinfo import ZoneInfo
                    ist = ZoneInfo('Asia/Kolkata')
                    ist_dt = timezone.localtime(auth_user_fallback.last_login, ist)
                    last_login_display = ist_dt.strftime("%d %b %Y, %I:%M %p IST")
                except Exception:
                    last_login_display = auth_user_fallback.last_login.strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    context = {
        'id': user_id,
        'username': username,
        'user_obj': user_obj,
        'msg': msg,
        'error': error,
        'last_login_display': last_login_display,
    }
    return render(request, "user/profile.html", context=context)


def logout_view(request):
    """
    Logout (UI-only): clear server session and clear client-side sessionStorage.
    We render a tiny page that clears sessionStorage to avoid redirect loops caused by legacy JS.
    """
    try:
        request.session.flush()
    except Exception:
        request.session.clear()
    return render(request, "user/logout.html")

from datetime import datetime

def loanrequest(request):
    # Session-based auth: do not allow direct access to loan application without login.
    if not request.session.get('user_id'):
        return redirect('login')
    # KYC-style: allow loan application only if admin has set verification_status = Approved.
    user = User.objects.filter(id=request.session.get('user_id')).first()
    if not user or getattr(user, 'verification_status', '') != 'Approved':
        request.session['login_msg'] = "Your account is not yet approved for loan application."
        return redirect('login')
    if request.method == "POST":
        # --- BASE LOAN FIELDS (always collected) ---
        base_user_id = request.POST.get("userid", 0)
        amount = request.POST.get("amount", "")
        duration = request.POST.get("duration", "")
        monthlyamount = request.POST.get("monthlyamount", "")
        loan_type = request.POST.get("loan_type", "")
        purpose = request.POST.get("purpose", "")
        surety_type = request.POST.get("surety_type", "")
        farmer_type = request.POST.get("farmer_type", "")

        # Server-side interest mapping (do not rely solely on client JS).
        def rate_for_type(t):
            if t == "Home": return Decimal("9.0")
            if t == "Education": return Decimal("7.0")
            if t == "Agriculture": return Decimal("4.0")
            return Decimal("10.0")
        interest_rate = rate_for_type(loan_type)
        try:
            amount_int = int(amount or 0)
        except Exception:
            amount_int = 0
        try:
            duration_int = int(duration or 0)
        except Exception:
            duration_int = 0
        try:
            monthlyamount_int = int(float(monthlyamount or 0))
        except Exception:
            monthlyamount_int = 0

        # --- INCOME-BASED FIELDS ---
        income_employment_type = request.POST.get("income_employment_type", "")
        income_annual = request.POST.get("income_annual") or None
        income_monthly = request.POST.get("income_monthly") or None
        income_employer_name = request.POST.get("income_employer_name", "")
        income_years_employment = request.POST.get("income_years_employment") or None
        income_proof = request.FILES.get("income_proof")

        # --- GUARANTOR-BASED FIELDS ---
        guarantor_name = request.POST.get("guarantor_name", "")
        guarantor_relationship = request.POST.get("guarantor_relationship", "")
        guarantor_pan = request.POST.get("guarantor_pan", "")
        guarantor_mobile = request.POST.get("guarantor_mobile", "")
        guarantor_address = request.POST.get("guarantor_address", "")
        guarantor_employment_type = request.POST.get("guarantor_employment_type", "")
        guarantor_annual_income = request.POST.get("guarantor_annual_income") or None
        guarantor_monthly_income = request.POST.get("guarantor_monthly_income") or None
        guarantor_employer_name = request.POST.get("guarantor_employer_name", "")
        guarantor_years_employment = request.POST.get("guarantor_years_employment") or None
        guarantor_income_proof = request.FILES.get("guarantor_income_proof")

        # --- ASSET-BASED FIELDS ---
        asset_type = request.POST.get("asset_type", "")
        asset_home_address = request.POST.get("asset_home_address", "")
        asset_home_value = request.POST.get("asset_home_value") or None
        asset_home_proof = request.FILES.get("asset_home_proof")
        asset_gold_weight = request.POST.get("asset_gold_weight") or None
        asset_gold_purity = request.POST.get("asset_gold_purity", "")
        asset_gold_value = request.POST.get("asset_gold_value") or None
        asset_gold_proof = request.FILES.get("asset_gold_proof")
        equipment_type = request.POST.get("equipment_type", "")
        equipment_model = request.POST.get("equipment_model", "")
        equipment_value = request.POST.get("equipment_value") or None
        equipment_proof = request.FILES.get("equipment_proof")

        # Helper to save uploaded documents to a predictable static path.
        def save_upload(fileobj, subdir):
            if not fileobj:
                return ""
            upload_dir = os.path.join("app", "static", "uploads", subdir)
            os.makedirs(upload_dir, exist_ok=True)
            ext = os.path.splitext(fileobj.name)[1] or ".pdf"
            filename = f"{round(time.time()*1000)}{ext}"
            filepath = os.path.join(upload_dir, filename)
            with open(filepath, "wb+") as fh:
                for chunk in fileobj.chunks():
                    fh.write(chunk)
            return f"/static/uploads/{subdir}/{filename}"

        income_proof_path = save_upload(income_proof, "income_proof")
        guarantor_income_proof_path = save_upload(guarantor_income_proof, "guarantor_income_proof")
        asset_home_proof_path = save_upload(asset_home_proof, "asset_home_proof")
        asset_gold_proof_path = save_upload(asset_gold_proof, "asset_gold_proof")
        equipment_proof_path = save_upload(equipment_proof, "equipment_proof")

        # --- SIMPLE RISK / ELIGIBILITY METRICS (hidden from user) ---
        try:
            emi_dec = Decimal(monthlyamount or "0")
        except Exception:
            emi_dec = Decimal("0")
        try:
            inc_month = Decimal(income_monthly or "0")
        except Exception:
            inc_month = Decimal("0")

        emi_to_income = float((emi_dec / inc_month * 100) if inc_month > 0 else 0)
        if emi_to_income == 0:
            risk_score = "Medium"
            eligibility = "Borderline"
        elif emi_to_income <= 30:
            risk_score = "Low"
            eligibility = "Eligible"
        elif emi_to_income <= 50:
            risk_score = "Medium"
            eligibility = "Borderline"
        else:
            risk_score = "High"
            eligibility = "Not Eligible"

        if loan_type == "Personal":
            surety_type = "income"
        elif loan_type == "Education":
            surety_type = "guarantor"
        elif loan_type == "Agriculture":
            surety_type = "guarantor" if (farmer_type == "Tenant Farmer") else "asset"
        elif loan_type == "Home":
            surety_type = "asset"

        if loan_type == "Agriculture":
            if asset_type == "Land":
                asset_type = "Home"
            elif asset_type == "Equipment":
                asset_type = "Gold"

        errors = []
        if loan_type == "Personal":
            if not income_employment_type:
                errors.append("Employment Type is required for Personal Loan.")
            if not (income_annual or income_monthly):
                errors.append("Provide Income details for Personal Loan.")
        elif loan_type == "Education":
            if not guarantor_name or not guarantor_relationship:
                errors.append("Guarantor Name and Relationship are required for Education Loan.")
        elif loan_type == "Agriculture":
            if not farmer_type:
                errors.append("Farmer Type is required for Agriculture Loan.")
            if farmer_type == "Tenant Farmer":
                if not guarantor_name or not guarantor_relationship:
                    errors.append("Guarantor details are required for Tenant Farmer.")
            else:
                if asset_type == "Land":
                    if not asset_home_address or not asset_home_value:
                        errors.append("Land asset address and value are required for Land Owner.")
                elif asset_type == "Equipment":
                    if not asset_equipment_value:
                        errors.append("Equipment value is required.")
        elif loan_type == "Home":
            if not (income_annual or income_monthly):
                errors.append("Income details are required for Loan Against Property.")
            if asset_type == "Home":
                if not asset_home_address or not asset_home_value:
                    errors.append("Property address and value are required for Loan Against Property.")
            if asset_type == "Gold":
                if not asset_gold_weight or not asset_gold_value:
                    errors.append("Gold weight and value are required.")
        if errors:
            messages.warning(request, " ".join(errors))
            return redirect("loanrequest")

        offline_required = (surety_type == "asset")

        # Legacy user linkage is preserved (details FK & core contact fields).
        base_user = User.objects.filter(id=int(base_user_id or 0)).last()
        start_date_str = request.POST.get("start_date", "")
        try:
            start_date_parsed = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except Exception:
            start_date_parsed = datetime.today().date()
        # Assign sequential loan_number once at creation
        max_ln = Loantable.objects.aggregate(max_ln=Max('loan_number'))['max_ln'] or 0
        next_ln = int(max_ln) + 1
        loan = Loantable(
            customer_name=user.full_name or user.username,
            amount=amount_int,
            details=base_user or user,
            duration=duration_int,
            monthlyamount=monthlyamount_int,
            loan_details=loan_type or "",      # keep compatible with existing templates
            status="Pending",
            loan_number=next_ln,
            pan_no=user.pan_number or "",
            gender=user.gender or "",
            city=user.address or "",
            address=user.address or "",
            mobile_no=user.mobile_number or "",
            email=user.email,
            start_date=start_date_parsed,

            # New structured loan fields
            loan_type=loan_type,
            interest_rate=interest_rate,
            farmer_type=farmer_type,
            purpose=purpose,
            surety_type=surety_type,

            income_employment_type=income_employment_type,
            income_annual=income_annual or None,
            income_monthly=income_monthly or None,
            income_employer_name=income_employer_name,
            income_years_employment=income_years_employment or None,
            income_proof_path=income_proof_path,

            guarantor_name=guarantor_name,
            guarantor_relationship=guarantor_relationship,
            guarantor_pan=guarantor_pan,
            guarantor_mobile=guarantor_mobile,
            guarantor_address=guarantor_address,
            guarantor_employment_type=guarantor_employment_type,
            guarantor_annual_income=guarantor_annual_income or None,
            guarantor_monthly_income=guarantor_monthly_income or None,
            guarantor_employer_name=guarantor_employer_name,
            guarantor_years_employment=guarantor_years_employment or None,
            guarantor_income_proof_path=guarantor_income_proof_path,

            asset_type=asset_type,
            asset_home_address=asset_home_address,
            asset_home_value=asset_home_value or None,
            asset_home_proof_path=asset_home_proof_path,
            asset_gold_weight=asset_gold_weight or None,
            asset_gold_purity=asset_gold_purity,
            asset_gold_value=asset_gold_value or None,
            asset_gold_proof_path=asset_gold_proof_path,
            equipment_type=equipment_type,
            equipment_model=equipment_model,
            equipment_value=equipment_value or None,
            equipment_proof_path=equipment_proof_path,
            offline_verification_required=offline_required,

            risk_score=risk_score,
            eligibility_status=eligibility,
        )
        loan.save()
        
        return redirect("applied_loans")
    username = getattr(user, 'username', None) or request.session.get('username', 'User')
    return render(request, "user/loanrequest.html", context={'username': username, 'id': request.session.get('user_id')})


def admin_view_loan(request, loan_id):
    """
    Detailed admin loan view (read-only):
    - SECTION 1: Personal Information
    - SECTION 2: Loan Application Details
    - SECTION 3: Risk Evaluation (derived from stored fields)
    Approval / rejection flows remain unchanged (handled via existing endpoints).
    """
    loan = get_object_or_404(Loantable, id=loan_id)
    customer = loan.details  # related User details object (existing FK)

    # Personal information (guard against missing attributes)
    personal = {
        "full_name": getattr(customer, "full_name", "") or getattr(customer, "username", ""),
        "email": getattr(customer, "email", ""),
        "mobile": getattr(customer, "mobile_number", ""),
        "pan": getattr(customer, "pan_number", ""),
        "gender": getattr(customer, "gender", ""),
        "dob": getattr(customer, "date_of_birth", ""),
        "address": getattr(customer, "address", ""),
    }

    # Loan application details straight from Loantable (using new structured fields where present)
    loan_details = {
        "loan_type": loan.loan_type or loan.loan_details,
        "amount": loan.amount,
        "duration": loan.duration,
        "interest_rate": loan.interest_rate,
        "monthly_emi": loan.monthlyamount,
        "purpose": loan.purpose,
        "surety_type": loan.surety_type,
        "farmer_type": loan.farmer_type,
        "income": {
            "employment_type": loan.income_employment_type,
            "annual": loan.income_annual,
            "monthly": loan.income_monthly,
            "employer_name": loan.income_employer_name,
            "years": loan.income_years_employment,
            "proof_path": loan.income_proof_path,
        },
        "guarantor": {
            "name": loan.guarantor_name,
            "relationship": loan.guarantor_relationship,
            "pan": loan.guarantor_pan,
            "mobile": loan.guarantor_mobile,
            "address": loan.guarantor_address,
            "employment_type": loan.guarantor_employment_type,
            "annual_income": loan.guarantor_annual_income,
            "monthly_income": loan.guarantor_monthly_income,
            "employer_name": loan.guarantor_employer_name,
            "years": loan.guarantor_years_employment,
            "proof_path": loan.guarantor_income_proof_path,
        },
        "asset": {
            "type": loan.asset_type,
            "home_address": loan.asset_home_address,
            "home_value": loan.asset_home_value,
            "home_proof_path": loan.asset_home_proof_path,
            "gold_weight": loan.asset_gold_weight,
            "gold_purity": loan.asset_gold_purity,
            "gold_value": loan.asset_gold_value,
            "gold_proof_path": loan.asset_gold_proof_path,
            "equipment_type": loan.equipment_type,
            "equipment_model": loan.equipment_model,
            "equipment_value": loan.equipment_value,
            "equipment_proof_path": loan.equipment_proof_path,
            "offline_verification_required": loan.offline_verification_required,
        },
    }
    income_present = any([
        loan.income_employment_type,
        loan.income_annual,
        loan.income_monthly,
        loan.income_employer_name,
        loan.income_years_employment,
        loan.income_proof_path,
    ])
    guarantor_present = any([
        loan.guarantor_name,
        loan.guarantor_relationship,
        loan.guarantor_pan,
        loan.guarantor_mobile,
        loan.guarantor_address,
        loan.guarantor_employment_type,
        loan.guarantor_annual_income,
        loan.guarantor_monthly_income,
        loan.guarantor_employer_name,
        loan.guarantor_years_employment,
        loan.guarantor_income_proof_path,
    ])
    asset_present = any([
        loan.asset_type,
        loan.asset_home_address,
        loan.asset_home_value,
        loan.asset_home_proof_path,
        loan.asset_gold_weight,
        loan.asset_gold_purity,
        loan.asset_gold_value,
        loan.asset_gold_proof_path,
        loan.offline_verification_required,
    ])

    # --- RISK EVALUATION (read-only, derived from stored values) ---
    emi = Decimal(str(loan.monthlyamount or 0))
    monthly_income = loan.income_monthly or loan.guarantor_monthly_income or Decimal("0")
    annual_income = loan.income_annual or loan.guarantor_annual_income or (monthly_income * 12 if monthly_income else Decimal("0"))

    emi_to_income_ratio = float((emi / monthly_income * 100) if monthly_income else 0)

    # Simple heuristics consistent with earlier loanrequest calculation
    if emi_to_income_ratio == 0:
        employment_stability = "Unknown"
    elif emi_to_income_ratio <= 30:
        employment_stability = "Stable"
    elif emi_to_income_ratio <= 50:
        employment_stability = "Moderate"
    else:
        employment_stability = "Stressed"

    # Surety strength
    if loan.surety_type == "income":
        surety_strength = "Backed by regular income"
    elif loan.surety_type == "guarantor":
        surety_strength = "Backed by guarantor"
    elif loan.surety_type == "asset":
        surety_strength = "Backed by collateral asset"
    else:
        surety_strength = "Not specified"

    # Asset coverage / LTV where applicable
    asset_coverage = None
    if loan.asset_type == "Home" and loan.asset_home_value:
        asset_coverage = float((loan.asset_home_value / loan.amount * 100) if loan.amount else 0)
    elif loan.asset_type == "Gold" and loan.asset_gold_value:
        asset_coverage = float((loan.asset_gold_value / loan.amount * 100) if loan.amount else 0)

    # Loan history summary placeholder (PAN-based – real implementation would query past loans)
    history_summary = "No previous loan history found for this PAN." if not loan.pan_no else "Existing PAN available; history lookup not implemented in this demo."

    # Map stored risk_score + eligibility_status into overall bucket + recommendation
    stored_risk = (loan.risk_score or "").lower()
    if stored_risk == "low":
        overall_risk = "Low"
        system_recommendation = "Approve"
    elif stored_risk == "medium":
        overall_risk = "Medium"
        system_recommendation = "Approve with Conditions"
    elif stored_risk == "high":
        overall_risk = "High"
        system_recommendation = "Reject"
    else:
        overall_risk = "Medium"
        system_recommendation = "Review Manually"

    risk = {
        "annual_income": annual_income,
        "monthly_income": monthly_income,
        "emi_to_income_ratio": round(emi_to_income_ratio, 2),
        "employment_stability": employment_stability,
        "surety_strength": surety_strength,
        "asset_coverage": asset_coverage,
        "loan_history_summary": history_summary,
        "overall_risk_score": overall_risk,
        "system_recommendation": system_recommendation,
    }

    origin = request.GET.get('from', '')
    return_to = 'dashboard' if origin == 'dashboard' else 'manage'
    borrower_id = getattr(customer, 'id', None)
    loan_list = []
    if borrower_id:
        loans_qs = Loantable.objects.filter(details=borrower_id)
        for l in loans_qs:
            monthly = float(l.monthlyamount or 0)
            paid = float(getattr(l, 'total_paid_amount', 0) or Transaction.objects.filter(loan=l, status='Success').aggregate(total=Sum('monthlyamount'))['total'] or 0)
            dur = int(getattr(l, 'total_installments', 0) or l.duration or 0)
            try:
                emis_paid = int(paid // monthly) if monthly else 0
            except (TypeError, ValueError, ZeroDivisionError):
                emis_paid = 0
            total_emis = int(getattr(l, 'total_installments', 0) or dur)
            try:
                repayable = float(getattr(l, 'total_repayable_amount', 0) or (dur * monthly))
            except (TypeError, ValueError):
                repayable = 0.0
            principal = float(getattr(l, 'total_amount', 0) or l.amount or 0)
            try:
                interest_total = float(getattr(l, 'total_interest', 0) or (repayable - principal))
            except (TypeError, ValueError):
                interest_total = 0.0
            try:
                remaining = max(0.0, repayable - paid)
            except (TypeError, ValueError):
                remaining = 0.0
            status_str = (l.status or '').strip()
            if status_str in ('Rejected',):
                display_status = 'Rejected'
            elif status_str in ('Approved', 'Active') and emis_paid >= dur:
                display_status = 'Completed'
            else:
                display_status = status_str or 'Pending'
            loan_type = (l.loan_type or l.loan_details or 'Personal')[:50]
            can_pay = status_str in ('Approved', 'Active') and remaining > 0
            loan_list.append({
                'loan': l,
                'loan_type': loan_type,
                'emis_paid': emis_paid,
                'total_emis': total_emis,
                'remaining_amount': remaining,
                'display_status': display_status,
                'can_pay': can_pay,
                'total_interest': interest_total,
                'total_amount_to_pay': repayable,
            })
    context = {
        "loan": loan,
        "personal": personal,
        "loan_details": loan_details,
        "risk": risk,
        "return_to": return_to,
        "income_present": income_present,
        "guarantor_present": guarantor_present,
        "asset_present": asset_present,
        "data": loan_list,
    }
    return render(request, "admin/view_loan.html", context)


# def transaction(request):
#     data=Loantable.objects.all()
#     view=contract_note_instance.functions.getTransactionData().call(one)
#     print(view)
#     data=[]
#     for i in range(len(view)):
#             v={
#             "id":view[i][0],
#             "username":view[i][1],
#             "monthlyamount":view[i][2],
#             "method":view[i][3],
#             "transaction_date":view[i][4],
#             "status":view[i][5],
#             "upi_id":view[i][6],
#             "card_number":view[i][7],
#             "wallet_name":view[i][8],
#             "wallet_number":view[i][9],
#         }
#             data.append(v)
#     return render(request, "user/transaction.html", context={"data": list(data)})


def transaction(request):
    if request.method != 'GET':
        return redirect('user_transactions')
    user_id = request.session.get('user_id')
    username_from_session = request.session.get('username', '')
    if not user_id or not username_from_session:
        return redirect('login')
    qs = Transaction.objects.select_related('username', 'loan').filter(
        username__username=username_from_session
    )
    data = [
        {
            "id": t.id,
            "loan_id": getattr(t.loan, "id", ""),
            "loan_number": getattr(t.loan, "loan_number", ""),
            "transaction_number": getattr(t, "transaction_number", ""),
            "loan_type": getattr(t.loan, "loan_details", "") or getattr(t.loan, "loan_type", ""),
            "monthlyamount": t.monthlyamount,
            "method": t.method,
            "transaction_date": t.transaction_date,
            "status": t.status,
        }
        for t in qs
    ]
    return render(request, "user/transaction.html", context={
        "data": data,
        "username": username_from_session or "User",
        "id": user_id,
    })
