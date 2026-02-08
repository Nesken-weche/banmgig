from django.urls import path
from . import views

urlpatterns = [
    path('', views.kreyate_signup, name='kreyate_signup'),
    path('account/', views.user_login_signup, name='user_login_signup'),
]