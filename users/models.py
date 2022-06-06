from tkinter import CASCADE
from django.db import models
from django.contrib.auth.models import User, auth
# Create your models here.

class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # name = models.CharField(max_length=50)
    teacherID = models.IntegerField(unique=True, null=True)
    department = models.CharField(max_length=50, blank=True, null=True)
    course = models.CharField(max_length=50, blank=True, null=True)
    semester = models.CharField(max_length=50, blank=True, null=True)
    is_classteacher = models.BooleanField(default=False)

    def __str__(self):
        return str(self.teacherID)+ ' ' +self.user.first_name+ ' ' +self.user.last_name