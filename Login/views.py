from http import cookies
from urllib import response
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import auth
from django.contrib import messages
# from django.conf import settings

# Create your views here.
def loginUser(request):
    

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
                if 'next' in request.POST:
                    print("hello")
                    return redirect(request.POST.get('next'))
                # if request.POST.get("checkbox", None):
                #     request.session.set_expiry(settings.KEEP_LOGGED_DURATION)
                #     response = redirect('/Dashboard')
                #     response.set_cookie('email', request.POST['email'])
                #     response.set_cookie('password', request.POST['password'])
                #     # print(response.set_cookie)
                #     return response
                    
                
                else:
                    return redirect('/dashboard')
               

            else:
                print('account active kar re')

        else:
            messages.info(request, "Check your cerdentials")
        

    return render(request, 'Login\login.html')


def logoutUser(request):
    if request.method =="POST":
        logout(request)
        return redirect("/")