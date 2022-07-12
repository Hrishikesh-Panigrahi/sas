# Create your models here.
# from django.contrib.auth.models import User
from django.db import models
from course.models import Course
from users.models import TeacherProfile, User
from cls.models import Class 


# User -> username, first_name, last_name, password, email, is_staff, is_active, is_superuser, date_created
#         last_login/last_updated

# auth_session, auth_users, auth_active,

# Create your models here.


class TimeTable(models.Model):
    lec_choices = (
        ('Lecture', 'Lecture'),
        ('Lab', 'Lab')
    )

    batch_choices = (
        ('All','All'),
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
    )

    day_choices = (
        ('Monday','Monday'),
        ('Tuesday','Tuesday'),
        ('Wednesday','Wednesday'),
        ('Thursday','Thursday'),
        ('Friday','Friday')
    )

    id = models.BigAutoField(primary_key=True)
    cls = models.ForeignKey(Class, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, null=True, on_delete=models.SET_NULL)
    lec_type = models.CharField(choices=lec_choices, max_length=7)
    batch = models.CharField(choices=batch_choices, max_length=3)
    day = models.CharField(choices=day_choices, max_length=9)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return self.id



# class TimeTable(models.Model):
    
#     time_slots = (
#         ('9:30 - 10:30', '9:30 - 10:30'),
#         ('10:30 - 11:30', '10:30 - 11:30'),
#         ('11:30 - 12:30', '11:30 - 12:30'),
#         ('12:30 - 1:30', '12:30 - 1:30'),
#         ('2:30 - 3:30', '2:30 - 3:30'),
#         ('3:30 - 4:30', '3:30 - 4:30'),
#         ('4:30 - 5:30', '4:30 - 5:30'),
#     )

#     DAYS_OF_WEEK = (
#         ('Monday', 'Monday'),
#         ('Tuesday', 'Tuesday'),
#         ('Wednesday', 'Wednesday'),
#         ('Thursday', 'Thursday'),
#         ('Friday', 'Friday'),
#         ('Saturday', 'Saturday'),
#     )
#     # relationship with class 
#     cls= models.ForeignKey(Class, on_delete=models.CASCADE)
#     # relationship with faculty
#     faculty=models.ForeignKey(TeacherProfile, on_delete=models.CASCADE)
#     # relationship with course
#     course = models.ForeignKey(Course, on_delete=models.CASCADE)

#     day = models.CharField(max_length=100, choices=DAYS_OF_WEEK)
#     slot = models.CharField(max_length=100, choices=time_slots)

#     def __str__(self):
#         return str(self.id)

