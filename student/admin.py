from django.contrib import admin

from student.models import student, AssignCourse

# Register your models here.
admin.site.register(student)
admin.site.register(AssignCourse)
