from .models import User, TeacherProfile
from student.models import student
from django.dispatch import receiver
from django.db.models.signals import post_save

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        print("hello")
        print(instance)
        if instance.is_staff == True:
            print("Hellp")
            print(instance)
            TeacherProfile.objects.create(user=instance)
            print("saved")

        if not instance.is_staff:
            print("Hellp2")
            s = student(user=instance)
            # student.objects.create(user=instance)
            s.save()
            print(student.objects.filter(user=instance))
            print("saved")


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if instance.is_staff == True :
        try:
            teacher_profile = TeacherProfile.objects.get(user=instance)
        except TeacherProfile.DoesNotExist:
            TeacherProfile.objects.create(user=instance)
        else:
            teacher_profile.save()
        # teacher, created = TeacherProfile.objects.update_or_create(user=instance)
        # teacher.save()
    elif not instance.is_staff:
        try:
            print("hello12")
            student_profile = student.objects.get(user=instance)
        except student.DoesNotExist:
            student.objects.create(user=instance)
            print(instance)
        else:
            student_profile.save()
        # stu, created = student.objects.update_or_create(user=instance)
        # stu.save()
        # print(stu)


# @receiver(post_save, sender=User)
# def save_user_profile(sender, instance, **kwargs):
#     print(instance)
#     if instance.is_staff == True:
#         try:
#             print("ins")
#             TeacherProfile.objects.get(user=instance).delete()
#         except:
#             pass
#     if not instance.is_staff:
#         try:
#             print("inswer")
#             student.objects.get(user=instance).delete()
#         except:
#             pass