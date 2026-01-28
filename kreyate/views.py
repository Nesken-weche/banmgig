from django.shortcuts import render

# Create your views here.

def kreyate_signup(request):
    return render(request, 'kreyate/kreyate_signup.html')
