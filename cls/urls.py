from django.urls import path
from . import views

urlpatterns = [
    path('', views.create, name='createClass'),
    path('<int:id>', views.update),
]
