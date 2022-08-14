from django.dispatch import receiver
from django.db.models.signals import post_save
from django.utils import timezone
import datetime

from attendance.models import Assign_cls, AttendanceClass

@receiver(post_save, sender = Assign_cls)
def creater_attendanceclass(sender, instance, created, **kwargs):
    if created:
        now1 = datetime.date.today()

        att, created = AttendanceClass.objects.update_or_create(assign = instance, date = now1)
        att.save()
        # AttendanceClass.objects.create(assign = instance)


# @receiver(post_save, sender = Assign_cls)
# def update_attendanceclass(sender, instance, created, **kwargs):
#     now1 = datetime.date.today()

#     att, created = AttendanceClass.objects.update_or_create(assign = instance, date = now1)
#     att.save()
#     print('hello2')