from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('gig-creation/', views.gig_creation, name='gig_creation'),
    path('gig/<str:gig_id>/', views.gig_detail, name='gig_detail'),
]