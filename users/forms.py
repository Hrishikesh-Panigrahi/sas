from django.forms import CharField, EmailInput, ModelForm, PasswordInput, TextInput
from users.models import TeacherProfile
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, ReadOnlyPasswordHashField


class TeacherForm(ModelForm):
    class Meta:
        model = TeacherProfile
        fields = ['department', 'course',
                  'is_classteacher']


class UserForm(UserCreationForm):
    pass_htext = [
        "Your password can’t be too similar to your other personal information.",
        "Your password must contain at least 8 characters.",
        "Your password can’t be a commonly used password.",
        "Your password can’t be entirely numeric."
    ]

    password1 = CharField(
        label="Password",
        widget=PasswordInput(
            attrs={'class': 'form-control', 'type': 'password'}
        ),
        help_text='<ul> <li>{}</li> <li>{}</li> <li>{}</li> <li>{}</li> </ul>'.format(
            pass_htext[0], pass_htext[1], pass_htext[2], pass_htext[3]),
        # error_messages=
    )
    password2 = CharField(
        label="Confirm password",
        widget=PasswordInput(
            attrs={'class': 'form-control', 'type': 'password'}
        )
    )

    class Meta:
        model = User
        fields = ['username', 'first_name',
                  'last_name', 'is_staff', 'password1', 'password2']
        widgets = {
            'username': TextInput(attrs={'class': 'form-control'}),
            'first_name': TextInput(attrs={'class': 'form-control'}),
            'last_name': TextInput(attrs={'class': 'form-control'}),
        }

    # def __init__(self, *args, **kwargs):
    #     super(UserForm, self).__init__(*args, **kwargs)
    #     self.fields['is_staff'].initial = True
    #     self.fields['is_staff'].disabled = True


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
