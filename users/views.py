from django.shortcuts import redirect, render
from django.contrib.auth.models import User
from .forms import TeacherForm, UserForm, UserUpdateForm
from .models import TeacherProfile
from .filters import CourseFilter
from course.models import Course


def index(request):
    teachers = TeacherProfile.objects.all()
    context = {
        'title': 'Teachers',
        'teachers': teachers,
        'range': range(60),
    }
    return render(request, 'users/teachers.html', context)


def register(request):
    courses = Course.objects.all()
    courseFilter = CourseFilter(request.GET, queryset=courses)
    courses = courseFilter.qs
    userForm = UserForm(request.POST)
    teacherForm = TeacherForm(courseSet=courses)
    print('hello')
    context = {
        'title': 'Teachers',
        'type': 'Create',
        'form': userForm,
        'tForm': teacherForm,
        'filter': courseFilter
    }

    if request.method == 'POST':
        userForm = UserForm(request.POST)
        print('not yet valid')
        print(userForm)
        if userForm.is_valid():
            print('valid')
            try:
                userForm.save()
                u = User.objects.get(username=request.POST['username'])
                print('user saved')
                t = TeacherProfile(user=u)
                t.save()
                return redirect(index)
            except Exception as e:
                context = {'e': e}
                print('user not saved')
                print(e)

    return render(request, 'users/TeacherForm.html', context)


def update(request, id):
    teacher = TeacherProfile.objects.get(pk=id)
    userForm = UserUpdateForm(instance=teacher.user)
    context = {
        'title': 'Teachers',
        'type': 'Update',
        'form': userForm,
        'id': teacher.id
    }

    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=teacher.user)
        if form.is_valid():
            form.save()
            return redirect(update, id)
    return render(request, 'users/TeacherForm.html', context)
