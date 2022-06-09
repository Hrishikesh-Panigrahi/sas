from django.db import models
from django.contrib.auth.models import User, auth


class TeacherProfile(models.Model):

    department_choices = [
        ('Computer Engineering', 'Computer Engineering'),
        ('Electronics and Telecommunication Engineering',
         'Electronics and Telecommunication Engineering'),
        ('Information Technology', 'Information Technology'),
        ('Mechanical Engineering', 'Mechanical Engineering'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # name = models.CharField(max_length=50)
    id = models.BigAutoField(primary_key=True)
    department = models.CharField(
        max_length=50, blank=True, null=True, choices=department_choices)
    course = models.CharField(max_length=50, blank=True, null=True)
    is_classteacher = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return str(self.id) + ' ' + self.user.first_name + ' ' + self.user.last_name
