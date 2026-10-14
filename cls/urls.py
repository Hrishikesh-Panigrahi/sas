from django.urls import path
from . import views

urlpatterns = [
    path('', views.AllClass),
    path('view', views.AllClass, name='viewcls'),
    path('creation', views.clsCreation, name='clsCreation'),
    path('<int:id>', views.detail, name='class-detail'),
    path('<int:id>/edit', views.update, name='class-edit'),
    path('<int:id>/delete', views.delete, name='class-delete'),
]
