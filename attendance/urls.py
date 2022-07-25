from django.urls import path
from . import views

urlpatterns = [
    path('<str:pk>/attendance/class', views.attendanceclass, name='attendance-class'),
    path('<str:pk>/attendance/class/<str:assign_id>/', views.attendance ,name='attendance-attendance_class'),
    path('attendance/<str:attendancecls_id>/', views.stu_list ,name='attendance'),
]
