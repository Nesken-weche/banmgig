from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('gig-creation/', views.gig_creation, name='gig_creation'),
]