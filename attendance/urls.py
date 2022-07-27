from django.urls import path
from . import views

urlpatterns = [
    path('<str:pk>/attendance/class', views.attendanceclass, name='attendance-class'),
    path('attendance/class/<str:assign_id>/', views.attendance_date ,name='attendance-attendance_date'),
    path('attendance/<str:attendancecls_id>/', views.stu_list ,name='attendance'),
    # path('attendance/<str:attendancecls_id>/confirm', views.confirm_attendance ,name='confirm-attendance'),
]
