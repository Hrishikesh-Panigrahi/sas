from django.db import models
from cls.models import Class
from course.models import Course
from student.models import student
from users.models import TeacherProfile


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
    ('Monday', 'Monday'),
    ('Tuesday', 'Tuesday'),
    ('Wednesday', 'Wednesday'),
    ('Thursday', 'Thursday'),
    ('Friday', 'Friday')
)


class Assign_cls(models.Model):
    """A teacher teaching a course to a class."""
    cls = models.ForeignKey(Class, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE)

    class Meta:
        unique_together = (('cls', 'course', 'teacher'),)

    def __str__(self):
        return '%s : %s : %s' % (self.teacher, self.course.name, self.cls)


class AssignTime(models.Model):
    assign = models.ForeignKey(Assign_cls, on_delete=models.CASCADE)
    period = models.CharField(max_length=50, choices=time_slots, default='11:00 - 11:50')
    day = models.CharField(max_length=15, choices=day_choices)
    date = models.DateField(default='2022-10-23')

    class Meta:
        unique_together = (('assign', 'period', 'day'),)

    def __str__(self):
        return str(self.assign)


class AttendanceClass(models.Model):
    """A single lecture for which attendance is taken.

    `status` is 0 until attendance has been marked, then 1.
    `period` is free text so lectures can come from the timetable's own times.
    """
    assign = models.ForeignKey(Assign_cls, on_delete=models.CASCADE)
    period = models.CharField(max_length=50, blank=True, default='')
    day = models.CharField(max_length=15, blank=True, default='')
    date = models.DateField(default='2022-10-23')
    status = models.IntegerField(default=0)
    # "All" for the whole class, or the lab batch ("A", "B", "C") this lecture is for.
    batch = models.CharField(max_length=3, default='All')

    class Meta:
        verbose_name = 'Attendance'
        verbose_name_plural = 'Attendance'

    def __str__(self):
        return '%s on %s %s' % (self.assign, self.date, self.period)

    def students(self):
        """Students expected at this lecture: the whole class, or one lab batch."""
        qs = self.assign.cls.student_set.all()
        return qs if self.batch == 'All' else qs.filter(batch=self.batch)

    @property
    def is_marked(self):
        return self.status == 1


class Attendance(models.Model):
    """One student's presence at one lecture."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, default=1)
    student = models.ForeignKey(student, on_delete=models.CASCADE, default=1)
    date = models.DateField(default='2022-10-23')
    attendanceclass = models.ForeignKey(
        AttendanceClass, on_delete=models.CASCADE, default=1)
    status = models.BooleanField(default=True)

    def __str__(self):
        return '%s : %s' % (self.student, self.course)
