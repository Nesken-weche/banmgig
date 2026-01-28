from django.urls import path
from . import views

urlpatterns = [
    path('', views.kreyate_signup, name='kreyate_signup'),
]