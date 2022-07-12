from django.db import models
from cls.models import Class
from course.models import Course
from student.models import student
from users.models import User, TeacherProfile
#attendance models

# Create your models here.
class Assign_cls(models.Model):
    cls=models.ForeignKey(Class, on_delete=models.CASCADE)
    course=models.ForeignKey(Course, on_delete=models.CASCADE )
    teacher= models.ForeignKey(TeacherProfile, on_delete=models.CASCADE)

    class Meta:
        unique_together = (('cls', 'course', 'teacher'),)

    def __str__(self):
        cl = Class.objects.get(id=self.cls_id)
        cr = Course.objects.get(id=self.course_id)
        te = TeacherProfile.objects.get(id=self.teacher_id)
        return '%s : %s : %s' % (te, cr.name, cl)

class AttendanceClass(models.Model):
    assign=models.ForeignKey(Assign_cls, on_delete=models.CASCADE)
    status = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Attendance'
        verbose_name_plural = 'Attendance'
    

class Attendance(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, default=1)
    student = models.ForeignKey(student, on_delete=models.CASCADE, default=1)
    attendanceclass = models.ForeignKey(AttendanceClass, on_delete=models.CASCADE, default=1)
    status = models.BooleanField(default='True')

    def __str__(self):
        sname = student.objects.get(id=self.student_id)
        cname = Course.objects.get(name=self.course)
        return '%s : %s' % (sname.user.first_name, cname)
     
