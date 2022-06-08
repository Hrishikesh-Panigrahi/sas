from django.shortcuts import redirect, render
from django.http import HttpResponse
from .forms import UserForm, TeacherForm
from django.contrib.auth.models import User
from .models import TeacherProfile
from django.contrib.auth.forms import UserCreationForm


def register(request):
    page = 'User'
    userForm = UserForm()  # USer Model - form

    if request.method == 'POST':
        userForm = UserForm(request.POST)
        print('not yet valid')
        if userForm.is_valid():
            print('valid')
            try:
                userForm.save()
                u = User.objects.get(username=request.POST['username'])
                print('user saved')
                t = TeacherProfile(user=u)
                t.save()
            except Exception as e:
                print('user not saved')
                print(e)
            print('h4')
    context = {'form': userForm, 'page': page}
    return render(request, 'users/register.html', context)
