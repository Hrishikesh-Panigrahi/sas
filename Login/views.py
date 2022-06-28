from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import auth
from django.contrib import messages

# Create your views here.
def login(request):
    context={ 'page' : 'Login' }
    if request.method == 'POST':
        email= request.POST['email']
        password= request.POST['password']
        user = auth.authenticate(email=email, password=password)
        if user is not None:
            if user.is_active:
                auth.login(request, user)

                return HttpResponse("hello world")

        else:
            print('account active kar re')

    else:
        messages.info(request, "Check your cerdentials")
        # return render(request, 'Login/login-page.html')

    return render(request, 'Login\login.html', context)