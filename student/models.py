from users.models import User
from django.db import models
from django.db.models import F
from course.models import Course
from cls.models import Class

# Create your models here.

class student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    roll_no = models.IntegerField(null=True, blank=True)
    # email= models.EmailField()
    # id = (str(roll_no)+str(DOB))
    # attendance=something
    id = models.BigAutoField(primary_key=True)
    course = models.ManyToManyField(Course, blank=True)
    cls = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return str(self.user)


# Roll number first (students without one last, on every database), then name.
ROLL_ORDER = (F('roll_no').asc(nulls_last=True), 'user__first_name', 'user__last_name')
