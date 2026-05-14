import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vetribills.settings')
django.setup()

from django.contrib.auth.models import User
from dashboard.models import UserProfile

def create_test_user():
    user, created = User.objects.get_or_create(
        username='test@example.com',
        email='test@example.com',
        defaults={'first_name': 'Lilly'}
    )
    
    if created:
        user.set_password('test123')
        user.save()
    
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.onboarding_completed = True
    profile.income_source = 'Salary'
    profile.monthly_income = 5000
    profile.save()
    
    print(f'Test user created!')
    print(f'Email: test@example.com')
    print(f'Password: test123')

if __name__ == '__main__':
    create_test_user()
