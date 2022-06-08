from django.forms import ModelForm
from course.models import Course
from users.models import TeacherProfile
from django.contrib.auth.models import User

class TeacherForm(ModelForm):
    class Meta:
        model = TeacherProfile
        fields = ['teacherID', 'department', 'course',
                  'is_classteacher']

class UserForm(ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email',
                  'password', 'is_staff']
