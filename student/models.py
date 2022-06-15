from django.contrib.auth.models import User
from django.db import models
from course.models import Course


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
    # name =models.CharField(max_length=30)
    # div = models.CharField(max_length=2)
    department = models.CharField(
        max_length=100, null=True, choices=department_choices)
    roll_no = models.IntegerField(null=True)
    DOB = models.DateField(null=True)
    address = models.TextField(null=True)
    # email= models.EmailField()
    # id = (str(roll_no)+str(DOB))
    # attendance=something
    id = models.BigAutoField(primary_key=True)
    # course = models.ManyToManyField(
    #     "course.Course", verbose_name=("Enrolled Course"))
    course = models.ManyToManyField(Course)
    def __str__(self):
        return str(self.id) + " " + self.user.username
