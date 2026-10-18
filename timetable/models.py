from django.conf import settings
from django.db import models
from course.models import Course
from cls.models import Class
from users.models import TeacherProfile


class TimeTable(models.Model):
    """One weekly slot in a class's timetable."""

    lec_choices = (
        ('Lecture', 'Lecture'),
        ('Lab', 'Lab')
    )

    batch_choices = (
        ('All', 'All'),
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
    )

    day_choices = (
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday')
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
        return '%s %s %s-%s' % (self.cls, self.day, self.start_time, self.end_time)

    @property
    def period(self):
        return '%s - %s' % (self.start_time.strftime('%H:%M'), self.end_time.strftime('%H:%M'))


class Substitution(models.Model):
    """A colleague covering one timetabled lecture for an absent teacher on a date."""
    slot = models.ForeignKey(TimeTable, on_delete=models.CASCADE, related_name='substitutions')
    date = models.DateField()
    absent_teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='+')
    substitute = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='substitutions')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('slot', 'date'),)

    def __str__(self):
        return '%s covers %s on %s' % (self.substitute, self.slot, self.date)
