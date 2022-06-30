from multiprocessing import context
from django.shortcuts import redirect, render

from course.models import Course
from .forms import UserForm,  StudentForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import student
from course.models import Course
from django.http import HttpResponse
# from django.contrib.auth.decorators import login_required

# @login_required(login_url='Login')
def register(request):
    context = {}
    # studentForm=StudentForm(request.POST)
    userform = UserForm(request.POST)
    courses = Course.objects.all()
    studentForm = StudentForm(courseSet=courses)
    if request.method == 'POST':
        userform = UserForm(request.POST)
        print('1')
        # studentForm = StudentForm(request.POST ,courseSet=course)
        if userform.is_valid():
            userform.save()
            c_ids = request.POST.getlist('course')
            print('2')
            
            s = User.objects.get(username=request.POST['username'])
            stu = student(user=s)
            print(c_ids)
            for i in c_ids:
                # c = Course.objects.get(pk=i)
                # stu.course.add(c)
                stu.course.add(course=i)
                print('course added saved')
            stu.save()
            print('student saved')

            return redirect("/")
    context = {
        'userform': userform,
        'type': 'Register',
        'sform': studentForm,
        'title': 'Students'
    }
    return render(request, 'student/studentRegister.html ', context)

def studentList(request):
    stu = student.objects.all()
    context = {'student': stu,
                'title' : 'Students'
    }
    return render(request, 'student/Studentlist.html', context)

def delete(request, pk):
    stu = student.objects.get(id=pk)
    context = {}
    if request.method == 'POST':
        user = stu.user
        stu.delete()
        user.delete()
        return redirect("/")

    context = {
        'id': stu.id,
        'type': 'delete',
        'title': 'Students'
    }

    return render(request, 'student/delete.html ', context)


def update(request, pk):
    course = Course.objects.all()
    stu = student.objects.get(id=pk)
    context = {}
    userform = UserForm(instance=stu.user)
    sform = StudentForm(instance=stu, courseSet=course)
    if request.method == 'POST':
        userform = UserForm(request.POST, instance=stu.user)
        sform = StudentForm(request.POST, instance=stu, courseSet=course)
        try:
            if userform.is_valid():
                userform.save()
                if sform.is_vaild():
                    sform.save()
                    print('student saved')
                    return redirect('')
        except Exception as e:
            pass

    context = {'userform': userform,
               'sform': sform,
               'type': 'Update',
               'id': stu.id,
               'title': 'Students'
               }

    return render(request, 'student/studentRegister.html ', context)
