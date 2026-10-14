from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='teachers'),
    path('profile/', views.profile, name='profile'),
    path('password/', views.password_change, name='password-change'),
    path('update/<int:id>', views.update, name='updateTeacher'),
    path('FacultyRegister', views.register, name='FacultyRegister'),
    path('delete/<int:id>', views.delete, name='deleteTeacher'),
]
