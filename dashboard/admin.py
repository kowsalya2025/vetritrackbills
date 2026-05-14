from django.contrib import admin
from .models import (
    Account,
    Bill,
    Budget,
    Category,
    Notification,
    PaymentAttempt,
    PaymentOrder,
    PaymentWebhookEvent,
    Refund,
    Transaction,
    UserProfile,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'income_source', 'monthly_income', 'onboarding_completed', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name')


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'provider', 'account_holder_name', 'initial_balance', 'created_at')
    list_filter = ('type', 'provider')
    search_fields = ('user__username', 'provider', 'account_holder_name')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'type')
    list_filter = ('type',)
    search_fields = ('name',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'amount', 'category', 'date')
    list_filter = ('category__type', 'category', 'date')
    search_fields = ('title', 'user__username', 'description')


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'category', 'provider', 'amount', 'due_date', 'status')
    list_filter = ('status', 'category', 'due_date')
    search_fields = ('name', 'provider', 'reference_number', 'user__username')


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('category', 'user', 'amount', 'alert_threshold', 'start_date', 'end_date')
    list_filter = ('category', 'alert_threshold')
    search_fields = ('category', 'user__username')


class PaymentAttemptInline(admin.TabularInline):
    model = PaymentAttempt
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    list_display = ('merchant_order_id', 'user', 'bill', 'provider', 'amount', 'status', 'created_at')
    list_filter = ('provider', 'status', 'created_at')
    search_fields = ('merchant_order_id', 'provider_order_id', 'user__username', 'bill__name')
    inlines = [PaymentAttemptInline]


@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(admin.ModelAdmin):
    list_display = ('provider', 'order', 'event_id', 'signature_valid', 'processed', 'created_at')
    list_filter = ('provider', 'signature_valid', 'processed')
    search_fields = ('event_id', 'order__merchant_order_id')


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('order', 'amount', 'status', 'provider_refund_id', 'created_at')
    list_filter = ('status',)
    search_fields = ('order__merchant_order_id', 'provider_refund_id')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('subject', 'user', 'channel', 'status', 'created_at')
    list_filter = ('channel', 'status')
    search_fields = ('subject', 'user__username', 'message')
