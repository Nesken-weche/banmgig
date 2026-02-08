from django.shortcuts import render

# Create your views here.

def kreyate_signup(request):
    return render(request, 'kreyate/kreyate_signup.html')

def user_login_signup(request):
    return render(request, 'kreyate/user_signup_login.html')