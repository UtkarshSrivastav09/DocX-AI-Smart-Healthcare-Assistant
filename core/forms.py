from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import SymptomEntry

class UserRegistrationForm(UserCreationForm):
    """
    Custom registration form extending Django's UserCreationForm.
    """
    email = forms.EmailField(
        required=True, 
        help_text="Required. Enter a valid email address.",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    first_name = forms.CharField(
        max_length=30, 
        required=False, 
        help_text="Optional.",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30, 
        required=False, 
        help_text="Optional.",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user

class SymptomEntryForm(forms.ModelForm):
    """
    Form for entering symptoms with severity level.
    """
    class Meta:
        model = SymptomEntry
        fields = ['symptom_text', 'severity']
        widgets = {
            'symptom_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Describe your symptoms in detail...'
            }),
            'severity': forms.Select(attrs={
                'class': 'form-control'
            })
        }
        labels = {
            'symptom_text': 'Symptom Description',
            'severity': 'Severity Level'
        }

