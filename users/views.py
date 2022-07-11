from django.shortcuts import redirect, render
from .forms import TeacherForm, UserForm, UserUpdateForm

from .models import TeacherProfile, User
from course.models import Course

from .filters import CourseFilter

from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from .decorators import hod_allowed

@login_required(login_url='/')
def index(request):
    uDept = request.user.department
    print(uDept)
    teachers = TeacherProfile.objects.filter(user__department=uDept)
    context = {
        'title': 'Teachers',
        'teachers': teachers,
    }
    return render(request, 'users/teachers.html', context)

@staff_member_required(login_url="/")
def profile(request):
    return render(request, 'users/profile.html')

@staff_member_required(login_url='/')
@hod_allowed
def register(request):
    
    uDept = request.user.department

    courses = Course.objects.filter(dept=uDept)
    courseFilter = CourseFilter(request.GET, queryset=courses)
    courses = courseFilter.qs
    userForm = UserForm(request.POST or None)
    teacherForm = TeacherForm(courseSet=courses)
    context = {
        'title': 'Teachers',
        'type': 'Create',
        'form': userForm,
        'tForm': teacherForm,
        'filter': courseFilter
    }

    if request.method == 'POST':
        userForm = UserForm(request.POST, department=uDept)
        # userForm = UserForm(request.POST, department=uDept)
        if userForm.is_valid():
            try:
                userForm.save()
                c_ids = request.POST.getlist('course')
                u = User.objects.get(email=request.POST['email'])
                t = TeacherProfile.objects.get(user=u)

                for id in c_ids:
                    c = Course.objects.get(pk=id)
                    t.course.add(c)
                t.save()
                return redirect(index)
            except Exception as e:
                context = {'e': e}
                print('user not saved')
                print(e)
                print('%s' % type(e))

    return render(request, 'users/TeacherForm.html', context)

@staff_member_required(login_url='/')
def update(request, id):
    uDept = request.user.department
    courses = Course.objects.filter(dept=uDept)
    teacher = TeacherProfile.objects.get(pk=id)
    courseFilter = CourseFilter(request.GET, queryset=courses)
    courses = courseFilter.qs
    userForm = UserUpdateForm(instance=teacher.user)
    teacherForm = TeacherForm(instance=teacher, courseSet=courses)

    if request.method == 'POST':
        print(request.POST)
        userForm = UserUpdateForm(request.POST, instance=teacher.user)
        teacherForm = TeacherForm(
            request.POST, instance=teacher, courseSet=courses)
        if userForm.is_valid():
            # try:
                print('user valid')
                userForm.save()
                if teacherForm.is_valid():
                    print('vali')
                    teacherForm.save()
            # except Exception as e:
            #     print(e)
            #     print('%s' % type(e))
            #     # TODO: handle exceptions
    
    context = {
        'title': 'Teachers',
        'type': 'Update',
        'form': userForm,
        'tForm': teacherForm,
        'filter': courseFilter,
        'id': teacher.id
    }

    return render(request, 'users/TeacherForm.html', context)

@staff_member_required(login_url='/')
def delete(request, id):
    teacher = TeacherProfile.objects.get(pk=id)
    context = {
        'title': 'Teachers',
        'id': id
    }
    if request.method == 'POST':
        user = teacher.user
        teacher.delete()
        user.delete()
        return redirect(index)
    return render(request, 'users/delete.html', context)
