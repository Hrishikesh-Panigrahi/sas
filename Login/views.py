from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import auth
from django.contrib import messages

# Create your views here.
def login(request):
    # context={ 'page' : 'Login' }
    if request.method == 'POST':
        email= request.POST['email']
        password= request.POST['password']
        user = auth.authenticate(email=email, password=password)
        if user is not None:
            if user.is_active:
                # if user.is_staff:
                auth.login(request, user)
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