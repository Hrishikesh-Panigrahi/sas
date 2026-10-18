from django.contrib import admin

from .models import LeaveRequest


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('student', 'kind', 'start_date', 'end_date', 'status', 'reviewed_by')
    list_filter = ('status', 'kind')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'reason')
