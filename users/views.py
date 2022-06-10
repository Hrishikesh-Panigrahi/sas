from django.shortcuts import redirect, render
from django.contrib.auth.models import User
from .forms import TeacherForm, UserForm, UserUpdateForm
from .models import TeacherProfile
from .filters import CourseFilter
from course.models import Course


def index(request):
    teachers = TeacherProfile.objects.all()
    for teacher in teachers:
        for course in teacher.course.all():
            print(course.name)
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
    courses = Course.objects.all()
    teacher = TeacherProfile.objects.get(pk=id)
    courseFilter = CourseFilter(request.GET, queryset=courses)
    courses = courseFilter.qs
    userForm = UserUpdateForm(instance=teacher.user)
    teacherForm = TeacherForm(instance=teacher, courseSet=courses)

    context = {
        'title': 'Teachers',
        'type': 'Update',
        'form': userForm,
        'tForm': teacherForm,
        'filter': courseFilter,
        'id': teacher.id
    }

    if request.method == 'POST':
        userForm = UserUpdateForm(request.POST, instance=teacher.user)
        teacherForm = TeacherForm(
            request.POST, instance=teacher, courseSet=courses)
        try:
            if userForm.is_valid():
                userForm.save()
                if teacherForm.is_valid():
                    teacherForm.save()
                    return redirect(update, id)
        except Exception as e:
            print(e)
            # TODO: handle exceptions
    return render(request, 'users/TeacherForm.html', context)


def delete(request, id):
    teacher = TeacherProfile.objects.get(pk=id)
    context = {
        'title': 'Teachers',
        'id': id
    }
    if request.method == 'POST':
        teacher.delete()
        return redirect(index)
    return render(request, 'users/delete.html', context)
