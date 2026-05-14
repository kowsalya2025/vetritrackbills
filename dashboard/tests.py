import json
import os
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Bill, Category, PaymentOrder, Transaction, UserProfile


class DashboardLiveReadinessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='owner@example.com', password='pass12345')
        self.other_user = User.objects.create_user(username='other@example.com', password='pass12345')
        UserProfile.objects.create(user=self.user, monthly_income=Decimal('50000.00'), onboarding_completed=True)
        UserProfile.objects.create(user=self.other_user, monthly_income=Decimal('90000.00'), onboarding_completed=True)
        self.expense_category = Category.objects.create(name='Bills', type='expense')
        self.income_category = Category.objects.create(name='Salary', type='income')

    def test_dashboard_filters_transactions_by_logged_in_user(self):
        Transaction.objects.create(
            user=self.user,
            title='Owner bill',
            amount=Decimal('1000.00'),
            category=self.expense_category,
            date=timezone.localdate(),
        )
        Transaction.objects.create(
            user=self.other_user,
            title='Other bill',
            amount=Decimal('7000.00'),
            category=self.expense_category,
            date=timezone.localdate(),
        )

        self.client.login(username='owner@example.com', password='pass12345')
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_expense'], Decimal('1000.00'))

    def test_start_bill_payment_creates_pending_phonepe_order(self):
        bill = Bill.objects.create(
            user=self.user,
            name='Electricity Bill',
            category='electricity',
            amount=Decimal('1200.00'),
            due_date=timezone.localdate() + timedelta(days=3),
        )

        self.client.login(username='owner@example.com', password='pass12345')
        response = self.client.post(reverse('start_bill_payment', args=[bill.id]))

        order = PaymentOrder.objects.get(user=self.user, bill=bill)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.status, PaymentOrder.STATUS_PENDING)
        self.assertTrue(order.merchant_order_id.startswith('VPIN-'))

    def test_payment_webhook_marks_bill_paid(self):
        os.environ['PHONEPE_WEBHOOK_TOKEN'] = 'test-token'
        bill = Bill.objects.create(
            user=self.user,
            name='Mobile Recharge',
            category='mobile',
            amount=Decimal('319.00'),
            due_date=timezone.localdate(),
        )
        order = PaymentOrder.objects.create(
            user=self.user,
            bill=bill,
            merchant_order_id='VPIN-TEST-001',
            amount=bill.amount,
            status=PaymentOrder.STATUS_PENDING,
        )
        payload = {'merchant_order_id': order.merchant_order_id, 'status': 'success'}

        response = self.client.post(
            reverse('phonepe_webhook'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_VETRI_PAYMENT_TOKEN='test-token',
        )

        order.refresh_from_db()
        bill.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(order.status, PaymentOrder.STATUS_SUCCESS)
        self.assertEqual(bill.status, Bill.STATUS_PAID)

    def test_add_bill_from_dashboard_action(self):
        self.client.login(username='owner@example.com', password='pass12345')
        response = self.client.post(
            reverse('add_bill'),
            data={
                'name': 'Internet Bill',
                'category': 'internet',
                'provider': 'Fiber Provider',
                'reference_number': 'NET123',
                'amount': '999.00',
                'due_date': timezone.localdate() + timedelta(days=5),
                'reminder_enabled': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Bill.objects.filter(user=self.user, name='Internet Bill').exists())

    def test_add_transaction_from_dashboard_action(self):
        self.client.login(username='owner@example.com', password='pass12345')
        response = self.client.post(
            reverse('add_transaction'),
            data={
                'transaction_type': 'expense',
                'title': 'Lunch',
                'category_name': 'Food & Dining',
                'amount': '250.00',
                'date': timezone.localdate(),
                'description': 'Team lunch',
            },
        )

        transaction = Transaction.objects.get(user=self.user, title='Lunch')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(transaction.category.type, 'expense')

    def test_successful_payment_receipt_download(self):
        bill = Bill.objects.create(
            user=self.user,
            name='Gas Bill',
            category='gas',
            amount=Decimal('800.00'),
            due_date=timezone.localdate(),
            status=Bill.STATUS_PAID,
            paid_at=timezone.now(),
        )
        order = PaymentOrder.objects.create(
            user=self.user,
            bill=bill,
            merchant_order_id='VPIN-RECEIPT-001',
            amount=bill.amount,
            status=PaymentOrder.STATUS_SUCCESS,
        )

        self.client.login(username='owner@example.com', password='pass12345')
        response = self.client.get(reverse('download_receipt', args=[order.merchant_order_id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertContains(response, 'Vetri PinTrack Payment Receipt')
