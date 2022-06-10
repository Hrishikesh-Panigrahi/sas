from django.urls import path
from . import views

urlpatterns = [
    path('StudentRegister', views.register, name='StudentRegister'),
]
