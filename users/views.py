from django.shortcuts import redirect, render
from django.contrib.auth.models import User
from .forms import UserForm, UserUpdateForm
from .models import TeacherProfile


def index(request):
    teachers = TeacherProfile.objects.all()
    context = {
        'title': 'Teachers',
        'teachers': teachers,
        'range': range(60),
    }
    return render(request, 'users/teachers.html', context)


def register(request):
    userForm = UserForm(request.POST)
    context = {
        'title': 'Teachers',
        'type': 'Create',
        'form': userForm
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
                return render(request, 'users/teachers.html')
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
