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
    context = {'userform': userform, 'type' : 'Register'}
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
    userform = UserForm(instance=stu.user)
    sform = StudentForm(instance=stu)
    if request.method=='POST':
        userform = UserForm(request.POST, instance=stu.user)
        sform = UserForm(request.POST, instance=stu)
        try: 
            if userform.is_valid():
                userform.save()
                if sform.is_vaild():
                    sform.save()
                    print('student saved')
                    return redirect('')
        except Exception as e:
            pass
            
    context = { 'userform': userform,
                'sform': sform, 
                'type' : 'Update', 
                'id': stu.id}

    return render(request, 'student/studentRegister.html ' , context)