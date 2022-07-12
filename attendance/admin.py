from datetime import timedelta, datetime

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponseRedirect
from django.urls import path


from .models import Assign_cls, Attendance, AttendanceClass

# Register your models here.
class AssignAdmin(admin.ModelAdmin):
    list_display = ('cls', 'course', 'teacher')
    search_fields = ('cls', 'course', 'course__name', 'teacher__user__firstname', 'course__code')
    ordering = ['cls',  'course__id']
    raw_id_fields = ['cls', 'course', 'teacher']


class AttendanceClassAdmin(admin.ModelAdmin):
    list_display = ('assign', 'status')
    ordering = ['assign']
    

    '''def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(),
        ]
        return my_urls + urls'''


admin.site.register(Assign_cls, AssignAdmin)
admin.site.register(AttendanceClass, AttendanceClassAdmin)
admin.site.register(Attendance)

# Register your models here.
