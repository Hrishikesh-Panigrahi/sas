from django.urls import path
from course.views import index, create, update, delete

urlpatterns = [
    # path('', Index.as_view())
    path('', index),
    path('create', create, name='create'),
    path('update/<int:id>', update, name='update'),
    path('delete/<int:id>', delete, name='delete')
]
