from django import forms
# from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from users.models import TeacherProfile
from users.models import User
from course.models import Course


class TeacherForm(forms.ModelForm):
    my_form = 'userForm'
    course = forms.ModelMultipleChoiceField(
        queryset=Course.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'form': my_form}),
    )

    class Meta:
        my_form = 'userForm'
        model = TeacherProfile
        fields = ['department', 'course']
        widgets = {
            'department': forms.Select(attrs={'form': my_form}),
            # 'course': forms.CheckboxSelectMultiple(attrs={'form': my_form}),
        }

    def __init__(self, *args, **kwargs):
        courseSet = kwargs.pop('courseSet')
        super(TeacherForm, self).__init__(*args, **kwargs)
        self.fields['course'].queryset = courseSet
        self.fields['course'].label = 'Courses'


class UserForm(UserCreationForm):

    class Meta:
        my_form = 'userForm'
        model = User
        # fields = ['username', 'is_staff']
        fields = [ 'email', 'first_name', 'last_name', 'is_staff', 'is_classteacher']
        widgets = {
            # 'username': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'form': my_form}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
            'is_staff': forms.HiddenInput(attrs={'form': my_form}),
            'is_classteacher': forms.CheckboxInput(attrs={'form': my_form}),    
        }

    def __init__(self, *args, **kwargs):
        my_form = 'userForm'
        super(UserForm, self).__init__(*args, **kwargs)
        self.fields['is_staff'].initial = True
        self.fields['is_staff'].disabled = True
        self.fields['password1'].widget = forms.PasswordInput(
            attrs={'class': 'form-control', 'type': 'password', 'form': my_form})
        self.fields['password2'].widget = forms.PasswordInput(
            attrs={'class': 'form-control', 'type': 'password', 'form': my_form})


class UserUpdateForm(UserChangeForm):
    class Meta:
        my_form = 'userForm'
        model = User
        fields = [ 'first_name', 'last_name', 'email', 'is_classteacher']
        widgets = {
            # 'username': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'form': my_form}),
        }

    def __init__(self, *args, **kwargs):
        super(UserChangeForm, self).__init__(*args, **kwargs)
        self.fields['password'].initial = ''
        self.fields['password'].help_text = ''
        self.fields['password'].label = ''
