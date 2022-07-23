from django.urls import path
from . import views

urlpatterns = [
    path('<str:pk>/attendance/class', views.attendanceclass, name='attendance-class'),
    # path('<str:pk>/attendance/class/<str:co>', views.attendancecourse, name='attendance-course'),
    path('<str:pk>/attendance/class/<str:cls_id>/', views.attendance ,name='attendance')
]
