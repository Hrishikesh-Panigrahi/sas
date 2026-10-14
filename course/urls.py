from django.urls import path
from course.views import index, create, update, delete

urlpatterns = [
    path('', index, name='chome'),
    path('create', create, name='course-create'),
    path('update/<int:id>', update, name='course-update'),
    path('delete/<int:id>', delete, name='course-delete'),
]
