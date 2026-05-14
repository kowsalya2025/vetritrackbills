from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    income_source = models.CharField(max_length=50, blank=True, null=True)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    money_management_methods = models.JSONField(default=list, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    currency = models.CharField(max_length=10, default='INR')
    two_factor_auth = models.BooleanField(default=False)
    bill_reminders = models.BooleanField(default=True)
    budget_alerts = models.BooleanField(default=True)
    transaction_alerts = models.BooleanField(default=False)
    upi_connected = models.BooleanField(default=True)
    bank_account_connected = models.BooleanField(default=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    onboarding_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.first_name}'s Profile"


class Account(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    type = models.CharField(max_length=50, choices=[('bank', 'Bank'), ('upi', 'UPI'), ('wallet', 'Wallet'), ('credit_card', 'Credit Card')])
    account_holder_name = models.CharField(max_length=200, blank=True, null=True)
    account_type = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=100, blank=True, null=True)
    provider = models.CharField(max_length=100, blank=True, null=True)
    initial_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type} - {self.provider or 'Account'}"


class Category(models.Model):
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=[('income', 'Income'), ('expense', 'Expense')])

    def __str__(self):
        return self.name


class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions', blank=True, null=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, related_name='transactions', blank=True, null=True)
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    date = models.DateField()
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.title} - {self.amount}"


class Bill(models.Model):
    STATUS_UPCOMING = 'upcoming'
    STATUS_DUE_SOON = 'due_soon'
    STATUS_OVERDUE = 'overdue'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_UPCOMING, 'Upcoming'),
        (STATUS_DUE_SOON, 'Due Soon'),
        (STATUS_OVERDUE, 'Overdue'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
    ]

    CATEGORY_CHOICES = [
        ('electricity', 'Electricity'),
        ('mobile', 'Mobile Recharge'),
        ('internet', 'Internet'),
        ('gas', 'Gas'),
        ('water', 'Water'),
        ('insurance', 'Insurance'),
        ('subscription', 'Subscription'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bills')
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other')
    provider = models.CharField(max_length=120, blank=True, null=True)
    reference_number = models.CharField(max_length=120, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_UPCOMING)
    is_recurring = models.BooleanField(default=False)
    reminder_enabled = models.BooleanField(default=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', 'name']

    def __str__(self):
        return f"{self.name} - {self.amount}"


class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    alert_threshold = models.PositiveIntegerField(default=80)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.category} - {self.amount}"


class PaymentOrder(models.Model):
    PROVIDER_PHONEPE = 'phonepe'

    PROVIDER_CHOICES = [
        (PROVIDER_PHONEPE, 'PhonePe'),
    ]

    STATUS_CREATED = 'created'
    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_EXPIRED = 'expired'
    STATUS_REFUNDED = 'refunded'

    STATUS_CHOICES = [
        (STATUS_CREATED, 'Created'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_orders')
    bill = models.ForeignKey(Bill, on_delete=models.PROTECT, related_name='payment_orders')
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES, default=PROVIDER_PHONEPE)
    merchant_order_id = models.CharField(max_length=80, unique=True)
    provider_order_id = models.CharField(max_length=120, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_CREATED)
    checkout_url = models.URLField(blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.merchant_order_id} - {self.status}"


class PaymentAttempt(models.Model):
    order = models.ForeignKey(PaymentOrder, on_delete=models.CASCADE, related_name='attempts')
    provider_transaction_id = models.CharField(max_length=120, blank=True, null=True)
    status = models.CharField(max_length=30, choices=PaymentOrder.STATUS_CHOICES, default=PaymentOrder.STATUS_CREATED)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    failure_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order.merchant_order_id} attempt - {self.status}"


class PaymentWebhookEvent(models.Model):
    provider = models.CharField(max_length=30, choices=PaymentOrder.PROVIDER_CHOICES, default=PaymentOrder.PROVIDER_PHONEPE)
    order = models.ForeignKey(PaymentOrder, on_delete=models.SET_NULL, related_name='webhook_events', blank=True, null=True)
    event_id = models.CharField(max_length=120, blank=True, null=True)
    payload = models.JSONField(default=dict, blank=True)
    signature_valid = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.provider} webhook - {self.event_id or self.created_at}"


class Refund(models.Model):
    order = models.ForeignKey(PaymentOrder, on_delete=models.PROTECT, related_name='refunds')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    provider_refund_id = models.CharField(max_length=120, blank=True, null=True)
    status = models.CharField(max_length=30, choices=PaymentOrder.STATUS_CHOICES, default=PaymentOrder.STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Refund {self.order.merchant_order_id} - {self.amount}"


class Notification(models.Model):
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
        ('in_app', 'In App'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    bill = models.ForeignKey(Bill, on_delete=models.SET_NULL, related_name='notifications', blank=True, null=True)
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES, default='in_app')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.subject
