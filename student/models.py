# from django.contrib.auth.models import User
from users.models import User
from django.db import models
from course.models import Course
from cls.models import Class


# User -> username, first_name, last_name, password, email, is_staff, is_active, is_superuser, date_created
#         last_login/last_updated

# auth_session, auth_users, auth_active,

# Create your models here.


class student(models.Model):

    department_choices = [
        ('Computer Engineering', 'Computer Engineering'),
        ('Electronics and Telecommunication Engineering',
         'Electronics and Telecommunication Engineering'),
        ('Information Technology', 'Information Technology'),
        ('Mechanical Engineering', 'Mechanical Engineering'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    department = models.CharField(
        max_length=100, null=True, choices=department_choices)
    roll_no = models.IntegerField(null=True)
    # email= models.EmailField()
    # id = (str(roll_no)+str(DOB))
    # attendance=something
    id = models.BigAutoField(primary_key=True)
    course = models.ManyToManyField(Course)
    cls = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return str(self.id) + " " + self.user.username
