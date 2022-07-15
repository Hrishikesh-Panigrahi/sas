from django.urls import path
from . import views

urlpatterns = [
    path('<str:pk>', views.attendanceclass, name='attendance-class'),
    path('<str:pk>/course/<str:co>', views.attendancecourse, name='attendance-course'),

]
