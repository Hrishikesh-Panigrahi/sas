# Create your models here.
from django.contrib.auth.models import User
from django.db import models
from course.models import Course
from users.models import TeacherProfile


# User -> username, first_name, last_name, password, email, is_staff, is_active, is_superuser, date_created
#         last_login/last_updated

# auth_session, auth_users, auth_active,

# Create your models here.




# class TimeTable(models.Model):
    
'''time_slots = (
    ('9:30 - 10:30', '9:30 - 10:30'),
    ('10:30 - 11:30', '10:30 - 11:30'),
    ('11:30 - 12:30', '11:30 - 12:30'),
    ('12:30 - 1:30', '12:30 - 1:30'),
    ('2:30 - 3:30', '2:30 - 3:30'),
    ('3:30 - 4:30', '3:30 - 4:30'),
    ('4:30 - 5:30', '4:30 - 5:30'),
)

DAYS_OF_WEEK = (
    ('Monday', 'Monday'),
    ('Tuesday', 'Tuesday'),
    ('Wednesday', 'Wednesday'),
    ('Thursday', 'Thursday'),
    ('Friday', 'Friday'),
    ('Saturday', 'Saturday'),
)'''
#     semester = 
#     department =
#     meetingtime =
#     course = models.ForeignKey()
#     faculty = forignkey
#     day =

#     def __str__(self):
#         return str(self.id)
