from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required

from student.forms import StudentForm, UserForm, UserUpdateForm
from student.models import student

from users.models import User
from course.models import Course

# from users.forms import UserForm

@staff_member_required(login_url='/')
def register(request):
    uDept = request.user.department
    context = {}
    # studentForm=StudentForm(request.POST)
    userform = UserForm(request.POST or None)
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
            
            s = User.objects.get(email=request.POST['email'])
            stu = student.objects.get(user=s)
            print(c_ids)
            for i in c_ids:
                # c = Course.objects.get(pk=i)
                # stu.course.add(c)
                stu.course.add(course=i)
                print('course added saved')
            stu.user.department = uDept
            stu.save()
            # stu.save
            print('student saved')

            return redirect(studentList)
        else:
            print('not valid')
    context = {
        'userform': userform,
        'type': 'Register',
        'sform': studentForm,
        'title': 'Students'
    }
    return render(request, 'student/studentRegister.html ', context)


@login_required(login_url='/')
def studentList(request):
    stu = student.objects.all()
    context = {'student': stu,
                'title' : 'Students'
    }
    return render(request, 'student/Studentlist.html', context)

@staff_member_required(login_url='/')
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

@staff_member_required(login_url='/')
def update(request, pk):
    uDept = request.user.department
    course = Course.objects.filter(dept=uDept)
    stu = student.objects.get(id=pk)
    userform = UserUpdateForm(instance=stu.user)
    sform = StudentForm(instance=stu, courseSet=course)
    if request.method == 'POST':
        print(request.POST)
        userform = UserUpdateForm(request.POST, instance=stu.user)
        sform = StudentForm(request.POST, instance=stu, courseSet=course)
        try:
            if userform.is_valid():
                userform.save()
                if sform.is_valid():
                    sform.save()
                    print('student saved')
                    return redirect(update, pk)
        except Exception as e:
            print(e)

    context = {
        'userform': userform,
        'sform': sform,
        'type': 'Update',
        'id': stu.id,
        'title': 'Students'
    }

    return render(request, 'student/studentRegister.html ', context)
