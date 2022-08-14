from django.db import models
from cls.models import Class
from course.models import Course
from student.models import student
from users.models import User, TeacherProfile
# attendance models

# Create your models here.

time_slots = (
        ('9:30 - 10:30', '9:30 - 10:30'),
        ('10:30 - 11:30', '10:30 - 11:30'),
        ('11:30 - 12:30', '11:30 - 12:30'),
        ('12:30 - 1:30', '12:30 - 1:30'),
        ('2:30 - 3:30', '2:30 - 3:30'),
        ('3:30 - 4:30', '3:30 - 4:30'),
        ('4:30 - 5:30', '4:30 - 5:30'),
    )

day_choices = (
        ('Monday','Monday'),
        ('Tuesday','Tuesday'),
        ('Wednesday','Wednesday'),
        ('Thursday','Thursday'),
        ('Friday','Friday')
    )

class Assign_cls(models.Model):
    cls = models.ForeignKey(Class, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE)

    class Meta:
        unique_together = (('cls', 'course', 'teacher'),)

    def __str__(self):
        cl = Class.objects.get(id=self.cls_id)
        cr = Course.objects.get(id=self.course_id)
        te = TeacherProfile.objects.get(id=self.teacher_id)
        return '%s : %s : %s' % (te, cr.name, cl)

class AssignTime(models.Model):
    assign = models.ForeignKey(Assign_cls, on_delete=models.CASCADE)
    period = models.CharField(max_length=50, choices=time_slots, default='11:00 - 11:50')
    day = models.CharField(max_length=15, choices=day_choices)


class AttendanceClass(models.Model):
    assign = models.ForeignKey(Assign_cls, on_delete=models.CASCADE)
    date = models.DateField(default='2022-10-23')
    status = models.IntegerField(default=0)
    

    class Meta:
        verbose_name = 'Attendance'
        verbose_name_plural = 'Attendance'


class Attendance(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, default=1)
    student = models.ForeignKey(student, on_delete=models.CASCADE, default=1)
    date = models.DateField(default='2022-10-23')
    attendanceclass = models.ForeignKey(
        AttendanceClass, on_delete=models.CASCADE, default=1)
    status = models.BooleanField(default='True')

    def __str__(self):
        sname = student.objects.get(id=self.student_id)
        cname = Course.objects.get(name=self.course)
        return '%s : %s' % (sname.user.first_name, cname)