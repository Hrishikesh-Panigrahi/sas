from django.shortcuts import render
from .forms import UserForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import student
from django.http import HttpResponse
# Create your views here.

def register(request):
    context = {}
    form = UserForm()
    if request.method=='POST':
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()
            u = User.objects.get(username=request.POST['username'])
            stu = student(user = u)
            print('student saved')
            stu.save()
    context = {'form': form}
    return render(request, 'student/studentRegister.html ' , context)


def studentList(request):
    context ={}
    stu = student.objects.all()
    context = {'student' : stu}
    return render(request, 'student/Studentlist.html', context)


def delete(request, pk):

    return HttpResponse("hello")

def update(request, pk):

    return HttpResponse("hello2")