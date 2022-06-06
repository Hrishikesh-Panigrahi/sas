from django.urls import path
from course.views import index, create, update

urlpatterns = [
    # path('', Index.as_view())
    path('', index),
    path('create', create, name='create'),
    path('update/<int:id>', update, name='update')
]
