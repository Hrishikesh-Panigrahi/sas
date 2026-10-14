from django.contrib import admin

from .models import Assign_cls, AssignTime, Attendance, AttendanceClass


class AssignAdmin(admin.ModelAdmin):
    list_display = ('cls', 'course', 'teacher')
    search_fields = ('cls__class_name', 'course__name', 'course__code',
                     'teacher__user__first_name', 'teacher__user__last_name')
    ordering = ['cls', 'course__id']
    raw_id_fields = ['cls', 'course', 'teacher']


class AttendanceClassAdmin(admin.ModelAdmin):
    list_display = ('assign', 'date', 'period', 'status')
    list_filter = ('status', 'date')
    ordering = ['-date']


class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'date', 'status')
    list_filter = ('status', 'date')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'course__name')


admin.site.register(Assign_cls, AssignAdmin)
admin.site.register(AttendanceClass, AttendanceClassAdmin)
admin.site.register(Attendance, AttendanceAdmin)
admin.site.register(AssignTime)
