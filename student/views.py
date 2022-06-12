from django.shortcuts import redirect, render
from .forms import UserForm,  StudentForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import student
from django.http import HttpResponse


def register(request):
    context = {}
    # studentForm=StudentForm(request.POST)
    userform = UserForm(request.POST)
    if request.method=='POST':
        userform = UserForm(request.POST)
        if userform.is_valid():
            userform.save()
            u = User.objects.get(username=request.POST['username'])
            stu = student(user = u)
            print('student saved')
            stu.save()
            return redirect("/")
    context = {'form': userform}
    return render(request, 'student/studentRegister.html ' , context)


def studentList(request):
    stu = student.objects.all()

    context = {'student' : stu}
    return render(request, 'student/Studentlist.html', context)


def delete(request, pk):
    stu = student.objects.get(id = pk)
    context = {}
    if request.method == 'POST':
        user = stu.user
        stu.delete()
        user.delete()
        return redirect("/")
            
    context = {'id': stu.id, 'type' : 'delete'}

    return render(request, 'student/delete.html ' , context)



def update(request, pk):
    stu = student.objects.get(id = pk)
    context = {}
    form = UserForm(instance=stu.user)
    if request.method=='POST':
        form = UserForm(request.POST, instance=stu.user)
        if form.is_valid():
            form.save()
            print('student saved')
            
    context = {'form': form, 'type' : 'Update', 'id': stu.id}

    return render(request, 'student/studentRegister.html ' , context)