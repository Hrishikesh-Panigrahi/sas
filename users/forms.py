from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from users.models import TeacherProfile
from course.models import Course


class TeacherForm(forms.ModelForm):
    course = forms.ModelMultipleChoiceField(
        queryset=Course.objects.all(), widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = TeacherProfile
        fields = ['department', 'course',
                  'is_classteacher']

    def __init__(self, courseSet, *args, **kwargs):
        super(TeacherForm, self).__init__(*args, **kwargs)
        self.fields['course'].queryset = courseSet
        self.fields['course'].label = 'Courses'


class UserForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'is_staff']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_staff': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.fields['is_staff'].initial = True
        self.fields['is_staff'].disabled = True
        self.fields['password1'].widget = forms.PasswordInput(
            attrs={'class': 'form-control', 'type': 'password'})
        self.fields['password2'].widget = forms.PasswordInput(
            attrs={'class': 'form-control', 'type': 'password'})


class UserUpdateForm(UserChangeForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(UserChangeForm, self).__init__(*args, **kwargs)
        self.fields['password'].initial = ''
        self.fields['password'].help_text = ''
        self.fields['password'].label = ''
