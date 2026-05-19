import json
import os
import uuid
import base64
import hashlib
import csv
import requests
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import AccountForm, BillForm, TransactionForm
from .models import (
    Account,
    Bill,
    Budget,
    Category,
    PaymentAttempt,
    PaymentOrder,
    PaymentWebhookEvent,
    Transaction,
    UserProfile,
)
from django.db.models import Sum
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User


def get_or_create_profile(user):
    profile, created = UserProfile.objects.get_or_create(user=user)
    return profile


def update_bill_statuses(bills):
    today = timezone.localdate()
    prepared = []
    for bill in bills:
        if bill.status != Bill.STATUS_PAID:
            if bill.due_date < today:
                bill.status = Bill.STATUS_OVERDUE
            elif (bill.due_date - today).days <= 7:
                bill.status = Bill.STATUS_DUE_SOON
            else:
                bill.status = Bill.STATUS_UPCOMING

        days_remaining = (bill.due_date - today).days
        if bill.status == Bill.STATUS_PAID:
            bill.due_label = 'Paid'
            bill.due_class = 'paid'
        elif days_remaining < 0:
            bill.due_label = f"Overdue {bill.due_date:%d/%m/%Y} ({abs(days_remaining)} days late)"
            bill.due_class = 'overdue'
        elif days_remaining == 0:
            bill.due_label = f"Due today ({bill.due_date:%d/%m/%Y})"
            bill.due_class = 'due-soon'
        else:
            bill.due_label = f"Due {bill.due_date:%d/%m/%Y} (in {days_remaining} days)"
            bill.due_class = 'due-soon' if days_remaining <= 7 else 'upcoming'
        prepared.append(bill)
    return prepared


def budget_label(category):
    labels = {
        'food': 'Food & Dining',
        'transport': 'Transportation',
        'shopping': 'Shopping',
        'entertainment': 'Entertainment',
    }
    return labels.get(category, category)


