from django import forms

from .models import Account, Bill


class BillForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = ['name', 'category', 'provider', 'reference_number', 'amount', 'due_date', 'is_recurring', 'reminder_enabled']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['type', 'account_holder_name', 'account_type', 'account_number', 'provider', 'initial_balance']


class TransactionForm(forms.Form):
    TYPE_CHOICES = [
        ('expense', 'Expense'),
        ('income', 'Income'),
    ]

    transaction_type = forms.ChoiceField(choices=TYPE_CHOICES)
    title = forms.CharField(max_length=200)
    category_name = forms.CharField(max_length=100)
    amount = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    description = forms.CharField(required=False, widget=forms.Textarea)
    account = forms.ModelChoiceField(queryset=Account.objects.none(), required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['account'].queryset = Account.objects.filter(user=user).order_by('-created_at')
