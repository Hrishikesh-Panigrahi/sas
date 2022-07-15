from django.db import models
from course.models import Course
from users.models import TeacherProfile
# from student.models import student

class Class(models.Model):

    department_choices = [
        ('Computer Engineering', 'Computer Engineering'),
        ('Electronics and Telecommunication Engineering',
         'Electronics and Telecommunication Engineering'),
        ('Information Technology', 'Information Technology'),
        ('Mechanical Engineering', 'Mechanical Engineering'),
    ]

    id = models.BigAutoField(primary_key=True)
    class_name = models.CharField(max_length=20, verbose_name='Class Name')
    department = models.CharField(
        max_length=100, null=True, choices=department_choices, blank=True)
    class_teacher = models.OneToOneField(
        TeacherProfile, on_delete=models.SET_NULL, null=True, blank=True)
    # is_timetable= models.BooleanField(default=False)

    def __str__(self):
        return str(self.id) + " " + self.class_name
