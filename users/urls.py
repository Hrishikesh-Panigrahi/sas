from django.urls import path
from . import views

urlpatterns = [
    path('FacultyRegister', views.register, name= 'FacultyRegister'),
    # path('FacultyDetails/<str:pk>', views.Teacherdetails, name= 'FacultyDetails'),
]