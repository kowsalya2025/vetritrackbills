import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vetribills.settings')
django.setup()

from dashboard.models import Category, Transaction

def populate_data():
    # Create categories
    income_categories = [
        {'name': 'Salary', 'type': 'income'},
        {'name': 'Freelance', 'type': 'income'},
        {'name': 'Investments', 'type': 'income'},
    ]
    
    expense_categories = [
        {'name': 'Food & Dining', 'type': 'expense'},
        {'name': 'Transportation', 'type': 'expense'},
        {'name': 'Shopping', 'type': 'expense'},
        {'name': 'Bills', 'type': 'expense'},
        {'name': 'Entertainment', 'type': 'expense'},
    ]
    
    categories = {}
    for cat_data in income_categories + expense_categories:
        cat, created = Category.objects.get_or_create(**cat_data)
        categories[cat.name] = cat
    
    # Create sample transactions
    transactions_data = [
        {'title': 'Monthly Salary', 'amount': 5000.00, 'category': 'Salary', 'date': date.today().replace(day=1), 'description': 'Monthly salary deposit'},
        {'title': 'Grocery Shopping', 'amount': 150.50, 'category': 'Food & Dining', 'date': date.today() - timedelta(days=2), 'description': 'Weekly groceries'},
        {'title': 'Uber Ride', 'amount': 25.00, 'category': 'Transportation', 'date': date.today() - timedelta(days=1), 'description': 'To office'},
        {'title': 'Freelance Project', 'amount': 800.00, 'category': 'Freelance', 'date': date.today() - timedelta(days=3), 'description': 'Web design project'},
        {'title': 'Electricity Bill', 'amount': 120.00, 'category': 'Bills', 'date': date.today() - timedelta(days=5), 'description': 'Monthly electricity bill'},
        {'title': 'Netflix Subscription', 'amount': 15.99, 'category': 'Entertainment', 'date': date.today() - timedelta(days=7), 'description': 'Monthly subscription'},
        {'title': 'New Shoes', 'amount': 89.99, 'category': 'Shopping', 'date': date.today() - timedelta(days=10), 'description': 'Running shoes'},
        {'title': 'Stock Dividend', 'amount': 250.00, 'category': 'Investments', 'date': date.today() - timedelta(days=14), 'description': 'Quarterly dividend'},
    ]
    
    for tx_data in transactions_data:
        tx_data['category'] = categories[tx_data['category']]
        Transaction.objects.create(**tx_data)
    
    print('Sample data added successfully!')

if __name__ == '__main__':
    populate_data()
