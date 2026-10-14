from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from attendance.models import Assign_cls, Attendance, AttendanceClass
from sas.permissions import hod_required, in_department, linked_records, staff_required
from .forms import ProfileForm, StyledPasswordChangeForm, TeacherForm
from .models import TeacherProfile


def _teachers_for(user):
    return in_department(TeacherProfile.objects.filter(user__is_staff=True),
                         user, 'user__department')


@staff_required
def index(request):
    teachers = (_teachers_for(request.user)
                .select_related('user', 'class')
                .prefetch_related(Prefetch('assign_cls_set',
                                           queryset=Assign_cls.objects.select_related('cls', 'course')))
                .order_by('user__first_name', 'user__last_name'))
    context = {'title': 'Teachers', 'teachers': teachers}
    return render(request, 'users/teachers.html', context)


@hod_required
def register(request):
    form = TeacherForm(request.POST or None, dept=request.user.department)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        messages.success(request, '%s can now sign in with %s.' % (user.full_name, user.email))
        if 'add_another' in request.POST:
            return redirect('FacultyRegister')
        return redirect('teachers')
    context = {'title': 'Register teacher', 'form': form, 'type': 'Create'}
    return render(request, 'users/TeacherForm.html', context)


@hod_required
def update(request, id):
    teacher = get_object_or_404(_teachers_for(request.user).select_related('user'), pk=id)
    form = TeacherForm(request.POST or None, instance=teacher.user, dept=request.user.department)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, '%s was updated.' % teacher.user.full_name)
        return redirect('teachers')
    context = {
        'title': 'Edit teacher',
        'form': form,
        'type': 'Update',
        'teacher': teacher,
        'assignments': teacher.assign_cls_set.select_related('cls', 'course'),
    }
    return render(request, 'users/TeacherForm.html', context)


@hod_required
def delete(request, id):
    teacher = get_object_or_404(_teachers_for(request.user).select_related('user'), pk=id)
    if teacher.user == request.user:
        messages.error(request, "You can't delete your own account.")
        return redirect('teachers')
    if request.method == 'POST':
        name = teacher.user.full_name
        teacher.user.delete()
        messages.success(request, '%s was deleted.' % name)
        return redirect('teachers')
    lectures = AttendanceClass.objects.filter(assign__teacher=teacher)
    context = {
        'title': 'Delete teacher',
        'object_name': '%s (%s)' % (teacher.user.full_name, teacher.user.email),
        'cancel_url': reverse('updateTeacher', args=[teacher.id]),
        'consequences': linked_records(
            (teacher.assign_cls_set.count(), 'class assignment'),
            (lectures.count(), 'lecture'),
            (Attendance.objects.filter(attendanceclass__in=lectures).count(), 'attendance record'),
        ),
    }
    return render(request, 'confirm_delete.html', context)


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your profile was updated.')
        return redirect('profile')
    context = {'title': 'My profile', 'form': form}
    return render(request, 'users/profile.html', context)


@login_required
def password_change(request):
    form = StyledPasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Your password was changed.')
        return redirect('profile')
    context = {'title': 'Change password', 'form': form}
    return render(request, 'users/password_change.html', context)
