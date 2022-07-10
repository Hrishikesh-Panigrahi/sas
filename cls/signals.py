from turtle import position
from urllib import request
from django.dispatch import receiver
from django.db.models.signals import post_save
from .models import Class
from student.models import student, AssignCourse
from course.models import Course



@receiver(post_save, sender=Class)
def create_class(sender, instance, created, **kwargs):
    if created:
        # print('hello')
        # print(instance.course)
        # AssignCourse.objects.create(cls=instance, course=instance.course)
        # student.objects.update(course=instance.course)
        print("saved")

        # stu=student.objects.(cls__class_name=instance.class_name)
        # print(stu)

# assign couse-> 1) class_name foreign
                # 2) course   for
                # 3) stu      many yto many