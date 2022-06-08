from dataclasses import fields
from pyexpat import model
from django.forms import ModelForm
from course.models import Course
from users.models import TeacherProfile
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class TeacherForm(ModelForm):
    class Meta:
        model = TeacherProfile
        fields = ['department', 'course',
                  'is_classteacher']


# class UserForm(ModelForm):
#     class Meta:
#         model = User
#         fields = ['username', 'first_name', 'last_name', 'email',
#                   'password1', 'password2', 'is_staff']

class UserForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'is_staff']
