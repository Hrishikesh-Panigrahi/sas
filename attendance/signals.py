from django.dispatch import receiver
from django.db.models.signals import post_save
from django.utils import timezone
import datetime

from attendance.models import Assign_cls, AssignTime, AttendanceClass

@receiver(post_save, sender = AssignTime)
def creater_attendanceclass(sender, instance, created, **kwargs):
    if created:
        ass = Assign_cls.objects.get()
        now1 = datetime.date.today()

        att, created = AttendanceClass.objects.update_or_create(assign = instance, date = now1)
        att.save()