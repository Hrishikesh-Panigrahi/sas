from users.models import User
from django.db import models
from course.models import Course
from cls.models import Class



# Create your models here.


class student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    roll_no = models.IntegerField(null=True)
    # email= models.EmailField()
    # id = (str(roll_no)+str(DOB))
    # attendance=something
    id = models.BigAutoField(primary_key=True)
    course = models.ManyToManyField(Course)
    cls = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return str(self.user.first_name) + " " + str(self.user.last_name)
