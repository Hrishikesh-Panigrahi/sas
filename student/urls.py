from django.urls import path
from . import views

urlpatterns = [
    path('StudentRegister', views.register, name='StudentRegister'),
    path('Students', views.studentList, name='StudentList'),
    path('DeleteStudent/<str:pk>', views.delete, name='deleteStudent'),
    path('UpdateStudent/<str:pk>', views.update, name='UpdateStudent'),
]
