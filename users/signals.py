from .models import User, TeacherProfile
from student.models import student
from django.dispatch import receiver
from django.db.models.signals import post_save


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, **kwargs):
    """Staff users get a TeacherProfile, everyone else a student profile.

    A profile that no longer matches (e.g. after `is_staff` is toggled in the
    admin) is kept rather than deleted, because deleting it would cascade to
    that person's class assignments and attendance records. Lists filter on
    `is_staff`, so the stale profile simply stops appearing.
    """
    if instance.is_staff:
        TeacherProfile.objects.get_or_create(user=instance)
    else:
        student.objects.get_or_create(user=instance)
