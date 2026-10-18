from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='leave'),
    path('<int:pk>/review', views.review, name='leave-review'),
    path('<int:pk>/cancel', views.cancel, name='leave-cancel'),
    path('<int:pk>/document', views.document, name='leave-document'),
]
