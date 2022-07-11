from django import forms
from .models import student
from course.models import Course
from users.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm


class StudentForm(forms.ModelForm):
    my_form = 'userForm'
    course = forms.ModelMultipleChoiceField(
        required=False,
        queryset=Course.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'form': my_form}),
        # widget=forms.CheckboxSelectMultiple()
    )
    class Meta:
        # my_form = 'userForm'
        model = student
        fields = [ 'course']
        # widgets = {
    
        #     'department': forms.HiddenInput(),
        # #     # 'course': forms.CheckboxSelectMultiple(attrs={'form': my_form}),
        # #     'address': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
        # #     'DOB': forms.DateField(attrs={'class': 'form-control', 'form': my_form}),
        # }
    
    def __init__(self, *args, **kwargs):
        courseSet = kwargs.pop('courseSet')
        d = kwargs.pop('dept', None)
        super(StudentForm, self).__init__(*args, **kwargs)
        self.fields['course'].queryset = courseSet
        self.fields['course'].label = 'Courses'
        # self.fields['department'].initial = d
    
       

class UserForm(UserCreationForm):
    class Meta:
        my_form = 'userForm'
        model = User
        
        fields = [ 'email', 'first_name', 'last_name' ]
        widgets = {
            'email': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
        }
        # widgets = {
        #     'email': forms.TextInput(attrs={'class': 'form-control'}),
        #     'first_name': forms.TextInput(attrs={'class': 'form-control'}),
        #     'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        # }

    def __init__(self, *args, **kwargs):
        my_form = 'userForm'
        super(UserForm, self).__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(
            attrs={'class': 'form-control', 'type': 'password', 'form': my_form})
        self.fields['password2'].widget = forms.PasswordInput(
            attrs={'class': 'form-control', 'type': 'password', 'form': my_form})


class UserUpdateForm(UserChangeForm):
    class Meta:
        my_form = 'userForm'
        model = User
        fields = [ 'first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'form': my_form}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'form': my_form}),
        }

    def __init__(self, *args, **kwargs):
        super(UserChangeForm, self).__init__(*args, **kwargs)
        self.fields['password'].initial = ''
        self.fields['password'].help_text = ''
        self.fields['password'].label = ''