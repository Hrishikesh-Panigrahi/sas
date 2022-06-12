from django import forms
from .models import student
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class UserForm(UserCreationForm):
    email = forms.EmailField(label = "Email")
    first_name = forms.CharField(label = "First name")
    last_name = forms.CharField(label = "Last name")

    class meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']