def prepare_budget_progress(user):
    budgets = list(Budget.objects.filter(user=user)[:4])
    for budget in budgets:
        label = budget_label(budget.category)
        spent = Transaction.objects.filter(
            user=user,
            category__type='expense',
            category__name__iexact=label,
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        budget.display_category = label
        budget.spent = spent
        budget.remaining = max(budget.amount - spent, Decimal('0'))
        usage = int((spent / budget.amount) * 100) if budget.amount else 0
        budget.usage_percent = min(usage, 100)
        budget.status_class = 'danger' if usage >= 100 else 'warning' if usage >= budget.alert_threshold else 'good'
    return budgets

def signup(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if User.objects.filter(username=email).exists():
            return render(request, 'signup.html', {'error': 'Email already exists'})
        
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name
        )
        user.save()
        login(request, user)
        return redirect('onboarding_step1')
    return render(request, 'signup.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            profile = get_or_create_profile(user)
            if not profile.onboarding_completed:
                return redirect('onboarding_step1')
            return redirect('dashboard')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

def onboarding_step1(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    profile = get_or_create_profile(request.user)
    
    if request.method == 'POST':
        income_source = request.POST.get('income_source')
        profile.income_source = income_source
        profile.save()
        return redirect('onboarding_step2')
    return render(request, 'onboarding_step1.html')

def onboarding_step2(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    profile = get_or_create_profile(request.user)
    
    if request.method == 'POST':
        monthly_income = request.POST.get('monthly_income')
        profile.monthly_income = monthly_income
        profile.save()
        return redirect('onboarding_step3')
    return render(request, 'onboarding_step2.html')

def onboarding_step3(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    profile = get_or_create_profile(request.user)
    
    if request.method == 'POST':
        methods = request.POST.getlist('methods')
        profile.money_management_methods = methods
        profile.save()
        return redirect('onboarding_step4')
    return render(request, 'onboarding_step3.html')

def onboarding_step4(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    profile = get_or_create_profile(request.user)
    
    if request.method == 'POST':
        if request.POST.get('skip'):
            return redirect('onboarding_step5')
        
        account_type = request.POST.get('account_type')
        account_holder = request.POST.get('account_holder')
        account_subtype = request.POST.get('account_subtype')
        account_number = request.POST.get('account_number')
        provider = request.POST.get('provider')
        initial_balance = request.POST.get('initial_balance', 0)
        
        Account.objects.create(
            user=request.user,
            type=account_type,
            account_holder_name=account_holder,
            account_type=account_subtype,
            account_number=account_number,
            provider=provider,
            initial_balance=initial_balance
        )
        return redirect('onboarding_step5')
    return render(request, 'onboarding_step4.html')

def onboarding_step5(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    if request.method == 'POST':
        if request.POST.get('skip'):
            return redirect('onboarding_step6')

        budget_category = request.POST.get('budget_category')
        budget_amount = request.POST.get('budget_amount')
        if budget_category and budget_amount:
            Budget.objects.create(
                user=request.user,
                category=budget_category,
                amount=budget_amount,
                start_date=parse_date(request.POST.get('start_date') or ''),
                end_date=parse_date(request.POST.get('end_date') or ''),
                alert_threshold=int(request.POST.get('alert_threshold') or 80),
            )
        return redirect('onboarding_step6')
    return render(request, 'onboarding_step5.html')

def onboarding_step6(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    profile = get_or_create_profile(request.user)
    
    if request.method == 'POST':
        profile.onboarding_completed = True
        profile.save()
        return redirect('dashboard')
    return render(request, 'onboarding_step6.html')

def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    profile = get_or_create_profile(request.user)
    if not profile.onboarding_completed:
        return redirect('onboarding_step1')
    
    accounts = Account.objects.filter(user=request.user).order_by('-created_at')
    account = accounts.first()
    account_balance = sum((item.initial_balance for item in accounts), Decimal('0'))
    account_holder = (
        account.account_holder_name
        if account and account.account_holder_name
        else request.user.first_name or request.user.username
    )
    bank_balance = sum((item.initial_balance for item in accounts if item.type == 'bank'), Decimal('0'))
    upi_balance = sum((item.initial_balance for item in accounts if item.type == 'upi'), Decimal('0'))
    credit_balance = sum((item.initial_balance for item in accounts if item.type == 'credit_card'), Decimal('0'))
    masked_account_number = ''
    if account and account.account_number:
        visible_digits = account.account_number[-2:]
        masked_account_number = f"xxxxxxxxxx{visible_digits}"

    transactions = Transaction.objects.filter(user=request.user).select_related('category', 'account').order_by('-date')
    transaction_income = transactions.filter(category__type='income').aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    total_income = transaction_income
    if profile.monthly_income:
        total_income += profile.monthly_income
    total_expense = transactions.filter(category__type='expense').aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    balance = account_balance + total_income - total_expense
    savings_rate = (balance / total_income * 100) if total_income else Decimal('0')
    bills = update_bill_statuses(
        Bill.objects.filter(user=request.user).exclude(status=Bill.STATUS_PAID).order_by('due_date')[:6]
    )
    recent_payment_orders = PaymentOrder.objects.filter(user=request.user).select_related('bill').order_by('-created_at')[:5]
    budgets = prepare_budget_progress(request.user)
    recent_transactions = transactions[:5]
    
    today = timezone.localdate()
    from datetime import timedelta
    last_week_dates = [(today - timedelta(days=i)).strftime('%b %d') for i in range(6, -1, -1)]
    
    income_data = [0]*7
    expense_data = [0]*7
    for t in transactions:
        days_ago = (today - t.date).days
        if 0 <= days_ago < 7:
            idx = 6 - days_ago
            if t.category.type == 'income':
                income_data[idx] += float(t.amount)
            else:
                expense_data[idx] += float(t.amount)
    
    expense_categories = {}
    for t in transactions.filter(category__type='expense'):
        cat_name = t.category.name
        expense_categories[cat_name] = expense_categories.get(cat_name, 0) + float(t.amount)

    context = {
        'transactions': transactions,
        'accounts': accounts,
        'account': account,
        'account_holder': account_holder,
        'bank_balance': bank_balance,
        'upi_balance': upi_balance,
        'credit_balance': credit_balance,
        'masked_account_number': masked_account_number,
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance,
        'savings_rate': savings_rate,
        'profile': profile,
        'bills': bills,
        'recent_payment_orders': recent_payment_orders,
        'recent_transactions': recent_transactions,
        'budgets': budgets,
        'last_week_dates': json.dumps(last_week_dates),
        'income_data': json.dumps(income_data),
        'expense_data': json.dumps(expense_data),
        'expense_categories': json.dumps(expense_categories),
        'expense_categories_dict': expense_categories,
        'bill_form': BillForm(),
        'account_form': AccountForm(),
        'transaction_form': TransactionForm(user=request.user, initial={'date': timezone.localdate()}),
    }
    return render(request, 'dashboard.html', context)


@require_POST
def add_bill(request):
    if not request.user.is_authenticated:
        return redirect('login')

    form = BillForm(request.POST)
    if form.is_valid():
        bill = form.save(commit=False)
        bill.user = request.user
        bill.save()
        messages.success(request, 'Bill added successfully.')
    else:
        messages.error(request, 'Please check the bill details and try again.')
    return redirect('dashboard')


@require_POST
def add_account(request):
    if not request.user.is_authenticated:
        return redirect('login')
        
    type = request.POST.get('type')
    account_holder_name = request.POST.get('account_holder_name')
    account_type = request.POST.get('account_type')
    account_number = request.POST.get('account_number')
    provider = request.POST.get('provider')
    initial_balance = request.POST.get('initial_balance', 0)
    
    Account.objects.create(
        user=request.user,
        type=type,
        account_holder_name=account_holder_name,
        account_type=account_type,
        account_number=account_number,
        provider=provider,
        initial_balance=initial_balance
    )
    messages.success(request, 'Account added successfully!')
    return redirect('accounts')

@require_POST
def edit_account(request, account_id):
    if not request.user.is_authenticated:
        return redirect('login')
        
    account = get_object_or_404(Account, id=account_id, user=request.user)
    
    account.type = request.POST.get('type')
    account.account_holder_name = request.POST.get('account_holder_name')
    account.account_type = request.POST.get('account_type')
    account.account_number = request.POST.get('account_number')
    account.provider = request.POST.get('provider')
    account.initial_balance = request.POST.get('initial_balance', 0)
    
    account.save()
    messages.success(request, 'Account updated successfully!')
    return redirect('accounts')

@require_POST
def delete_account(request, account_id):
    if not request.user.is_authenticated:
        return redirect('login')
        
    account = get_object_or_404(Account, id=account_id, user=request.user)
    account.delete()
    messages.success(request, 'Account deleted successfully!')
    return redirect('accounts')

@require_POST
def delete_transaction(request, transaction_id):
    if not request.user.is_authenticated:
        return redirect('login')
        
    transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)
    transaction.delete()
    messages.success(request, 'Transaction deleted successfully!')
    return redirect('transactions')

@require_POST
def delete_bill(request, bill_id):
    if not request.user.is_authenticated:
        return redirect('login')
        
    bill = get_object_or_404(Bill, id=bill_id, user=request.user)
    bill.delete()
    messages.success(request, 'Bill deleted successfully!')
    return redirect('bills')


@require_POST
def add_transaction(request):
    if not request.user.is_authenticated:
        return redirect('login')

    form = TransactionForm(request.POST, user=request.user)
    if form.is_valid():
        category, created = Category.objects.get_or_create(
            name=form.cleaned_data['category_name'].strip(),
            type=form.cleaned_data['transaction_type'],
        )
        Transaction.objects.create(
            user=request.user,
            account=form.cleaned_data['account'],
            title=form.cleaned_data['title'],
            amount=form.cleaned_data['amount'],
            category=category,
            date=form.cleaned_data['date'],
            description=form.cleaned_data['description'],
        )
        messages.success(request, 'Transaction added successfully.')
    else:
        messages.error(request, 'Please check the transaction details and try again.')
    return redirect('dashboard')


def start_bill_payment(request, bill_id):
    if not request.user.is_authenticated:
        return redirect('login')
    if request.method != 'POST':
        return HttpResponseBadRequest('Payment must be started with POST.')

    bill = get_object_or_404(Bill, id=bill_id, user=request.user)
    if bill.status == Bill.STATUS_PAID:
        return redirect('dashboard')

    merchant_order_id = f"VPIN-{timezone.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8].upper()}"
    order = PaymentOrder.objects.create(
        user=request.user,
        bill=bill,
        merchant_order_id=merchant_order_id,
        amount=bill.amount,
        status=PaymentOrder.STATUS_CREATED,
    )

    callback_url = request.build_absolute_uri(reverse('phonepe_webhook'))
    redirect_url = request.build_absolute_uri(reverse('payment_status', args=[order.merchant_order_id]))
    
    if settings.PHONEPE_ENABLED:
        # Prepare PhonePe Payload
        payload = {
            "merchantId": settings.PHONEPE_MERCHANT_ID,
            "merchantTransactionId": merchant_order_id,
            "merchantUserId": str(request.user.id),
            "amount": int(bill.amount * 100), # Amount in paise
            "redirectUrl": redirect_url,
            "redirectMode": "REDIRECT",
            "callbackUrl": callback_url,
            "paymentInstrument": {"type": "PAY_PAGE"}
        }

        # Base64 Encode Payload
        json_payload = json.dumps(payload)
        base64_payload = base64.b64encode(json_payload.encode()).decode()

        # Generate Checksum
        # PhonePe Checksum Formula: SHA256(Base64Payload + endpoint + SaltKey) + "###" + SaltIndex
        endpoint = "/pg/v1/pay"
        main_string = base64_payload + endpoint + settings.PHONEPE_SALT_KEY
        sha256_hash = hashlib.sha256(main_string.encode()).hexdigest()
        checksum = sha256_hash + "###" + settings.PHONEPE_SALT_INDEX

        # Headers for PhonePe
        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": checksum,
            "accept": "application/json"
        }

        try:
            response = requests.post(settings.PHONEPE_API_URL, json={"request": base64_payload}, headers=headers)
            res_data = response.json()

            if res_data.get('success'):
                order.status = PaymentOrder.STATUS_PENDING
                order.checkout_url = res_data['data']['instrumentResponse']['redirectInfo']['url']
                order.save(update_fields=['status', 'checkout_url', 'updated_at'])
                
                PaymentAttempt.objects.create(
                    order=order,
                    status=PaymentOrder.STATUS_PENDING,
                    request_payload=payload,
                    response_payload=res_data,
                )
                return redirect(order.checkout_url)
            else:
                order.status = PaymentOrder.STATUS_FAILED
                order.failure_reason = res_data.get('message', 'Failed to initiate payment')
                order.save(update_fields=['status', 'failure_reason', 'updated_at'])
                
                PaymentAttempt.objects.create(
                    order=order,
                    status=PaymentOrder.STATUS_FAILED,
                    request_payload=payload,
                    response_payload=res_data,
                    failure_reason=order.failure_reason
                )
                messages.error(request, f"Payment initiation failed: {order.failure_reason}")
                return redirect('payment_status', merchant_order_id=order.merchant_order_id)
        except Exception as e:
            order.status = PaymentOrder.STATUS_FAILED
            order.failure_reason = str(e)
            order.save(update_fields=['status', 'failure_reason', 'updated_at'])
            messages.error(request, "A technical error occurred while initiating payment.")
            return redirect('payment_status', merchant_order_id=order.merchant_order_id)

    # Fallback for sandbox/development if not enabled
    order.status = PaymentOrder.STATUS_PENDING
    order.failure_reason = 'PhonePe is not enabled in settings. Order stored for development.'
    order.save(update_fields=['status', 'failure_reason', 'updated_at'])
    PaymentAttempt.objects.create(
        order=order,
        status=PaymentOrder.STATUS_PENDING,
        request_payload={'merchant_order_id': merchant_order_id, 'amount': str(bill.amount)},
        response_payload={'mode': 'not_enabled'},
        failure_reason=order.failure_reason,
    )
    return redirect('payment_status', merchant_order_id=order.merchant_order_id)


def payment_status(request, merchant_order_id):
    if not request.user.is_authenticated:
        return redirect('login')

    order = get_object_or_404(
        PaymentOrder.objects.select_related('bill'),
        merchant_order_id=merchant_order_id,
        user=request.user,
    )

    if order.status == PaymentOrder.STATUS_PENDING and settings.PHONEPE_ENABLED:
        merchant_id = settings.PHONEPE_MERCHANT_ID
        endpoint = f"/pg/v1/status/{merchant_id}/{merchant_order_id}"
        main_string = endpoint + settings.PHONEPE_SALT_KEY
        sha256_hash = hashlib.sha256(main_string.encode()).hexdigest()
        checksum = sha256_hash + "###" + settings.PHONEPE_SALT_INDEX

        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": checksum,
            "X-MERCHANT-ID": merchant_id,
            "accept": "application/json"
        }

        status_url = f"{settings.PHONEPE_STATUS_URL}/{merchant_id}/{merchant_order_id}"
        
        try:
            response = requests.get(status_url, headers=headers)
            res_data = response.json()
            
            if res_data.get('success'):
                code = res_data.get('code')
                if code == 'PAYMENT_SUCCESS':
                    order.status = PaymentOrder.STATUS_SUCCESS
                    order.bill.status = Bill.STATUS_PAID
                    order.bill.paid_at = timezone.now()
                    order.bill.save(update_fields=['status', 'paid_at', 'updated_at'])
                elif code == 'PAYMENT_ERROR':
                    order.status = PaymentOrder.STATUS_FAILED
                    order.bill.status = Bill.STATUS_FAILED
                    order.bill.save(update_fields=['status', 'updated_at'])
                
                if 'data' in res_data and 'transactionId' in res_data['data']:
                    order.provider_order_id = res_data['data']['transactionId']
                
                order.save(update_fields=['status', 'provider_order_id', 'updated_at'])
                PaymentAttempt.objects.create(order=order, status=order.status, response_payload=res_data)
        except Exception as e:
            pass

    attempts = order.attempts.all()
    return render(request, 'payment_status.html', {'order': order, 'attempts': attempts})


def download_receipt(request, merchant_order_id):
    if not request.user.is_authenticated:
        return redirect('login')

    order = get_object_or_404(
        PaymentOrder.objects.select_related('bill', 'user'),
        merchant_order_id=merchant_order_id,
        user=request.user,
        status=PaymentOrder.STATUS_SUCCESS,
    )
    lines = [
        'Vetri PinTrack Payment Receipt',
        f"Receipt Date: {timezone.localtime(order.updated_at):%d/%m/%Y %I:%M %p}",
        f"Order ID: {order.merchant_order_id}",
        f"Bill: {order.bill.name}",
        f"Amount: Rs. {order.amount}",
        f"Provider: {order.get_provider_display()}",
        f"Status: {order.get_status_display()}",
    ]
    response = HttpResponse('\n'.join(lines), content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{order.merchant_order_id}_receipt.txt"'
    return response


@csrf_exempt
def phonepe_webhook(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Webhook requires POST.')

    # PhonePe sends the response in a base64 encoded 'response' field
    try:
        received_payload = json.loads(request.body.decode('utf-8'))
        base64_response = received_payload.get('response')
        
        if not base64_response:
            return HttpResponseBadRequest('Missing response field.')

        # Verify Checksum
        received_checksum = request.headers.get('X-VERIFY')
        if not received_checksum:
            return HttpResponseBadRequest('Missing X-VERIFY header.')

        main_string = base64_response + settings.PHONEPE_SALT_KEY
        sha256_hash = hashlib.sha256(main_string.encode()).hexdigest()
        expected_checksum = sha256_hash + "###" + settings.PHONEPE_SALT_INDEX

        if received_checksum != expected_checksum:
            return JsonResponse({'ok': False, 'error': 'invalid_signature'}, status=403)

        # Decode payload
        decoded_response = json.loads(base64.b64decode(base64_response).decode())
    except Exception as e:
        return HttpResponseBadRequest(f'Invalid payload: {str(e)}')

    merchant_order_id = decoded_response.get('data', {}).get('merchantTransactionId')
    order = PaymentOrder.objects.filter(merchant_order_id=merchant_order_id).first()
    
    event = PaymentWebhookEvent.objects.create(
        order=order,
        event_id=decoded_response.get('code'),
        payload=decoded_response,
        signature_valid=True,
    )

    if not order:
        return JsonResponse({'ok': False, 'error': 'order_not_found'}, status=404)

    status_code = decoded_response.get('code')
    if status_code == 'PAYMENT_SUCCESS':
        order.status = PaymentOrder.STATUS_SUCCESS
        order.bill.status = Bill.STATUS_PAID
        order.bill.paid_at = timezone.now()
        order.bill.save(update_fields=['status', 'paid_at', 'updated_at'])
    elif status_code == 'PAYMENT_ERROR':
        order.status = PaymentOrder.STATUS_FAILED
        order.bill.status = Bill.STATUS_FAILED
        order.bill.save(update_fields=['status', 'updated_at'])
    else:
        order.status = PaymentOrder.STATUS_PENDING

    order.provider_order_id = decoded_response.get('data', {}).get('transactionId')
    order.save(update_fields=['status', 'provider_order_id', 'updated_at'])
    PaymentAttempt.objects.create(order=order, status=order.status, response_payload=decoded_response)

    event.processed = True
    event.save(update_fields=['processed'])
    return JsonResponse({'ok': True, 'status': order.status})


def bills_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    profile = get_or_create_profile(request.user)
    account_holder = request.user.first_name or request.user.username
    accounts = Account.objects.filter(user=request.user).order_by('-created_at')
    if accounts.exists():
        account_holder = accounts.first().account_holder_name or account_holder
        
    bills_query = Bill.objects.filter(user=request.user).order_by('due_date')
    bills = update_bill_statuses(bills_query)
    
    total_bills = sum(b.amount for b in bills)
    paid_this_month = sum(b.amount for b in bills if b.status == Bill.STATUS_PAID and getattr(b, 'paid_at', None) and b.paid_at.month == timezone.now().month)
    pending_bills = sum(b.amount for b in bills if b.status != Bill.STATUS_PAID)

    context = {
        'profile': profile,
        'account_holder': account_holder,
        'bills': bills,
        'total_bills': total_bills,
        'paid_this_month': paid_this_month,
        'pending_bills': pending_bills,
        'bill_form': BillForm(),
    }
    return render(request, 'bills.html', context)


def reports_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    profile = get_or_create_profile(request.user)
    account_holder = request.user.first_name or request.user.username
    accounts = Account.objects.filter(user=request.user).order_by('-created_at')
    if accounts.exists():
        account_holder = accounts.first().account_holder_name or account_holder

    transactions = Transaction.objects.filter(user=request.user).select_related('category').order_by('-date')
    
    total_income = transactions.filter(category__type='income').aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    if profile.monthly_income:
        total_income += profile.monthly_income
        
    total_expense = transactions.filter(category__type='expense').aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    account_balance = sum((item.initial_balance for item in accounts), Decimal('0'))
    total_balance = account_balance + total_income - total_expense
    
    savings_rate = (total_balance / total_income * 100) if total_income else Decimal('0')

    today = timezone.localdate()
    from datetime import timedelta
    last_week_dates = [(today - timedelta(days=i)).strftime('%b %d') for i in range(6, -1, -1)]
    
    income_data = [0]*7
    expense_data = [0]*7
    for t in transactions:
        days_ago = (today - t.date).days
        if 0 <= days_ago < 7:
            idx = 6 - days_ago
            if t.category.type == 'income':
                income_data[idx] += float(t.amount)
            else:
                expense_data[idx] += float(t.amount)
    
    expense_categories = {}
    for t in transactions.filter(category__type='expense'):
        cat_name = t.category.name
        expense_categories[cat_name] = expense_categories.get(cat_name, 0) + float(t.amount)
        
    top_spending = transactions.filter(category__type='expense').order_by('-amount')[:5]

    context = {
        'profile': profile,
        'account_holder': account_holder,
        'transactions': transactions,
        'total_income': total_income,
        'total_expense': total_expense,
        'total_balance': total_balance,
        'savings_rate': savings_rate,
        'last_week_dates': json.dumps(last_week_dates),
        'income_data': json.dumps(income_data),
        'expense_data': json.dumps(expense_data),
        'expense_categories_labels': json.dumps(list(expense_categories.keys())),
        'expense_categories_data': json.dumps(list(expense_categories.values())),
        'top_spending': top_spending,
    }
    return render(request, 'reports.html', context)


def transactions_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    profile = get_or_create_profile(request.user)
    account_holder = request.user.first_name or request.user.username
    accounts = Account.objects.filter(user=request.user).order_by('-created_at')
    if accounts.exists():
        account_holder = accounts.first().account_holder_name or account_holder

    # Get filter parameters
    date_range = request.GET.get('date_range', 'all')
    transaction_type = request.GET.get('type', 'all')
    search_query = request.GET.get('search', '')

    transactions_query = Transaction.objects.filter(user=request.user).select_related('category', 'account').order_by('-date')

    # Apply filters
    if search_query:
        transactions_query = transactions_query.filter(title__icontains=search_query)
    
    if transaction_type != 'all':
        transactions_query = transactions_query.filter(category__type=transaction_type)

    today = timezone.localdate()
    if date_range == '7_days':
        transactions_query = transactions_query.filter(date__gte=today - timezone.timedelta(days=7))
    elif date_range == '30_days':
        transactions_query = transactions_query.filter(date__gte=today - timezone.timedelta(days=30))
    elif date_range == '90_days':
        transactions_query = transactions_query.filter(date__gte=today - timezone.timedelta(days=90))

    # Summary calculations
    total_income = transactions_query.filter(category__type='income').aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    if profile.monthly_income:
        total_income += profile.monthly_income
    total_expense = transactions_query.filter(category__type='expense').aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    net_balance = total_income - total_expense

    categories = Category.objects.all()

    context = {        'profile': profile,
        'account_holder': account_holder,
        'transactions': transactions_query,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_balance': net_balance,
        'categories': categories,
        'accounts': accounts,
        'date_range': date_range,
        'transaction_type': transaction_type,
        'search_query': search_query,
        'transaction_form': TransactionForm(user=request.user),
    }
    return render(request, 'transactions.html', context)


def budgets_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    profile = get_or_create_profile(request.user)
    account_holder = request.user.first_name or request.user.username
    accounts = Account.objects.filter(user=request.user).order_by('-created_at')
    if accounts.exists():
        account_holder = accounts.first().account_holder_name or account_holder

    budgets = Budget.objects.filter(user=request.user)
    
    for budget in budgets:
        # Calculate spent for this budget's category within its dates
        spent = Transaction.objects.filter(
            user=request.user,
            category__name__iexact=budget.category,
            category__type='expense'
        )
        
        if budget.start_date:
            spent = spent.filter(date__gte=budget.start_date)
        if budget.end_date:
            spent = spent.filter(date__lte=budget.end_date)
            
        spent_amount = spent.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        budget.spent = spent_amount
        budget.remaining = max(budget.amount - spent_amount, Decimal('0'))
        
        usage = int((spent_amount / budget.amount) * 100) if budget.amount else 0
        budget.usage_percent = min(usage, 100)
        
        if usage >= 100:
            budget.status_class = 'danger'
            budget.status_label = 'Over Limit'
        elif usage >= budget.alert_threshold:
            budget.status_class = 'warning'
            budget.status_label = 'Near Limit'
        else:
            budget.status_class = 'good'
            budget.status_label = 'On Track'

    context = {
        'profile': profile,
        'account_holder': account_holder,
        'budgets': budgets,
        'categories': Category.objects.filter(type='expense').values_list('name', flat=True).distinct(),
    }
    return render(request, 'budgets.html', context)

@require_POST
def add_budget(request):
    if not request.user.is_authenticated:
        return redirect('login')
        
    category = request.POST.get('category')
    amount = request.POST.get('amount')
    start_date = request.POST.get('start_date')
    end_date = request.POST.get('end_date')
    alert_threshold = request.POST.get('alert_threshold', 80)
    
    Budget.objects.create(
        user=request.user,
        category=category,
        amount=amount,
        start_date=parse_date(start_date) if start_date else None,
        end_date=parse_date(end_date) if end_date else None,
        alert_threshold=alert_threshold
    )
    messages.success(request, 'Budget created successfully!')
    return redirect('budgets')

@require_POST
def edit_budget(request, budget_id):
    if not request.user.is_authenticated:
        return redirect('login')
        
    budget = get_object_or_404(Budget, id=budget_id, user=request.user)
    
    budget.category = request.POST.get('category')
    budget.amount = request.POST.get('amount')
    start_date = request.POST.get('start_date')
    end_date = request.POST.get('end_date')
    budget.start_date = parse_date(start_date) if start_date else None
    budget.end_date = parse_date(end_date) if end_date else None
    budget.alert_threshold = request.POST.get('alert_threshold', 80)
    
    budget.save()
    messages.success(request, 'Budget updated successfully!')
    return redirect('budgets')

@require_POST
def delete_budget(request, budget_id):
    if not request.user.is_authenticated:
        return redirect('login')
        
    budget = get_object_or_404(Budget, id=budget_id, user=request.user)
    budget.delete()
    messages.success(request, 'Budget deleted successfully!')
    return redirect('budgets')

def export_transactions(request):
    if not request.user.is_authenticated:
        return redirect('login')
        
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="transactions_export_{timezone.now():%Y%m%d}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Title', 'Amount', 'Type', 'Category', 'Account', 'Description'])
    
    transactions = Transaction.objects.filter(user=request.user).select_related('category', 'account').order_by('-date')
    for t in transactions:
        writer.writerow([
            t.date,
            t.title,
            t.amount,
            t.category.get_type_display(),
            t.category.name,
            t.account.provider if t.account else 'Manual',
            t.description or ''
        ])
    return response


def settings_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    profile = get_or_create_profile(request.user)
    account_holder = request.user.first_name or request.user.username
    accounts = Account.objects.filter(user=request.user).order_by('-created_at')
    if accounts.exists():
        account_holder = accounts.first().account_holder_name or account_holder

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'profile_settings':
            request.user.first_name = request.POST.get('name', '')
            request.user.email = request.POST.get('email', '')
            request.user.save()
            
            profile.phone_number = request.POST.get('phone_number', '')
            
            # Handle profile picture upload
            if 'profile_picture' in request.FILES:
                profile.profile_picture = request.FILES['profile_picture']
                
            profile.save()
            messages.success(request, 'Profile settings updated successfully!')
            
        elif action == 'security_settings':
            # Simplified password change logic
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            if new_password and new_password == confirm_password:
                request.user.set_password(new_password)
                request.user.save()
                login(request, request.user) # Keep the user logged in
                messages.success(request, 'Password changed successfully!')
            else:
                messages.error(request, 'Passwords do not match.')
                
        elif action == 'toggle_settings':
            profile.two_factor_auth = 'two_factor_auth' in request.POST
            profile.bill_reminders = 'bill_reminders' in request.POST
            profile.budget_alerts = 'budget_alerts' in request.POST
            profile.transaction_alerts = 'transaction_alerts' in request.POST
            profile.upi_connected = 'upi_connected' in request.POST
            profile.bank_account_connected = 'bank_account_connected' in request.POST
            profile.save()
            messages.success(request, 'Preferences updated successfully!')
            
        elif action == 'currency_settings':
            profile.currency = request.POST.get('currency', 'INR')
            profile.save()
            messages.success(request, 'Currency updated successfully!')
            
        elif action == 'clear_data':
            # Danger zone: Clear all transactions and bills
            Transaction.objects.filter(user=request.user).delete()
            Bill.objects.filter(user=request.user).delete()
            messages.success(request, 'All data cleared successfully!')
            
        return redirect('settings')

    context = {
        'profile': profile,
        'account_holder': account_holder,
    }
    return render(request, 'settings.html', context)

def accounts_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    profile = get_or_create_profile(request.user)
    account_holder = request.user.first_name or request.user.username
    accounts = Account.objects.filter(user=request.user).order_by('-created_at')
    if accounts.exists():
        account_holder = accounts.first().account_holder_name or account_holder

    transactions = Transaction.objects.filter(user=request.user).select_related('category')
    total_income = transactions.filter(category__type='income').aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    if profile.monthly_income:
        total_income += profile.monthly_income
        
    total_expense = transactions.filter(category__type='expense').aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    account_balance = sum((item.initial_balance for item in accounts), Decimal('0'))
    total_balance = account_balance + total_income - total_expense
    
    bank_accounts = accounts.filter(type='bank')
    upi_accounts = accounts.filter(type='upi')
    credit_cards = accounts.filter(type='credit_card')
    
    bank_balance = sum((item.initial_balance for item in bank_accounts), Decimal('0'))
    upi_balance = sum((item.initial_balance for item in upi_accounts), Decimal('0'))
    credit_balance = sum((item.initial_balance for item in credit_cards), Decimal('0'))

    context = {
        'profile': profile,
        'account_holder': account_holder,
        'accounts': accounts,
        'total_balance': total_balance,
        'bank_balance': bank_balance,
        'upi_balance': upi_balance,
        'credit_balance': credit_balance,
        'bank_accounts': bank_accounts,
        'upi_accounts': upi_accounts,
        'credit_cards': credit_cards,
        'total_accounts': accounts.count(),
        'bank_count': bank_accounts.count(),
        'upi_count': upi_accounts.count(),
        'credit_count': credit_cards.count(),
        'account_form': AccountForm(),
    }
    return render(request, 'accounts.html', context)
