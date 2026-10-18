from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from attendance.stats import student_summary
from cls.models import Class
from sas.permissions import in_department, linked_records, manager_required, staff_required
from student.forms import StudentForm
from student.models import ROLL_ORDER, student


def _students_for(user):
    return in_department(student.objects.filter(user__is_staff=False),
                         user, 'user__department')


def _classes_for(user):
    return in_department(Class.objects.all(), user).order_by('class_name')


@manager_required
def register(request):
    form = StudentForm(request.POST or None, dept=request.user.department,
                       classes=_classes_for(request.user))
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        messages.success(request, '%s was registered.' % user.full_name)
        if 'add_another' in request.POST:
            return redirect('StudentRegister')
        return redirect('StudentList')
    context = {'title': 'Register student', 'form': form, 'type': 'Create'}
    return render(request, 'student/studentRegister.html', context)


@staff_required
def studentList(request):
    students = (_students_for(request.user)
                .select_related('user', 'cls')
                .order_by('cls__class_name', *ROLL_ORDER))
    context = {'title': 'Students', 'students': students}
    return render(request, 'student/Studentlist.html', context)


@staff_required
def detail(request, pk):
    stu = get_object_or_404(_students_for(request.user).select_related('user', 'cls'), pk=pk)
    from insights.forecast import forecasts
    context = {'title': stu.user.full_name, 'stu': stu, 'summary': student_summary(stu),
               'forecast': forecasts(student.objects.filter(pk=stu.pk)).get(stu.pk),
               'who': stu.user.first_name or 'they'}
    return render(request, 'student/detail.html', context)


@manager_required
def update(request, pk):
    stu = get_object_or_404(_students_for(request.user).select_related('user'), pk=pk)
    form = StudentForm(request.POST or None, instance=stu.user, profile=stu,
                       dept=request.user.department, classes=_classes_for(request.user))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, '%s was updated.' % stu.user.full_name)
        return redirect('student-detail', pk=stu.pk)
    context = {'title': 'Edit student', 'form': form, 'type': 'Update', 'stu': stu}
    return render(request, 'student/studentRegister.html', context)


@manager_required
def delete(request, pk):
    stu = get_object_or_404(_students_for(request.user).select_related('user'), pk=pk)
    if request.method == 'POST':
        name = stu.user.full_name
        stu.user.delete()
        messages.success(request, '%s was deleted.' % name)
        return redirect('StudentList')
    context = {
        'title': 'Delete student',
        'object_name': '%s (%s)' % (stu.user.full_name, stu.user.email),
        'cancel_url': reverse('student-detail', args=[stu.pk]),
        'consequences': linked_records((stu.attendance_set.count(), 'attendance record')),
    }
    return render(request, 'confirm_delete.html', context)
