from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Member


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = Member
        fields = ("username", "first_name", "last_name", "email", "callsign", "password1", "password2")
