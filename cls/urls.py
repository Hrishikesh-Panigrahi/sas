from django.urls import path
from . import views

urlpatterns = [
    path('', views.create, name='createClass'),
    path('<int:id>', views.update),
    path('creation', views.clsCreation, name='clsCreation'),

    path('view', views.AllClass, name='viewcls'),
    # path('<str:name>/courseteachass',views.assigncourse,name='courseteach' )
    
]
