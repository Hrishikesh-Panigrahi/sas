from http import cookies
from urllib import response
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import auth
from django.contrib import messages
# from django.conf import settings
# Create your views here.
def loginUser(request):
    # context={ 'page' : 'Login' }

    # if request.COOKIES.get("email"):
    #     return render(request, 'Login\login.html', {'cookies1': request.COOKIES['email'], 'cookies2': request.COOKIES['password']})
        
    if request.method == 'POST':
        email= request.POST['email']
        password= request.POST['password']
        user = auth.authenticate(email=email, password=password)
        if user is not None:
            if user.is_active:
                # if user.is_staff:
                auth.login(request, user)
                # if request.POST.get("checkbox", None):
                #     request.session.set_expiry(settings.KEEP_LOGGED_DURATION)
                #     response = redirect('/Dashboard')
                #     response.set_cookie('email', request.POST['email'])
                #     response.set_cookie('password', request.POST['password'])
                #     # print(response.set_cookie)
                #     return response
                print("hello")
                # if request.user.is_staff:
                    # context.update(subjectTeacher = 'subjectTeacher')
                return redirect('/Dashboard')
                # return render (request, 'blank.html', context)

            else:
                print('account active kar re')

        else:
            messages.info(request, "Check your cerdentials")
        # return render(request, 'Login/login-page.html')

    return render(request, 'Login\login.html')