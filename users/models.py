from tkinter import CASCADE
from django.db import models
from django.contrib.auth.models import User, auth


class TeacherProfile(models.Model):
    sem_choices = [
        (1, '1'),
        (2, '2'),
        (3, '3'),
        (4, '4'),
        (5, '5'),
        (6, '6'),
        (7, '7'),
        (8, '8')
    ]

    department_choices = [
        ('Computer Engineering', 'Computer Engineering'),
        ('Electronics and Telecommunication Engineering',
         'Electronics and Telecommunication Engineering'),
        ('Information Technology', 'Information Technology'),
        ('Mechanical Engineering', 'Mechanical Engineering'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # name = models.CharField(max_length=50)
    teacherID = models.IntegerField(unique=True, null=True)
    department = models.CharField(max_length=50, blank=True, null=True, choices=department_choices)
    course = models.CharField(max_length=50, blank=True, null=True)
    semester = models.CharField(max_length=50, blank=True, null=True, choices=sem_choices)
    is_classteacher = models.BooleanField(default=False)

    def __str__(self):
        return str(self.teacherID)+ ' ' +self.user.first_name+ ' ' +self.user.last_name

