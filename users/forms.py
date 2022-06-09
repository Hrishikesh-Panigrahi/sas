from django.forms import CharField, EmailInput, HiddenInput, ModelForm, PasswordInput, TextInput
from users.models import TeacherProfile
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm


class TeacherForm(ModelForm):
    class Meta:
        model = TeacherProfile
        fields = ['department', 'course',
                  'is_classteacher']


class UserForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'is_staff']
        widgets = {
            'username': TextInput(attrs={'class': 'form-control'}),
            'first_name': TextInput(attrs={'class': 'form-control'}),
            'last_name': TextInput(attrs={'class': 'form-control'}),
            'is_staff': HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.fields['is_staff'].initial = True
        self.fields['is_staff'].disabled = True
        self.fields['password1'].widget = PasswordInput(
            attrs={'class': 'form-control', 'type': 'password'})
        self.fields['password2'].widget = PasswordInput(
            attrs={'class': 'form-control', 'type': 'password'})


class UserUpdateForm(UserChangeForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': TextInput(attrs={'class': 'form-control'}),
            'first_name': TextInput(attrs={'class': 'form-control'}),
            'last_name': TextInput(attrs={'class': 'form-control'}),
            'email': EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(UserChangeForm, self).__init__(*args, **kwargs)
        self.fields['password'].initial = ''
        self.fields['password'].help_text = ''
        self.fields['password'].label = ''
