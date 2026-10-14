from django.urls import path
from . import views

urlpatterns = [
    path('', views.studentList),
    path('StudentRegister', views.register, name='StudentRegister'),
    path('Students', views.studentList, name='StudentList'),
    path('<int:pk>', views.detail, name='student-detail'),
    path('DeleteStudent/<int:pk>', views.delete, name='deleteStudent'),
    path('UpdateStudent/<int:pk>', views.update, name='UpdateStudent'),
]
