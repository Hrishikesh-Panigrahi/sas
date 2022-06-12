from django import forms
from .models import student
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class StudentForm(forms.ModelForm):
    class Meta:
        # my_form = 'userForm'
        model = student
        fields = ['department',
                  'DOB', 'address']
        # widgets = {
        #     'department': forms.Select(attrs={'form': my_form}),
        #     # 'course': forms.CheckboxSelectMultiple(attrs={'form': my_form}),
        #     'address': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
        #     'DOB': forms.DateField(attrs={'class': 'form-control', 'form': my_form}),
        # }

    
       

class UserForm(UserCreationForm):
    class Meta:
        # my_form = 'userForm'
        model = User
        
        fields = ['username', 'first_name', 'last_name']
        # widgets = {
        #     'username': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
        #     'first_name': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
        #     'last_name': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
            
        # }

    # def __init__(self, *args, **kwargs):
    #     my_form = 'userForm'
    #     super(UserForm, self).__init__(*args, **kwargs)
    #     self.fields['password1'].widget = forms.PasswordInput(
    #         attrs={'class': 'form-control', 'type': 'password', 'form': my_form})
    #     self.fields['password2'].widget = forms.PasswordInput(
    #         attrs={'class': 'form-control', 'type': 'password', 'form': my_form})
