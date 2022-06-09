from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('update/<int:id>', views.update, name='updateTeacher'),
    path('FacultyRegister', views.register, name='FacultyRegister'),
    # path('FacultyDetails/<str:pk>', views.Teacherdetails, name= 'FacultyDetails'),
]
